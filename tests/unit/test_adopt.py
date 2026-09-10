"""Unit tests for the adoption planner (meta_harness.adopt)."""

from __future__ import annotations

import pytest

from meta_harness.adopt import (
    RATCHET_BASELINES,
    RECOMMENDED,
    plan_adoption,
    rewrite_required,
)

BASELINE_7 = (
    "00_build",
    "05_hygiene",
    "10_format",
    "20_lint",
    "30_typecheck",
    "40_test",
    "50_security",
)


def test_plan_adds_all_recommended_to_a_baseline_project() -> None:
    plan = plan_adoption(BASELINE_7, has_changelog=False)
    assert plan.add_checks == RECOMMENDED
    # existing order preserved, additions appended
    assert plan.new_required == BASELINE_7 + RECOMMENDED
    # ratchets among the additions are the ones to seed
    assert set(plan.seed_baselines) == set(RATCHET_BASELINES)
    assert plan.needs_changelog is True


def test_plan_is_idempotent_when_already_adopted() -> None:
    already = BASELINE_7 + RECOMMENDED
    plan = plan_adoption(already, has_changelog=True)
    assert plan.add_checks == ()
    assert plan.seed_baselines == ()
    assert plan.needs_changelog is False
    assert plan.new_required == already


def test_plan_skips_changelog_when_one_exists() -> None:
    plan = plan_adoption(BASELINE_7, has_changelog=True)
    assert "11_changelog" in plan.add_checks
    assert plan.needs_changelog is False


def test_plan_does_not_reseed_a_ratchet_already_required() -> None:
    current = (*BASELINE_7, "32_complexity")
    plan = plan_adoption(current, has_changelog=True)
    assert "32_complexity" not in plan.add_checks
    assert "32_complexity" not in plan.seed_baselines


def test_rewrite_required_single_line_preserves_other_text() -> None:
    text = '[checks]\nrequired = ["00_build", "40_test"]\n\n[context]\naccount = "demo"\n'
    out = rewrite_required(text, ("00_build", "40_test", "12_secrets"))
    assert 'required = ["00_build", "40_test", "12_secrets"]' in out
    # unrelated table untouched
    assert '[context]\naccount = "demo"' in out


def test_rewrite_required_multiline_array() -> None:
    text = "[checks]\nrequired = [\n  '00_build',\n  '40_test',\n]\n\n[context]\n"
    out = rewrite_required(text, ("00_build", "40_test", "45_docstrings"))
    assert 'required = ["00_build", "40_test", "45_docstrings"]' in out
    assert "[context]" in out


def test_rewrite_required_is_scoped_to_checks_table() -> None:
    # A 'required' key under another table must not be rewritten.
    text = '[hygiene]\nrequired = ["README.md"]\n\n[checks]\nrequired = ["40_test"]\n'
    out = rewrite_required(text, ("40_test", "12_secrets"))
    assert 'required = ["README.md"]' in out  # hygiene untouched
    assert 'required = ["40_test", "12_secrets"]' in out


def test_rewrite_required_raises_without_checks_table() -> None:
    with pytest.raises(ValueError, match="no .checks. table"):
        rewrite_required('[context]\nfoo = "bar"\n', ("40_test",))


def test_rewrite_required_raises_without_required_array() -> None:
    with pytest.raises(ValueError, match="no required array"):
        rewrite_required('[checks]\nheavy = ["60_mutation"]\n', ("40_test",))


def test_coverage_seed_takes_the_latest_receipt_with_a_number() -> None:
    from meta_harness.adopt import coverage_seed

    receipts = (
        {"check": "40_test", "coverage_percent": 71.5},
        {"check": "40_test", "status": "noop"},  # a hollow run carries no number
        {"check": "40_test", "coverage_percent": 80.25},
    )
    assert coverage_seed(receipts) == "80.25"


def test_coverage_seed_is_none_without_a_measured_run() -> None:
    from meta_harness.adopt import coverage_seed

    assert coverage_seed(()) is None
    assert coverage_seed(({"check": "40_test", "status": "noop"},)) is None
    assert coverage_seed(({"check": "40_test", "coverage_percent": "n/a"},)) is None
