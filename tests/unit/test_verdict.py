"""Unit tests for persisted gate verdicts (meta_harness.verdict)."""

from __future__ import annotations

from pathlib import Path

from meta_harness.verdict import (
    LAST_VERDICT_FILE,
    VERDICT_HISTORY_FILE,
    Verdict,
    append_history,
    read_history,
    read_last_verdict,
    write_last_verdict,
)


def test_write_then_read_round_trips(tmp_path: Path) -> None:
    v = Verdict(
        ok=True, checks=(("00_build", "pass"), ("40_test", "pass")), run_id="r1", digest="d1"
    )
    write_last_verdict(tmp_path, v)
    assert (tmp_path / LAST_VERDICT_FILE).is_file()
    got = read_last_verdict(tmp_path)
    assert got == v


def test_write_creates_evidence_dir(tmp_path: Path) -> None:
    # .meta-harness/ need not pre-exist — write creates it.
    write_last_verdict(tmp_path, Verdict(ok=False, checks=(("50_security", "fail"),)))
    got = read_last_verdict(tmp_path)
    assert got is not None
    assert got.ok is False
    assert got.checks == (("50_security", "fail"),)


def test_write_creates_nested_project_dirs(tmp_path: Path) -> None:
    # the project root itself may not exist yet ⇒ parent dirs must be created.
    proj = tmp_path / "new" / "proj"
    write_last_verdict(proj, Verdict(ok=True))
    assert read_last_verdict(proj) == Verdict(ok=True)


def test_written_file_is_pretty_printed(tmp_path: Path) -> None:
    # evidence is human-readable (indented), not a single dense line.
    write_last_verdict(tmp_path, Verdict(ok=True, checks=(("00_build", "pass"),)))
    text = (tmp_path / LAST_VERDICT_FILE).read_text(encoding="utf-8")
    assert "\n  " in text


def test_read_verdict_without_checks_key_defaults_empty(tmp_path: Path) -> None:
    path = tmp_path / LAST_VERDICT_FILE
    path.parent.mkdir(parents=True)
    path.write_text('{"ok": true}', encoding="utf-8")
    v = read_last_verdict(tmp_path)
    assert v == Verdict(ok=True, checks=())
    # absent run_id/digest default to "" — not the string "None".
    assert v is not None
    assert v.run_id == ""
    assert v.digest == ""


def test_read_excludes_malformed_check_pairs(tmp_path: Path) -> None:
    path = tmp_path / LAST_VERDICT_FILE
    path.parent.mkdir(parents=True)
    # "xy" is length-2 but not a list/tuple ⇒ must be excluded (and-not-or).
    path.write_text('{"ok": true, "checks": [["a", "b"], "xy"]}', encoding="utf-8")
    got = read_last_verdict(tmp_path)
    assert got is not None
    assert got.checks == (("a", "b"),)


def test_read_missing_returns_none(tmp_path: Path) -> None:
    assert read_last_verdict(tmp_path) is None


def test_read_malformed_json_returns_none(tmp_path: Path) -> None:
    path = tmp_path / LAST_VERDICT_FILE
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    assert read_last_verdict(tmp_path) is None


def test_read_wrong_shape_returns_none(tmp_path: Path) -> None:
    path = tmp_path / LAST_VERDICT_FILE
    path.parent.mkdir(parents=True)
    # a JSON array, and an object missing 'ok', both invalid
    for bad in ("[1, 2, 3]", '{"checks": []}', '{"ok": "yes"}', '{"ok": true, "checks": "nope"}'):
        path.write_text(bad, encoding="utf-8")
        assert read_last_verdict(tmp_path) is None


def test_append_history_accumulates_in_order(tmp_path: Path) -> None:
    # the project root may not exist yet ⇒ dirs are created; entries keep insertion order.
    proj = tmp_path / "new" / "proj"
    append_history(proj, Verdict(ok=True, run_id="r1"))
    append_history(proj, Verdict(ok=False, run_id="r2"))
    hist = read_history(proj)
    assert [v.ok for v in hist] == [True, False]
    assert [v.run_id for v in hist] == ["r1", "r2"]


def test_read_history_missing_returns_empty(tmp_path: Path) -> None:
    assert read_history(tmp_path) == []


def test_read_history_skips_blank_and_malformed_lines(tmp_path: Path) -> None:
    path = tmp_path / VERDICT_HISTORY_FILE
    path.parent.mkdir(parents=True)
    # a good line, a blank, a non-JSON line, and a valid-JSON-but-wrong-shape line.
    path.write_text(
        '{"ok": true}\n\n{not json\n[1, 2, 3]\n{"ok": false}\n',
        encoding="utf-8",
    )
    hist = read_history(tmp_path)
    assert [v.ok for v in hist] == [True, False]


def test_to_dict_is_json_shaped() -> None:
    v = Verdict(ok=True, checks=(("00_build", "pass"),), run_id="r", digest="d")
    d = v.to_dict()
    assert d == {"ok": True, "run_id": "r", "digest": "d", "checks": [["00_build", "pass"]]}
