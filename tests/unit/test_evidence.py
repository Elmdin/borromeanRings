"""Unit tests for per-check evidence + gated intent (meta_harness.evidence)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from meta_harness.evidence import (
    Evidence,
    Intent,
    evidence_from_receipt,
    parse_evidence,
    parse_intent,
    read_intent,
)

# --- Evidence: what a receipt SHOWED, not just its status -----------------------------


def test_evidence_from_receipt_copies_the_facts_and_measures_the_log(tmp_path: Path) -> None:
    log = tmp_path / "40_test.log"
    log.write_bytes(b"12 passed\n")  # 10 bytes
    receipt = {
        "check": "40_test",
        "command": "pytest -q",
        "exit_code": 0,
        "log": str(log),
        "status": "pass",
        "content_sha256": "abc",
        "coverage_percent": 99.0,  # check-specific extras are NOT evidence fields
    }
    ev = evidence_from_receipt(receipt, lane="fast")
    assert ev == Evidence(
        check="40_test",
        command="pytest -q",
        exit_code=0,
        log=str(log),
        log_bytes=10,
        content_sha256="abc",
        lane="fast",
    )


def test_evidence_from_receipt_missing_log_is_zero_bytes(tmp_path: Path) -> None:
    receipt = {"check": "x", "log": str(tmp_path / "gone.log"), "exit_code": 2}
    ev = evidence_from_receipt(receipt, lane="heavy")
    assert ev.log_bytes == 0
    assert ev.exit_code == 2
    assert ev.lane == "heavy"
    assert ev.command == ""
    assert ev.content_sha256 == ""


def test_evidence_from_receipt_non_int_exit_code_is_recorded_as_minus_one() -> None:
    # A receipt whose exit_code is not an int (forged/corrupt) must not look like exit 0.
    assert evidence_from_receipt({"check": "x", "exit_code": "0"}, lane="fast").exit_code == -1
    assert evidence_from_receipt({"check": "x", "exit_code": True}, lane="fast").exit_code == -1
    assert evidence_from_receipt({"check": "x"}, lane="fast").exit_code == -1


def test_is_heavy_is_exactly_the_heavy_lane() -> None:
    assert Evidence("a", lane="heavy").is_heavy is True
    assert Evidence("a", lane="fast").is_heavy is False
    assert Evidence("a", lane="HEAVY").is_heavy is False  # exact match, no folding


def test_evidence_to_dict_is_exact() -> None:
    ev = Evidence("a", "cmd", 1, "/l", 5, "h", "heavy")
    assert ev.to_dict() == {
        "check": "a",
        "command": "cmd",
        "exit_code": 1,
        "log": "/l",
        "log_bytes": 5,
        "content_sha256": "h",
        "lane": "heavy",
    }


def test_parse_evidence_round_trips_to_dict() -> None:
    evs = (
        Evidence("a", "c", 0, "/l", 1, "h", "fast"),
        Evidence("b", "d", 3, "/m", 0, "i", "heavy"),
    )
    assert parse_evidence([e.to_dict() for e in evs]) == evs


def test_parse_evidence_fills_defaults_for_partial_entries() -> None:
    assert parse_evidence([{"check": "a"}]) == (Evidence("a"),)
    # exit_code defaults to -1 ("not recorded"): an absent exit must never read as 0.
    assert Evidence("a") == Evidence("a", "", -1, "", 0, "", "fast")


def test_parse_evidence_skips_malformed_entries() -> None:
    raw = [
        {"check": "ok"},
        "not-a-mapping",
        {"command": "no check field"},
        {"check": 7},  # check must be a string
        {"check": "bad-int", "exit_code": "1", "log_bytes": "9"},
        None,
    ]
    got = parse_evidence(raw)
    # non-int numerics degrade to their defaults (-1 / 0); a non-string check is dropped.
    assert got == (Evidence("ok"), Evidence("bad-int"))


def test_parse_evidence_non_list_is_empty() -> None:
    assert parse_evidence(None) == ()
    assert parse_evidence("nope") == ()
    assert parse_evidence({"check": "a"}) == ()


def test_parse_evidence_bool_numerics_are_not_ints() -> None:
    # bool is an int subclass in Python; a True exit code must not become 1.
    assert parse_evidence([{"check": "a", "exit_code": True, "log_bytes": False}]) == (
        Evidence("a"),
    )


# --- Intent: what was gated (branch / head / input digest, read from git) --------------


def test_intent_to_dict_and_parse_round_trip() -> None:
    intent = Intent(branch="feat/x", head_sha="abc123", input_digest="d")
    assert intent.to_dict() == {"branch": "feat/x", "head_sha": "abc123", "input_digest": "d"}
    assert parse_intent(intent.to_dict()) == intent


def test_parse_intent_partial_and_malformed_defaults_empty() -> None:
    assert parse_intent({"branch": "b"}) == Intent(branch="b")
    assert parse_intent(None) == Intent()
    assert parse_intent([1, 2]) == Intent()
    # non-string fields are coerced to str, never raise.
    assert parse_intent({"head_sha": 42}) == Intent(head_sha="42")


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def test_read_intent_reads_branch_and_head_from_git(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "trunk")
    _git(
        repo,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@e",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "i",
    )
    intent = read_intent(repo, "digest-1")
    assert intent.branch == "trunk"
    assert intent.head_sha == _git(repo, "rev-parse", "HEAD")
    assert len(intent.head_sha) == 40
    assert intent.input_digest == "digest-1"


def test_read_intent_outside_git_is_empty_but_keeps_digest(tmp_path: Path) -> None:
    intent = read_intent(tmp_path, "digest-2")
    assert intent == Intent(branch="", head_sha="", input_digest="digest-2")


def test_read_intent_without_git_binary_is_empty(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))  # no git on PATH ⇒ OSError ⇒ fail-soft
    assert read_intent(tmp_path, "d") == Intent(input_digest="d")
