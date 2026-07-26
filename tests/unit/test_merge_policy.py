"""Truth-table tests for the merge policy (docs/specs/SPEC-merge.md §5).

The invariant: allow a merge only when it is explicitly requested AND the gate
passed; deny otherwise. Covers both branches of :func:`decide_merge`.
"""

from meta_harness.merge_policy import decide_merge


def test_allows_when_requested_and_gate_passed() -> None:
    decision = decide_merge(gate_passed=True, explicitly_requested=True)
    assert decision.allowed is True


def test_denies_when_not_explicitly_requested() -> None:
    decision = decide_merge(gate_passed=True, explicitly_requested=False)
    assert decision.allowed is False
    assert "explicitly requested" in decision.reason


def test_denies_when_gate_failed() -> None:
    decision = decide_merge(gate_passed=False, explicitly_requested=True)
    assert decision.allowed is False
    assert "gate did not pass" in decision.reason


def test_denies_when_neither() -> None:
    decision = decide_merge(gate_passed=False, explicitly_requested=False)
    assert decision.allowed is False
