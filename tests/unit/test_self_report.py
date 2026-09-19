"""Unit tests for the self-report receipt (meta_harness.self_report, SPEC-self-report).

The diligence skill asks the agent to end a substantive reply with a VERIFICATION STATUS
block of four labelled lines and no confidence grade. These tests pin the deterministic
verdict on fixture replies and transcripts for every outcome: present, absent, malformed,
graded, exempt, unknown.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from meta_harness.rewrite_contract import prompt_hash
from meta_harness.self_report import (
    FIELDS,
    HEADING,
    Block,
    SelfReportVerdict,
    assess_reply,
    classify,
    evaluate_transcript,
    find_block,
    record,
    record_from_payload,
    to_record,
)
from meta_harness.verdict import SELF_REPORT_FILE, read_self_report_tally

GOOD = (
    "Done.\n\n"
    "VERIFICATION STATUS\n"
    "Verified: unit tests pass — ran pytest\n"
    "Unverified: none\n"
    "Weakest claim: the timeout default — never exercised under load\n"
    "Assumed: UTC timestamps are fine\n"
)


def _entry(kind: str, content: object) -> dict[str, object]:
    entry: dict[str, object] = {"type": kind, "message": {"content": content}}
    if kind == "user":
        entry["origin"] = {"kind": "human"}
    return entry


def _text(text: str) -> list[dict[str, str]]:
    return [{"type": "text", "text": text}]


def _write(path: Path, entries: list[object]) -> Path:
    path.write_text(
        "".join((e if isinstance(e, str) else json.dumps(e)) + "\n" for e in entries),
        encoding="utf-8",
    )
    return path


# --- find_block -------------------------------------------------------------------------


def test_constants_are_the_convention() -> None:
    assert HEADING == "VERIFICATION STATUS"
    assert FIELDS == ("Verified", "Unverified", "Weakest claim", "Assumed")


def test_find_block_reads_all_four_lines_exactly() -> None:
    block = find_block(GOOD)
    assert block is not None
    assert block.values == (
        ("Verified", "unit tests pass — ran pytest"),
        ("Unverified", "none"),
        ("Weakest claim", "the timeout default — never exercised under load"),
        ("Assumed", "UTC timestamps are fine"),
    )
    assert block.present == FIELDS
    assert block.value("Unverified") == "none"
    assert block.value("Nope") is None
    assert block.text.startswith("VERIFICATION STATUS\nVerified:")
    assert block.text.endswith("Assumed: UTC timestamps are fine")


def test_find_block_returns_none_without_a_heading() -> None:
    assert find_block("") is None
    assert find_block("Verified: x\nUnverified: y\nWeakest claim: z\nAssumed: w") is None
    assert find_block("VERIFICATION STATUSES\nVerified: x") is None


def test_heading_and_labels_are_case_insensitive_and_may_be_decorated() -> None:
    reply = (
        "## Verification Status:\n"
        "**verified:** a\n"
        "- _Unverified_: b\n"
        "`WEAKEST CLAIM`: c\n"
        "> Assumed : d\n"
    )
    block = find_block(reply)
    assert block is not None
    assert block.values == (
        ("Verified", "a"),
        ("Unverified", "b"),
        ("Weakest claim", "c"),
        ("Assumed", "d"),
    )


def test_labels_with_a_space_before_the_colon_are_still_labels() -> None:
    block = find_block("VERIFICATION STATUS\nAssumed : d")
    assert block is not None and block.values == (("Assumed", "d"),)


def test_last_heading_wins_when_the_block_appears_twice() -> None:
    reply = GOOD + "\nRevised.\n\nVERIFICATION STATUS\nVerified: only this\n"
    block = find_block(reply)
    assert block is not None
    assert block.values == (("Verified", "only this"),)
    assert block.text == "VERIFICATION STATUS\nVerified: only this"


def test_a_block_inside_a_code_fence_is_ignored() -> None:
    quoted = "Use this template:\n```\n" + GOOD + "```\nThat is all.\n"
    assert find_block(quoted) is None
    # a fence with a language tag and indentation is still a fence; text after it counts
    real = "```md\n" + GOOD + "```\n" + GOOD.replace("none", "the docs")
    block = find_block(real)
    assert block is not None and block.value("Unverified") == "the docs"


def test_repeated_label_keeps_the_last_value_and_continuations_join() -> None:
    reply = (
        "VERIFICATION STATUS\n"
        "ignored preamble line\n"
        "Verified: first\n"
        "  still the first, continued\n"
        "\n"
        "Verified: second\n"
    )
    block = find_block(reply)
    assert block is not None
    assert block.values == (("Verified", "second"),)
    block = find_block("VERIFICATION STATUS\nAssumed: a\n  b\n c\n")
    assert block is not None and block.values == (("Assumed", "a b c"),)


def test_block_text_evidence_is_bounded() -> None:
    reply = "VERIFICATION STATUS\nVerified: " + "x" * 1000
    block = find_block(reply)
    assert block is not None and len(block.text) == 400
    assert block.value("Verified") == "x" * 1000


def test_block_is_immutable() -> None:
    block = Block((("Verified", "a"),), "t")
    with pytest.raises(AttributeError):
        block.text = "u"  # type: ignore[misc]


# --- classify ---------------------------------------------------------------------------


def test_classify_present() -> None:
    v = classify(find_block(GOOD), "abc", 7)
    assert v == SelfReportVerdict(
        "present", "block present with all four lines", "abc", FIELDS, "", 7
    )


def test_classify_absent() -> None:
    assert classify(None, "abc", 3) == SelfReportVerdict(
        "absent", "reply carried no VERIFICATION STATUS block", "abc"
    )


def test_classify_malformed_names_the_missing_lines() -> None:
    block = find_block("VERIFICATION STATUS\nVerified: a\nAssumed: none\n")
    v = classify(block, "abc", 2)
    assert v.status == "malformed"
    assert v.reason == "block is missing: Unverified, Weakest claim"
    assert v.present_fields == ("Verified", "Assumed")
    assert (v.violation, v.line) == ("", 2)


@pytest.mark.parametrize(
    ("value", "violation"),
    [
        ("medium", "Weakest claim: medium"),
        ("Low.", "Weakest claim: Low."),
        ("HIGH!", "Weakest claim: HIGH!"),
        ("med", "Weakest claim: med"),
        ("coverage is 95% here", "95%"),
        ("about 0.5 % of calls", "0.5 %"),
        ("I rate this 7/10", "7/10"),
        ("9 / 10 on the tests", "9 / 10"),
        ("fairly confident in the parser", "confident"),
        ("Confidence: not applicable", "Confidence"),
    ],
)
def test_classify_graded_on_any_ordinal_or_numeric_confidence(value: str, violation: str) -> None:
    reply = GOOD.replace(
        "Weakest claim: the timeout default — never exercised under load", f"Weakest claim: {value}"
    )
    v = classify(find_block(reply), "abc", 1)
    assert v.status == "graded"
    assert v.reason == "block carries a confidence grade (structural rule)"
    assert v.violation == violation
    assert v.present_fields == FIELDS


def test_grade_words_inside_a_sentence_are_not_grades() -> None:
    reply = GOOD.replace(
        "Assumed: UTC timestamps are fine", "Assumed: the high-water mark test is low priority"
    )
    assert classify(find_block(reply), "abc", 1).status == "present"
    # a grade on the heading line's own tail, or with 11/10, is not one of the listed forms
    reply = GOOD.replace("Assumed: UTC timestamps are fine", "Assumed: 11/100 rows migrate")
    assert classify(find_block(reply), "abc", 1).status == "present"


def test_violation_evidence_is_bounded() -> None:
    reply = GOOD.replace("Unverified: none", "Unverified: " + "9" * 200 + "%")
    v = classify(find_block(reply), "abc", 1)
    assert v.status == "graded" and len(v.violation) == 80


def test_classify_defaults() -> None:
    v = classify(None)
    assert (v.prompt_hash, v.line, v.present_fields, v.violation) == ("", None, (), "")


# --- assess_reply -----------------------------------------------------------------------


def test_assess_reply_exempts_trivial_prompts_regardless_of_reply() -> None:
    v = assess_reply("yes", "Sure.", 4)
    assert v == SelfReportVerdict(
        "exempt", "trivial prompt (exempt, as for the rewrite contract)", prompt_hash("yes"), line=4
    )


def test_assess_reply_judges_real_prompts() -> None:
    assert assess_reply("add retries", GOOD, 4).status == "present"
    assert assess_reply("add retries", "Done.", 4).status == "absent"
    assert assess_reply("add retries", GOOD, 4).prompt_hash == prompt_hash("add retries")


# --- evaluate_transcript ----------------------------------------------------------------


def test_evaluate_judges_the_final_assistant_text(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "s.jsonl",
        [
            _entry("user", "old prompt"),
            _entry("assistant", _text(GOOD)),
            _entry("user", "add retries"),
            _entry("assistant", _text("Reading this as: add retries.")),
            _entry("assistant", [{"type": "tool_use", "name": "Bash"}]),
            _entry("assistant", _text(GOOD)),
        ],
    )
    v = evaluate_transcript(path, allowed_root=tmp_path)
    assert (v.status, v.line, v.prompt_hash) == ("present", 6, prompt_hash("add retries"))
    # the opening text alone (no block) would be absent — proving the LAST text is judged
    path = _write(
        tmp_path / "t.jsonl",
        [
            _entry("user", "add retries"),
            _entry("assistant", _text(GOOD)),
            _entry("assistant", _text("Reading this as: add retries.")),
        ],
    )
    assert evaluate_transcript(path, allowed_root=tmp_path).status == "absent"


def test_evaluate_every_unknown_reason(tmp_path: Path) -> None:
    v = evaluate_transcript(tmp_path / "missing.jsonl", allowed_root=tmp_path)
    assert v.status == "unknown" and v.reason.startswith("transcript unreadable: ")
    v = evaluate_transcript(tmp_path / "s.txt", allowed_root=tmp_path)
    assert (v.status, v.reason, v.prompt_hash) == ("unknown", "not a .jsonl transcript", "")
    path = _write(tmp_path / "s.jsonl", ["{garbage", _entry("assistant", _text(GOOD))])
    v = evaluate_transcript(path, allowed_root=tmp_path)
    assert (v.status, v.reason) == ("unknown", "no human prompt found in the transcript tail")
    path = _write(tmp_path / "p.jsonl", [_entry("user", "add retries")])
    v = evaluate_transcript(path, allowed_root=tmp_path)
    assert v.status == "unknown"
    assert v.reason == "no assistant text after the last prompt"
    assert v.prompt_hash == prompt_hash("add retries")


def test_evaluate_exempt_and_graded_transcripts(tmp_path: Path) -> None:
    path = _write(tmp_path / "e.jsonl", [_entry("user", "ok"), _entry("assistant", _text("Done."))])
    assert evaluate_transcript(path, allowed_root=tmp_path).status == "exempt"
    graded = GOOD.replace("Unverified: none", "Unverified: low")
    path = _write(tmp_path / "g.jsonl", [_entry("user", "q"), _entry("assistant", _text(graded))])
    v = evaluate_transcript(path, allowed_root=tmp_path)
    assert (v.status, v.violation) == ("graded", "Unverified: low")


def test_evaluate_uses_the_default_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    root = tmp_path / "projects"
    root.mkdir()
    path = _write(root / "s.jsonl", [_entry("user", "q"), _entry("assistant", _text(GOOD))])
    assert evaluate_transcript(path).status == "present"
    outside = _write(tmp_path / "s.jsonl", [_entry("user", "q")])
    assert evaluate_transcript(outside).reason == (
        "transcript path outside the substrate's transcript directory"
    )


# --- recording --------------------------------------------------------------------------


def test_to_record_shape_is_exact() -> None:
    v = SelfReportVerdict("graded", "r", "h", ("Verified",), "Verified: low", 9)
    assert to_record(v, "s1", "2026-09-09T00:00:00Z") == {
        "ts": "2026-09-09T00:00:00Z",
        "session_id": "s1",
        "prompt_hash": "h",
        "status": "graded",
        "present_fields": ["Verified"],
        "violation": "Verified: low",
        "line": 9,
    }


def test_record_appends_json_lines(tmp_path: Path) -> None:
    v = SelfReportVerdict("present", "r", "h", FIELDS, "", 2)
    record(tmp_path, v, "s1", "2026-09-09T00:00:00Z")
    record(tmp_path, v, "s1")
    lines = (tmp_path / SELF_REPORT_FILE).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first, second = (json.loads(line) for line in lines)
    assert first["ts"] == "2026-09-09T00:00:00Z"
    assert second["ts"].endswith("Z") and len(second["ts"]) == 20
    assert first["present_fields"] == list(FIELDS)
    assert read_self_report_tally(tmp_path).present == 2


def test_record_from_payload_records_every_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    root = tmp_path / "projects"
    root.mkdir()
    transcript = _write(root / "s.jsonl", [_entry("user", "q"), _entry("assistant", _text(GOOD))])
    project = tmp_path / "p"
    now = "2026-09-09T00:00:00Z"

    v = record_from_payload(project, "{not json", now)
    assert (v.status, v.reason) == ("unknown", "hook payload unreadable")
    v = record_from_payload(project, "[1, 2]", now)
    assert (v.status, v.reason) == ("unknown", "hook payload unreadable")
    v = record_from_payload(project, json.dumps({"session_id": "s1"}), now)
    assert (v.status, v.reason) == ("unknown", "no transcript_path in the hook payload")
    v = record_from_payload(project, json.dumps({"transcript_path": ""}), now)
    assert v.status == "unknown"
    payload = json.dumps({"session_id": "s1", "transcript_path": str(transcript)})
    v = record_from_payload(project, payload, now)
    assert v.status == "present"

    rows = [
        json.loads(line)
        for line in (project / SELF_REPORT_FILE).read_text(encoding="utf-8").splitlines()
    ]
    assert [row["status"] for row in rows] == ["unknown"] * 4 + ["present"]
    assert [row["session_id"] for row in rows] == ["", "", "s1", "", "s1"]
    assert rows[-1]["prompt_hash"] == prompt_hash("q") and rows[-1]["line"] == 2
    assert all(row["ts"] == now for row in rows)
    tally = read_self_report_tally(project)
    assert (tally.present, tally.unknown, tally.judged, tally.total) == (1, 4, 1, 5)
