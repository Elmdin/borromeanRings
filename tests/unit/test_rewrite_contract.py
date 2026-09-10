"""Unit tests for the rewrite contract (meta_harness.rewrite_contract, SPEC-rewrite-contract).

The UserPromptSubmit directive asks the agent to open its reply with a ``Reading this
as:`` line. These tests pin the deterministic verdict on fixture transcripts: honoured,
not honoured, exempt (trivial prompt), unknown (missing / malformed / no exchange).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from meta_harness.prompt_rewrite import MARKER, build_directive
from meta_harness.rewrite_contract import (
    DEFAULT_TAIL_BYTES,
    TRIVIAL_PROMPTS,
    Exchange,
    RewriteVerdict,
    TranscriptRefused,
    assess_reply,
    default_transcript_root,
    evaluate_transcript,
    find_last_exchange,
    is_trivial,
    parse_entries,
    prompt_hash,
    read_tail,
    record,
    record_from_payload,
    to_record,
)
from meta_harness.verdict import REWRITE_CONTRACT_FILE, read_rewrite_tally

# --- fixtures ---------------------------------------------------------------------------


def _user(text: str, *, human: bool = True, meta: bool = False) -> dict[str, object]:
    entry: dict[str, object] = {"type": "user", "message": {"role": "user", "content": text}}
    if human:
        entry["origin"] = {"kind": "human"}
    if meta:
        entry["isMeta"] = True
    return entry


def _tool_result() -> dict[str, object]:
    return {
        "type": "user",
        "origin": {"kind": "human"},
        "message": {"role": "user", "content": [{"type": "tool_result", "content": "ok"}]},
    }


def _assistant(*blocks: dict[str, object], sidechain: bool = False) -> dict[str, object]:
    entry: dict[str, object] = {
        "type": "assistant",
        "message": {"role": "assistant", "content": list(blocks)},
    }
    if sidechain:
        entry["isSidechain"] = True
    return entry


def _text(text: str) -> dict[str, object]:
    return {"type": "text", "text": text}


def _write(path: Path, entries: list[object]) -> Path:
    path.write_text(
        "".join((e if isinstance(e, str) else json.dumps(e)) + "\n" for e in entries),
        encoding="utf-8",
    )
    return path


# --- marker / hash / exemption ------------------------------------------------------------


def test_marker_is_the_one_the_directive_asks_for() -> None:
    assert MARKER == "Reading this as:"
    assert f'"{MARKER} <your sharpened version of the request>"' in build_directive({})


def test_prompt_hash_is_the_hooks_dedupe_digest() -> None:
    """Same digest as prompt_rewrite.sh's dedupe key, so the two records can be joined."""
    import hashlib

    assert prompt_hash("fix the bug") == hashlib.sha256(b"fix the bug").hexdigest()[:16]
    assert len(prompt_hash("")) == 16


@pytest.mark.parametrize(
    "prompt", ["yes", "No", "  continue  ", "ok.", "y", "go ahead!", "Yes, please", ""]
)
def test_trivial_prompts_are_exempt(prompt: str) -> None:
    assert is_trivial(prompt) is True


@pytest.mark.parametrize(
    "prompt", ["yes, and also refactor the parser", "continue with the ADR", "fix the bug", "/x"]
)
def test_real_requests_are_not_exempt(prompt: str) -> None:
    assert is_trivial(prompt) is False


def test_trivial_set_is_small_and_bare() -> None:
    assert {"yes", "no", "continue", "ok", "y", "n"} <= TRIVIAL_PROMPTS
    assert all(p == p.lower().strip() for p in TRIVIAL_PROMPTS)


# --- assess_reply -------------------------------------------------------------------------


def test_reply_opening_with_the_marker_is_honoured() -> None:
    v = assess_reply("fix the bug", "Reading this as: fix the null deref in parse().\n\nDone.", 7)
    assert v == RewriteVerdict(
        status="honoured",
        reason="reply opened with the marker",
        prompt_hash=prompt_hash("fix the bug"),
        line=7,
        matched="Reading this as: fix the null deref in parse().",
    )
    assert v.honoured is True


def test_marker_may_be_emphasised_and_preceded_by_blank_lines() -> None:
    v = assess_reply("fix", "\n\n**Reading this as:** tighten the loop\n", 3)
    assert v.status == "honoured"
    assert v.matched == "Reading this as:** tighten the loop"


def test_marker_match_is_case_insensitive_but_must_open_the_reply() -> None:
    assert assess_reply("fix", "reading this as: x", 1).status == "honoured"
    v = assess_reply("fix", "Sure.\nReading this as: x", 1)
    assert v.status == "not_honoured"
    assert v.matched == "Sure."
    assert v.reason == "reply opened with something else"
    assert v.honoured is False


def test_empty_reply_is_not_honoured() -> None:
    v = assess_reply("fix", "   \n", 9)
    assert (v.status, v.reason, v.matched, v.line) == (
        "not_honoured",
        "reply had no text",
        "",
        9,
    )


def test_trivial_prompt_is_exempt_regardless_of_reply() -> None:
    v = assess_reply("yes", "Sure, doing it.", 2)
    assert v.status == "exempt"
    assert v.reason == "trivial prompt (exempt by the directive's own wording)"
    assert v.honoured is None
    assert v.line == 2
    assert v.matched == "Sure, doing it."


def test_matched_text_is_bounded() -> None:
    v = assess_reply("fix", "Reading this as: " + "x" * 500, 1)
    assert len(v.matched) == 200


def test_verdict_is_immutable() -> None:
    v = assess_reply("fix", "Reading this as: y", 1)
    with pytest.raises(AttributeError):
        v.status = "exempt"  # type: ignore[misc]


# --- parse_entries / find_last_exchange ---------------------------------------------------


def test_parse_entries_numbers_lines_and_skips_garbage() -> None:
    lines = ['{"type": "user"}', "", "{not json", "[1, 2]", '{"type": "assistant"}']
    assert parse_entries(lines, 10) == [(10, {"type": "user"}), (14, {"type": "assistant"})]


def test_last_exchange_is_the_last_human_prompt_and_its_first_text() -> None:
    entries = parse_entries(
        [
            json.dumps(_user("first")),
            json.dumps(_assistant(_text("Reading this as: first"))),
            json.dumps(_user("second")),
            json.dumps(_assistant({"type": "thinking", "thinking": "..."})),
            json.dumps(_assistant({"type": "tool_use", "name": "Bash"})),
            json.dumps(_tool_result()),
            json.dumps(_assistant(_text(""), _text("Reading this as: second"))),
            json.dumps(_assistant(_text("later text"))),
        ],
        1,
    )
    assert find_last_exchange(entries) == Exchange(
        prompt="second", reply="Reading this as: second", reply_line=7
    )


def test_prompt_text_blocks_are_joined_and_meta_or_nonhuman_entries_are_ignored() -> None:
    prompt = {
        "type": "user",
        "origin": {"kind": "human"},
        "message": {"content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]},
    }
    entries = parse_entries(
        [
            json.dumps(prompt),
            json.dumps(_assistant(_text("Reading this as: ab"))),
            json.dumps(_user("skill text", meta=True)),
            json.dumps(_user("/compact", human=False)),
            json.dumps({"type": "user", "origin": {"kind": "task-notification"}, "message": {}}),
            json.dumps({"type": "user", "origin": "human", "message": {"content": "x"}}),
            json.dumps({"type": "user", "origin": {"kind": "human"}, "message": "bad"}),
            json.dumps({"type": "user", "origin": {"kind": "human"}, "message": {"content": 5}}),
            json.dumps({"type": "user", "origin": {"kind": "human"}, "message": {"content": [1]}}),
            json.dumps(_assistant(_text("no prompt above me counts"))),
        ],
        1,
    )
    assert find_last_exchange(entries) == Exchange(
        prompt="a b", reply="Reading this as: ab", reply_line=2
    )


def test_sidechain_and_malformed_assistant_entries_are_not_the_reply() -> None:
    entries = parse_entries(
        [
            json.dumps(_user("q")),
            json.dumps(_assistant(_text("sub-agent"), sidechain=True)),
            json.dumps({"type": "assistant", "message": "bad"}),
            json.dumps({"type": "assistant", "message": {"content": "str"}}),
            json.dumps({"type": "assistant", "message": {"content": [{"type": "text"}]}}),
            json.dumps(
                {"type": "assistant", "message": {"content": [{"type": "text", "text": 1}]}}
            ),
            json.dumps({"type": "system"}),
        ],
        1,
    )
    assert find_last_exchange(entries) == Exchange(prompt="q", reply=None, reply_line=None)


def test_no_human_prompt_means_no_exchange() -> None:
    assert find_last_exchange([]) is None
    assert find_last_exchange(parse_entries([json.dumps(_assistant(_text("x")))], 1)) is None


# --- read_tail ----------------------------------------------------------------------------


def test_read_tail_of_a_small_file_is_the_whole_file(tmp_path: Path) -> None:
    path = _write(tmp_path / "t.jsonl", ["a", "b", "c"])
    assert read_tail(path, allowed_root=tmp_path) == (1, ["a", "b", "c", ""])


def test_read_tail_drops_the_partial_first_line_and_keeps_line_numbers(tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl"
    path.write_bytes(b"line1\nline2\nline3\nline4\n")
    # 14 bytes back from the end lands mid-"line2" (bytes: "e2\nline3\nline4\n"): one
    # newline was skipped, the partial line is dropped, so "line3" is line 3.
    assert read_tail(path, max_bytes=14, allowed_root=tmp_path) == (3, ["line3", "line4", ""])


def test_read_tail_exact_boundary_still_drops_the_first_line(tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl"
    path.write_bytes(b"ab\ncd\n")
    # 3 bytes back is exactly the start of "cd\n"; the boundary is not provably a line
    # start without reading further back, so the (possibly partial) first line goes.
    assert read_tail(path, max_bytes=3, allowed_root=tmp_path) == (3, [""])


def test_read_tail_is_bounded_and_streams_the_skipped_prefix(tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl"
    path.write_bytes(b"x" * 300_000 + b"\n" + b"y\n" * 5)
    first, lines = read_tail(path, max_bytes=8, allowed_root=tmp_path)
    # start = 300_003: two newlines skipped (after the x's, and the first "y\n"), the
    # partial "y" line dropped ⇒ the first kept line is line 4.
    assert (first, lines) == (4, ["y", "y", "y", ""])
    assert DEFAULT_TAIL_BYTES == 8 * 1024 * 1024


def test_read_tail_refuses_non_jsonl_symlink_and_missing(tmp_path: Path) -> None:
    with pytest.raises(TranscriptRefused, match="not a .jsonl"):
        read_tail(tmp_path / "t.txt", allowed_root=tmp_path)
    real = _write(tmp_path / "real.jsonl", ["{}"])
    link = tmp_path / "link.jsonl"
    link.symlink_to(real)
    with pytest.raises(TranscriptRefused, match="symlink"):
        read_tail(link, allowed_root=tmp_path)
    with pytest.raises(OSError):
        read_tail(tmp_path / "missing.jsonl", allowed_root=tmp_path)
    assert issubclass(TranscriptRefused, ValueError)


OUTSIDE = "transcript path outside the substrate's transcript directory"


def test_read_tail_refuses_paths_outside_the_transcript_root(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    root.mkdir()
    inside = _write(root / "s.jsonl", ["{}"])
    outside = _write(tmp_path / "elsewhere.jsonl", ["{}"])
    assert read_tail(inside, allowed_root=root) == (1, ["{}", ""])
    with pytest.raises(TranscriptRefused, match=OUTSIDE):
        read_tail(outside, allowed_root=root)
    # a traversal that only LOOKS inside is resolved before the check
    with pytest.raises(TranscriptRefused, match=OUTSIDE):
        read_tail(root / ".." / "elsewhere.jsonl", allowed_root=root)
    # a root that resolves to the same place is honoured either way
    assert read_tail(root / "." / "s.jsonl", allowed_root=root / "..")[0] == 1


def test_read_tail_refuses_a_symlink_escape_as_outside(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    root.mkdir()
    secret = _write(tmp_path / "secret.jsonl", ['{"leak": 1}'])
    escape = root / "escape.jsonl"
    escape.symlink_to(secret)
    with pytest.raises(TranscriptRefused, match=OUTSIDE):
        read_tail(escape, allowed_root=root)
    v = evaluate_transcript(escape, allowed_root=root)
    assert v == RewriteVerdict("unknown", OUTSIDE, "")


def test_default_transcript_root_prefers_config_dir_then_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    assert default_transcript_root() == tmp_path / "cfg" / "projects"
    monkeypatch.delenv("CLAUDE_CONFIG_DIR")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    assert default_transcript_root() == tmp_path / "home"  # no ~/.claude/projects yet
    (tmp_path / "home" / ".claude" / "projects").mkdir(parents=True)
    assert default_transcript_root() == tmp_path / "home" / ".claude" / "projects"

    def no_home(cls: type[Path]) -> Path:
        raise RuntimeError("no home")

    monkeypatch.setattr(Path, "home", classmethod(no_home))
    assert default_transcript_root() is None
    with pytest.raises(TranscriptRefused, match=OUTSIDE):
        read_tail(tmp_path / "x.jsonl")


def test_evaluate_uses_the_default_root_when_none_is_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    root = tmp_path / "projects"
    root.mkdir()
    path = _write(root / "s.jsonl", [_user("ship it"), _assistant(_text("Reading this as: ship"))])
    assert evaluate_transcript(path).status == "honoured"
    stray = _write(tmp_path / "stray.jsonl", [_user("ship it")])
    assert evaluate_transcript(stray) == RewriteVerdict("unknown", OUTSIDE, "")


# --- evaluate_transcript ------------------------------------------------------------------


def test_evaluate_honoured_transcript(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "s.jsonl",
        [
            {"type": "mode", "mode": "x"},
            _user("add a retry to the client"),
            _assistant({"type": "thinking", "thinking": ""}),
            _assistant(_text("Reading this as: add bounded retries to HttpClient.get.\nOn it.")),
        ],
    )
    v = evaluate_transcript(path, allowed_root=tmp_path)
    assert v == RewriteVerdict(
        status="honoured",
        reason="reply opened with the marker",
        prompt_hash=prompt_hash("add a retry to the client"),
        line=4,
        matched="Reading this as: add bounded retries to HttpClient.get.",
    )


def test_evaluate_not_honoured_transcript(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "s.jsonl", [_user("add a retry"), _assistant(_text("Sure! Adding it now."))]
    )
    v = evaluate_transcript(path, allowed_root=tmp_path)
    assert (v.status, v.line, v.matched) == ("not_honoured", 2, "Sure! Adding it now.")


def test_evaluate_exempt_transcript(tmp_path: Path) -> None:
    path = _write(tmp_path / "s.jsonl", [_user("continue"), _assistant(_text("Continuing."))])
    v = evaluate_transcript(path, allowed_root=tmp_path)
    assert (v.status, v.prompt_hash) == ("exempt", prompt_hash("continue"))


def test_evaluate_missing_transcript_is_unknown(tmp_path: Path) -> None:
    v = evaluate_transcript(tmp_path / "nope.jsonl", allowed_root=tmp_path)
    assert v.status == "unknown"
    assert v.reason.startswith("transcript unreadable: ")
    assert (v.prompt_hash, v.line, v.matched, v.honoured) == ("", None, "", None)


def test_evaluate_non_jsonl_path_is_unknown(tmp_path: Path) -> None:
    (tmp_path / "t.txt").write_text("{}", encoding="utf-8")
    v = evaluate_transcript(tmp_path / "t.txt", allowed_root=tmp_path)
    assert v == RewriteVerdict("unknown", "not a .jsonl transcript", "")


def test_evaluate_malformed_transcript_is_unknown(tmp_path: Path) -> None:
    path = _write(tmp_path / "s.jsonl", ["{garbage", "more garbage"])
    v = evaluate_transcript(path, allowed_root=tmp_path)
    assert v == RewriteVerdict("unknown", "no human prompt found in the transcript tail", "")


def test_evaluate_prompt_without_reply_is_unknown(tmp_path: Path) -> None:
    path = _write(tmp_path / "s.jsonl", [_user("do the thing")])
    v = evaluate_transcript(path, allowed_root=tmp_path)
    assert v == RewriteVerdict(
        "unknown", "no assistant text after the last prompt", prompt_hash("do the thing")
    )


def test_evaluate_reads_only_the_tail(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "s.jsonl",
        [_user("old"), _assistant(_text("Reading this as: old")), _user("new" * 10)],
    )
    v = evaluate_transcript(path, max_bytes=40, allowed_root=tmp_path)
    assert v.status == "unknown"


# --- record -------------------------------------------------------------------------------


def test_to_record_shape_is_exact() -> None:
    v = RewriteVerdict("honoured", "reply opened with the marker", "abc", 4, "Reading this as: x")
    assert to_record(v, "s1", "2026-09-08T10:00:00Z") == {
        "ts": "2026-09-08T10:00:00Z",
        "session_id": "s1",
        "prompt_hash": "abc",
        "honoured": True,
        "status": "honoured",
        "reason": "reply opened with the marker",
        "line": 4,
        "matched": "Reading this as: x",
    }
    unknown = to_record(RewriteVerdict("unknown", "why", ""), "", "t")
    assert (unknown["honoured"], unknown["line"], unknown["matched"]) == (None, None, "")


def test_record_appends_one_json_line_and_tally_reads_it_back(tmp_path: Path) -> None:
    record(tmp_path, RewriteVerdict("honoured", "r", "h1", 1, "m"), "s1", now="t1")
    record(tmp_path, RewriteVerdict("not_honoured", "r", "h2", 2, "m"), "s1", now="t2")
    lines = (tmp_path / REWRITE_CONTRACT_FILE).read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["ts"] for line in lines] == ["t1", "t2"]
    assert json.loads(lines[0])["honoured"] is True
    tally = read_rewrite_tally(tmp_path)
    assert (tally.honoured, tally.judged) == (1, 2)


def test_record_default_timestamp_is_utc_iso(tmp_path: Path) -> None:
    record(tmp_path, RewriteVerdict("exempt", "r", "h", 1, ""), "s")
    ts = json.loads((tmp_path / REWRITE_CONTRACT_FILE).read_text(encoding="utf-8"))["ts"]
    assert ts.endswith("Z") and len(ts) == 20


def test_record_from_payload_records_the_transcript_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    (tmp_path / "projects").mkdir()
    transcript = _write(
        tmp_path / "projects" / "s.jsonl",
        [_user("build it"), _assistant(_text("Reading this as: build X"))],
    )
    payload = json.dumps({"session_id": "s9", "transcript_path": str(transcript)})
    v = record_from_payload(tmp_path, payload, now="t")
    assert v.status == "honoured"
    row = json.loads((tmp_path / REWRITE_CONTRACT_FILE).read_text(encoding="utf-8"))
    assert (row["session_id"], row["status"], row["ts"]) == ("s9", "honoured", "t")


def test_record_from_payload_survives_garbage_and_missing_path(tmp_path: Path) -> None:
    assert record_from_payload(tmp_path, "{not json", now="t") == RewriteVerdict(
        "unknown", "hook payload unreadable", ""
    )
    assert record_from_payload(
        tmp_path, json.dumps({"session_id": "s"}), now="t"
    ) == RewriteVerdict("unknown", "no transcript_path in the hook payload", "")
    assert record_from_payload(tmp_path, json.dumps([1]), now="t").reason == (
        "no transcript_path in the hook payload"
    )
    tally = read_rewrite_tally(tmp_path)
    assert (tally.unknown, tally.judged) == (3, 0)


def test_last_exchange_can_pick_the_final_reply_instead_of_the_first() -> None:
    entries = parse_entries(
        [
            json.dumps(_user("q")),
            json.dumps(_assistant(_text("first"))),
            json.dumps(_assistant({"type": "tool_use", "name": "Bash"})),
            json.dumps(_assistant(_text("last"))),
        ],
        1,
    )
    assert find_last_exchange(entries) == Exchange("q", "first", 2)
    assert find_last_exchange(entries, final=True) == Exchange("q", "last", 4)
    only_prompt = parse_entries([json.dumps(_user("q"))], 1)
    assert find_last_exchange(only_prompt, final=True) == Exchange("q", None, None)
