"""Behavioral tests for :func:`meta_harness.sample.overall_status`.

Boundary/equivalence cases per TEST-PLAN.md: all-pass, a single failure, and
the empty (fail-closed) case — covering both branches of the aggregation.
"""

from meta_harness.sample import overall_status


def test_all_pass() -> None:
    assert overall_status(["pass", "pass", "pass"]) == "pass"


def test_single_failure_fails_the_aggregate() -> None:
    assert overall_status(["pass", "fail", "pass"]) == "fail"


def test_non_pass_status_fails() -> None:
    assert overall_status(["pass", "error"]) == "fail"


def test_empty_input_fails_closed() -> None:
    assert overall_status([]) == "fail"
