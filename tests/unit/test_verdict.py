"""Unit tests for persisted gate verdicts (meta_harness.verdict)."""

from __future__ import annotations

import json
from pathlib import Path

from meta_harness.evidence import Evidence, Intent
from meta_harness.verdict import (
    LAST_VERDICT_FILE,
    NON_FAILING_STATUSES,
    REWRITE_CONTRACT_FILE,
    REWRITE_STATUSES,
    RISK_BANDS,
    SELF_REPORT_FILE,
    SELF_REPORT_STATUSES,
    VERDICT_HISTORY_FILE,
    RewriteTally,
    SelfReportTally,
    Verdict,
    advisory_failures,
    append_history,
    append_rewrite_record,
    append_self_report_record,
    is_failing,
    read_history,
    read_last_verdict,
    read_rewrite_tally,
    read_self_report_tally,
    risk_band,
    status_label,
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
    v = Verdict(
        ok=True,
        checks=(("00_build", "pass"),),
        run_id="r",
        digest="d",
        harness_version="v1.2.3",
        intent=Intent(generator="claude-code:s1"),
    )
    d = v.to_dict()
    assert d == {
        "ok": True,
        "run_id": "r",
        "digest": "d",
        "harness_version": "v1.2.3",
        "risk": "",
        "intent": {
            "branch": "",
            "head_sha": "",
            "input_digest": "",
            "generator": "claude-code:s1",
        },
        "lane": "",
        "checks": [["00_build", "pass"]],
        "evidence": [],
    }


def test_lane_round_trips_and_defaults_to_unmarked(tmp_path: Path) -> None:
    # A partial (fast-lane) green has to stay distinguishable from a full one once it is
    # written down, not only in the console output it scrolled past. See ADR-0081.
    write_last_verdict(tmp_path, Verdict(ok=True, lane="fast"))
    got = read_last_verdict(tmp_path)
    assert got is not None and got.lane == "fast"
    # A record written before lanes existed reads back as "" — never as a fast one.
    (tmp_path / LAST_VERDICT_FILE).write_text('{"ok": true, "checks": []}', encoding="utf-8")
    legacy = read_last_verdict(tmp_path)
    assert legacy is not None and legacy.lane == ""


def test_harness_version_round_trips(tmp_path: Path) -> None:
    # the governing borromeanRings version is persisted and read back verbatim.
    write_last_verdict(tmp_path, Verdict(ok=True, harness_version="v1.0.0-3-gabc123"))
    got = read_last_verdict(tmp_path)
    assert got is not None
    assert got.harness_version == "v1.0.0-3-gabc123"


def test_read_verdict_without_harness_version_defaults_empty(tmp_path: Path) -> None:
    # records written before versioning have no harness_version ⇒ "" (not "None").
    path = tmp_path / LAST_VERDICT_FILE
    path.parent.mkdir(parents=True)
    path.write_text('{"ok": true, "checks": []}', encoding="utf-8")
    v = read_last_verdict(tmp_path)
    assert v is not None
    assert v.harness_version == ""


# --- fail-closed status classification (the gate's core safety property) -------------
# The gate must decide "does this status fail the run?" from an explicit ALLOWLIST.
# Written as a negation ("anything that isn't 'fail'"), a new/typo'd/forged status would
# silently pass — which is exactly the hole that introducing 'noop' could open.


def test_real_pass_and_noop_do_not_fail_the_gate() -> None:
    assert is_failing("pass") is False
    assert is_failing("noop") is False


def test_fail_and_error_fail_the_gate() -> None:
    assert is_failing("fail") is True
    assert is_failing("error") is True


def test_unknown_status_fails_closed() -> None:
    """The critical property: anything not explicitly allowlisted must FAIL."""
    for unknown in ("", "?", "skipped", "noopp", "ok", "success", "MISSING", "unknown"):
        assert is_failing(unknown) is True, f"{unknown!r} must fail closed"


def test_status_matching_is_exact_not_fuzzy() -> None:
    # Case/whitespace variants are not silently accepted — only the canonical form is.
    for variant in ("PASS", "Pass", " pass", "pass ", "NOOP"):
        assert is_failing(variant) is True, f"{variant!r} must not be treated as a pass"


def test_non_failing_allowlist_is_immutable_and_minimal() -> None:
    assert isinstance(NON_FAILING_STATUSES, frozenset)
    assert sorted(NON_FAILING_STATUSES) == ["noop", "pass"]


# --- intent.generator: who produced the change this verdict judged (ADR-0071 §4) ------
# Provenance, not evidence. Self-declared by the adapter that ran the gate; the gate
# makes no decision on it, and a record that carries none reads "" — never a guess.


def test_generator_round_trips_under_intent(tmp_path: Path) -> None:
    """The persisted shape is ``intent.generator``, a field of ADR-0056's Intent (ADR-0078)."""
    verdict = Verdict(
        ok=True,
        checks=(("20_lint", "pass"),),
        intent=Intent(generator="headless:apply_patch.sh"),
    )
    assert verdict.to_dict()["intent"]["generator"] == "headless:apply_patch.sh"
    write_last_verdict(tmp_path, verdict)
    got = read_last_verdict(tmp_path)
    assert got is not None
    assert got.intent.generator == "headless:apply_patch.sh"


def test_generator_defaults_to_empty_not_guessed() -> None:
    """A gate run with nothing declared records nothing, and says so as ``""``."""
    assert Verdict(ok=True).intent.generator == ""
    assert Verdict(ok=True).to_dict()["intent"]["generator"] == ""


def test_records_without_an_intent_read_unchanged(tmp_path: Path) -> None:
    """Fail-soft: every verdict written before this field parses as before."""
    path = tmp_path / LAST_VERDICT_FILE
    path.parent.mkdir(parents=True)
    path.write_text('{"ok": true, "checks": [["20_lint", "pass"]]}', encoding="utf-8")
    got = read_last_verdict(tmp_path)
    assert got is not None
    assert (got.ok, got.intent.generator) == (True, "")


def test_a_malformed_intent_yields_no_generator(tmp_path: Path) -> None:
    """Anything that is not an object carrying a string is not provenance."""
    path = tmp_path / LAST_VERDICT_FILE
    path.parent.mkdir(parents=True)
    for intent in ('"claude-code"', "[]", "17", "null", '{"generator": 17}', '{"branch": "dev"}'):
        path.write_text(f'{{"ok": true, "checks": [], "intent": {intent}}}', encoding="utf-8")
        got = read_last_verdict(tmp_path)
        assert got is not None, intent
        assert got.intent.generator == "", intent


def test_history_carries_the_generator_too(tmp_path: Path) -> None:
    """The ledger's rows attribute their change like the last-verdict record does."""
    append_history(tmp_path, Verdict(ok=False, intent=Intent(generator="claude-code:s1")))
    append_history(tmp_path, Verdict(ok=True, intent=Intent(generator="claude-code:s1")))
    assert [v.intent.generator for v in read_history(tmp_path)] == [
        "claude-code:s1",
        "claude-code:s1",
    ]


# --- evidence, intent and the risk band (ADR-0056) ------------------------------------
# The verdict records what was SHOWN to happen, not only pass/fail: per-check evidence,
# the gated intent, and a band derived deterministically from the recorded facts.


def _rich_verdict() -> Verdict:
    return Verdict(
        ok=True,
        checks=(("00_build", "pass"), ("60_mutation", "noop")),
        run_id="r",
        digest="d",
        harness_version="v1",
        risk="hollow",
        intent=Intent(branch="feat/x", head_sha="abc", input_digest="in"),
        evidence=(
            Evidence("00_build", "python -m build", 0, "/l/00.log", 12, "h0", "fast"),
            Evidence("60_mutation", "mutmut run", 0, "/l/60.log", 0, "h6", "heavy"),
        ),
    )


def test_rich_verdict_to_dict_is_exact_and_human_readable() -> None:
    assert _rich_verdict().to_dict() == {
        "ok": True,
        "run_id": "r",
        "digest": "d",
        "harness_version": "v1",
        "lane": "",
        "risk": "hollow",
        "intent": {"branch": "feat/x", "head_sha": "abc", "input_digest": "in", "generator": ""},
        "checks": [["00_build", "pass"], ["60_mutation", "noop"]],
        "evidence": [
            {
                "check": "00_build",
                "command": "python -m build",
                "exit_code": 0,
                "log": "/l/00.log",
                "log_bytes": 12,
                "content_sha256": "h0",
                "lane": "fast",
            },
            {
                "check": "60_mutation",
                "command": "mutmut run",
                "exit_code": 0,
                "log": "/l/60.log",
                "log_bytes": 0,
                "content_sha256": "h6",
                "lane": "heavy",
            },
        ],
    }


def test_rich_verdict_round_trips_through_file_and_history(tmp_path: Path) -> None:
    v = _rich_verdict()
    write_last_verdict(tmp_path, v)
    assert read_last_verdict(tmp_path) == v
    append_history(tmp_path, v)
    assert read_history(tmp_path) == [v]


def test_old_verdict_without_evidence_fields_parses_with_empty_defaults(tmp_path: Path) -> None:
    path = tmp_path / LAST_VERDICT_FILE
    path.parent.mkdir(parents=True)
    path.write_text('{"ok": true, "checks": [["a", "pass"]]}', encoding="utf-8")
    v = read_last_verdict(tmp_path)
    assert v == Verdict(ok=True, checks=(("a", "pass"),))
    assert v is not None
    # "" — NOT a re-derived band: an old record never claimed one, and saying "green"
    # for it would be an over-claim.
    assert v.risk == ""
    assert v.intent == Intent()
    assert v.evidence == ()


def test_malformed_evidence_and_intent_degrade_not_crash(tmp_path: Path) -> None:
    path = tmp_path / LAST_VERDICT_FILE
    path.parent.mkdir(parents=True)
    path.write_text(
        '{"ok": false, "risk": 3, "intent": "nope", "evidence": {"check": "x"}}',
        encoding="utf-8",
    )
    v = read_last_verdict(tmp_path)
    assert v is not None
    assert v.risk == "3"  # coerced to str, never raises
    assert v.intent == Intent()
    assert v.evidence == ()


def test_risk_band_is_derived_only_from_recorded_facts() -> None:
    # green: every check passed for real.
    assert risk_band((("a", "pass"), ("b", "pass"))) == "green"
    # hollow: at least one check inspected nothing (a green resting on less).
    assert risk_band((("a", "pass"), ("b", "noop"))) == "hollow"
    # red: anything failing — and red beats hollow (a failure is never softened).
    assert risk_band((("a", "noop"), ("b", "fail"))) == "red"
    assert risk_band((("a", "pass"), ("b", "missing"))) == "red"
    assert risk_band((("a", "pass"), ("b", "fail !tampered"))) == "red"
    # unknown statuses are failing (allowlist), so they band red too.
    assert risk_band((("a", "skipped"),)) == "red"


def test_risk_band_of_no_checks_is_hollow_not_green() -> None:
    # A run that inspected nothing at all cannot be "green".
    assert risk_band(()) == "hollow"


def test_risk_band_constants_are_the_only_bands() -> None:
    assert RISK_BANDS == ("green", "hollow", "red")


# --- rewrite-contract records (ADR-0059) ------------------------------------------------


def test_rewrite_record_appends_and_tallies_by_status(tmp_path: Path) -> None:
    for status in ("honoured", "honoured", "not_honoured", "exempt", "unknown"):
        append_rewrite_record(tmp_path, {"status": status, "prompt_hash": "h"})
    raw = (tmp_path / REWRITE_CONTRACT_FILE).read_text(encoding="utf-8")
    assert raw.count("\n") == 5 and raw.startswith('{"status": "honoured", "prompt_hash": "h"}\n')
    tally = read_rewrite_tally(tmp_path)
    assert tally == RewriteTally(honoured=2, not_honoured=1, exempt=1, unknown=1)
    assert (tally.judged, tally.total) == (3, 5)


def test_rewrite_tally_is_fail_soft_and_fail_closed(tmp_path: Path) -> None:
    assert read_rewrite_tally(tmp_path) == RewriteTally()
    path = tmp_path / REWRITE_CONTRACT_FILE
    path.parent.mkdir(parents=True)
    path.write_text(
        '{"status": "honoured"}\n\n{garbage\n[1]\n{"status": "forged"}\n{"no": "status"}\n',
        encoding="utf-8",
    )
    # malformed lines are skipped; an unrecognised or missing status is never "honoured"
    assert read_rewrite_tally(tmp_path) == RewriteTally(honoured=1, unknown=2)
    assert REWRITE_STATUSES == ("honoured", "not_honoured", "exempt", "unknown")


# --- self-report records (ADR-0066) ------------------------------------------------------


def test_self_report_record_appends_and_tallies_by_status(tmp_path: Path) -> None:
    for status in ("present", "present", "absent", "malformed", "graded", "exempt", "unknown"):
        append_self_report_record(tmp_path, {"status": status, "prompt_hash": "h"})
    raw = (tmp_path / SELF_REPORT_FILE).read_text(encoding="utf-8")
    assert raw.count("\n") == 7 and raw.startswith('{"status": "present", "prompt_hash": "h"}\n')
    tally = read_self_report_tally(tmp_path)
    assert tally == SelfReportTally(present=2, absent=1, malformed=1, graded=1, exempt=1, unknown=1)
    assert (tally.judged, tally.total) == (5, 7)
    assert SELF_REPORT_FILE == ".meta-harness/self_report.jsonl"


def test_self_report_tally_is_fail_soft_and_fail_closed(tmp_path: Path) -> None:
    assert read_self_report_tally(tmp_path) == SelfReportTally()
    path = tmp_path / SELF_REPORT_FILE
    path.parent.mkdir(parents=True)
    path.write_text(
        '{"status": "present"}\n\n{garbage\n[1]\n{"status": "honoured"}\n{"no": "status"}\n',
        encoding="utf-8",
    )
    # a rewrite-contract status is not a self-report status: never counted as present
    assert read_self_report_tally(tmp_path) == SelfReportTally(present=1, unknown=2)
    assert SELF_REPORT_STATUSES == ("present", "absent", "malformed", "graded", "exempt", "unknown")


# --- status_label: the gate-output row text, with a check's optional one-line summary ---
#
# Any check may write a `summary` field into its receipt (60_mutation writes the
# evaluated-mutant count + score). The gate prints it after the status so a reader
# never has to open the log to see whether the check did real work. Issue #187.


def test_status_label_without_summary_is_the_upper_status() -> None:
    assert status_label("pass", None) == "PASS"
    assert status_label("fail", "") == "FAIL"
    assert status_label("noop", "   ") == "NOOP"


def test_status_label_appends_summary_in_parentheses() -> None:
    assert status_label("pass", "evaluated 12, score 0.83") == "PASS (evaluated 12, score 0.83)"
    assert status_label("fail", "evaluated 0") == "FAIL (evaluated 0)"


def test_status_label_ignores_non_string_summary() -> None:
    # A receipt is JSON a check wrote; a malformed summary must not crash the verdict.
    assert status_label("pass", 42) == "PASS"
    assert status_label("pass", ["evaluated 3"]) == "PASS"


def test_status_label_keeps_the_row_to_one_bounded_line() -> None:
    # Only the first line survives, and an over-long summary is cut so the table stays readable.
    assert status_label("pass", "first line\nsecond line") == "PASS (first line)"
    long = "x" * 200
    label = status_label("pass", long)
    assert label.startswith("PASS (") and label.endswith("...)") and len(label) <= 100


# --- advisory_failures: failing checks outside the expected set (#229) --------------


def _receipt(run_dir: Path, name: str, body: object) -> None:
    (run_dir / f"{name}.json").write_text(json.dumps(body), encoding="utf-8")


def test_advisory_failures_names_failing_checks_outside_the_expected_set(tmp_path: Path) -> None:
    _receipt(tmp_path, "05_hygiene", {"check": "05_hygiene", "status": "fail"})  # expected
    _receipt(tmp_path, "06_git_identity", {"check": "06_git_identity", "status": "fail"})
    _receipt(tmp_path, "14_container", {"check": "14_container", "status": "error"})
    _receipt(tmp_path, "15_a11y", {"check": "15_a11y", "status": "noop"})
    _receipt(tmp_path, "16_shellcheck", {"check": "16_shellcheck", "status": "pass"})
    assert advisory_failures(tmp_path, ("05_hygiene",)) == (
        "06_git_identity (fail)",
        "14_container (error)",
    )


def test_advisory_failures_skips_anything_that_is_not_a_receipt(tmp_path: Path) -> None:
    """The run dir's JSON is untrusted: none of these may raise or be reported."""
    (tmp_path / "zz_list.json").write_text("[1, 2]", encoding="utf-8")
    (tmp_path / "zz_str.json").write_text('"text"', encoding="utf-8")
    (tmp_path / "zz_broken.json").write_text("{not json", encoding="utf-8")
    _receipt(tmp_path, "zz_nocheck", {"status": "fail"})
    _receipt(tmp_path, "zz_other", {"check": "someone_else", "status": "fail"})
    _receipt(tmp_path, "zz_badstatus", {"check": "zz_badstatus", "status": 17})
    assert advisory_failures(tmp_path, ()) == ()


def test_advisory_failures_of_an_empty_or_absent_run_dir_is_empty(tmp_path: Path) -> None:
    assert advisory_failures(tmp_path, ()) == ()
    assert advisory_failures(tmp_path / "missing", ()) == ()
