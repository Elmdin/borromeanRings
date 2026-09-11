"""Unit tests for the generator loop's pure decision core (SPEC-generator.md §3.2)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from meta_harness.generator import (
    ACTION_ESCALATED,
    ACTION_GENERATOR_FAILED,
    ACTION_GREEN,
    ACTION_RETRY,
    ACTIONS,
    CAP,
    MAX_GENERATOR_LENGTH,
    evidence_writes,
    failing_check_ids,
    next_action,
    read_generator,
    snapshot_evidence,
)

# Exit codes a real generator can produce: clean, a crash, git-apply's refusal,
# the driver's timeout (124) and its untrusted-write code (125), and a shell that
# reports a signal as a negative code.
NONZERO_EXITS = (1, 2, 124, 125, 127, -1)


# --- the shared constants (pinned: two shell adapters read them) --------------


def test_cap_is_three_and_lives_here() -> None:
    """CAP is the one place both generator adapters read the retry bound from."""
    assert CAP == 3


def test_action_names_are_the_drivers_vocabulary() -> None:
    """The driver prints these verbatim, so the literals are part of the contract."""
    assert ACTION_GREEN == "green"
    assert ACTION_RETRY == "retry"
    assert ACTION_ESCALATED == "escalated"
    assert ACTION_GENERATOR_FAILED == "generator-failed"
    assert ACTIONS == (ACTION_GREEN, ACTION_RETRY, ACTION_ESCALATED, ACTION_GENERATOR_FAILED)


# --- next_action: N3/N4/N5 --------------------------------------------------


@pytest.mark.parametrize("exit_code", NONZERO_EXITS)
@pytest.mark.parametrize("gate_ok", [True, False])
@pytest.mark.parametrize("tree_changed", [True, False])
def test_nonzero_exit_is_generator_failed(
    exit_code: int, gate_ok: bool, tree_changed: bool
) -> None:
    """N4: the generator said it could not — nothing else it did can redeem that."""
    assert next_action(1, CAP, gate_ok, tree_changed, exit_code) == ACTION_GENERATOR_FAILED


@pytest.mark.parametrize("attempt", [1, 2, 3])
@pytest.mark.parametrize("gate_ok", [True, False])
def test_unchanged_tree_escalates_immediately(attempt: int, gate_ok: bool) -> None:
    """N4: exit 0 with nothing written means retrying is wasted attempts."""
    assert next_action(attempt, CAP, gate_ok, False, 0) == ACTION_ESCALATED


@pytest.mark.parametrize("attempt", [1, 2, 3, 4])
def test_green_whenever_the_gate_passes(attempt: int) -> None:
    """A green gate ends the loop at any attempt, including the last one."""
    assert next_action(attempt, CAP, True, True, 0) == ACTION_GREEN


@pytest.mark.parametrize("cap", [1, 2, 3, 4])
def test_retry_below_cap_and_escalate_at_it(cap: int) -> None:
    """N5: at most ``cap`` attempts, then the human — for every cap, not just 3."""
    for attempt in range(1, cap):
        assert next_action(attempt, cap, False, True, 0) == ACTION_RETRY
    for attempt in (cap, cap + 1):
        assert next_action(attempt, cap, False, True, 0) == ACTION_ESCALATED


@pytest.mark.parametrize(("attempt", "cap"), [(0, 3), (-1, 3), (1, 0), (1, -1), (0, 0)])
def test_out_of_range_counts_fail_closed(attempt: int, cap: int) -> None:
    """An impossible attempt/cap is an ambiguous state — never silently a pass."""
    with pytest.raises(ValueError, match="attempt and cap"):
        next_action(attempt, cap, True, True, 0)


def test_every_reachable_input_yields_a_known_action() -> None:
    """The decision is total over the inputs a driver can hand it."""
    for attempt in (1, 2, 3, 4):
        for cap in (1, 2, 3):
            for gate_ok in (True, False):
                for tree_changed in (True, False):
                    for exit_code in (0, *NONZERO_EXITS):
                        assert (
                            next_action(attempt, cap, gate_ok, tree_changed, exit_code) in ACTIONS
                        )


# --- N6: generator identity (provenance, never guessed) ----------------------


@pytest.mark.parametrize("raw", [None, "", "   ", "\t\n"])
def test_absent_generator_is_empty_never_guessed(raw: str | None) -> None:
    """Absent ⇒ ``""``. The gate never invents an author for a change."""
    assert read_generator(raw) == ""


def test_generator_identity_is_kept_verbatim() -> None:
    """The kind is self-declared: the gate stores it, it does not validate it."""
    assert read_generator("claude-code:abc-123") == "claude-code:abc-123"
    assert read_generator("  headless:apply_patch.sh  ") == "headless:apply_patch.sh"
    assert read_generator("anything at all") == "anything at all"


@pytest.mark.parametrize("raw", ["a\nb", "a\rb", "a\tb", "a\x00b", "a\x7fb", "\x1b[31m"])
def test_control_characters_are_rejected(raw: str) -> None:
    """A control character would corrupt the record it is written into."""
    assert read_generator(raw) == ""


def test_overlong_identity_is_truncated_at_the_documented_bound() -> None:
    """Provenance is a label, not a payload: bounded, exactly."""
    assert read_generator("x" * MAX_GENERATOR_LENGTH) == "x" * MAX_GENERATOR_LENGTH
    assert read_generator("x" * (MAX_GENERATOR_LENGTH + 1)) == "x" * MAX_GENERATOR_LENGTH
    assert MAX_GENERATOR_LENGTH == 128


# --- N2: the failing ids come from the verdict's rows ------------------------


def test_failing_ids_are_the_rows_the_verdict_failed() -> None:
    """Read off the verdict, not a summary string, so no name can be dropped."""
    rows = (
        ("00_build", "pass"),
        ("15_a11y", "noop"),
        ("20_lint", "fail"),
        ("30_typecheck", "missing"),
        ("40_test", "fail !tampered"),
    )
    assert failing_check_ids(rows) == ("20_lint", "30_typecheck", "40_test")


def test_no_failing_ids_when_every_row_passed() -> None:
    """A green verdict names nothing."""
    assert failing_check_ids((("00_build", "pass"), ("15_a11y", "noop"))) == ()


def test_failing_ids_of_nothing_is_nothing() -> None:
    """Fail-soft: an empty row set is not an error."""
    assert failing_check_ids(()) == ()


# --- conformance 5: the generator must not write under .meta-harness/ --------


def test_snapshot_of_a_missing_directory_is_empty(tmp_path: Path) -> None:
    """A project with no evidence area yet snapshots as nothing, not an error."""
    assert snapshot_evidence(tmp_path / "nope") == {}


def test_snapshot_records_size_and_mtime_of_every_file(tmp_path: Path) -> None:
    """The recorded value is what makes an in-place edit detectable."""
    (tmp_path / "sub").mkdir()
    target = tmp_path / "sub" / "a.txt"
    target.write_text("hello", encoding="utf-8")
    stat = target.stat()
    assert snapshot_evidence(tmp_path) == {
        os.path.join("sub", "a.txt"): f"{stat.st_size}:{stat.st_mtime_ns}"
    }


def test_snapshot_can_exclude_the_drivers_own_log(tmp_path: Path) -> None:
    """The driver writes the generator's log itself; that is not a violation.

    The excluded file is whichever the filesystem enumerates *first*, so skipping it must
    not end the scan — everything after it still has to be fingerprinted.
    """
    for name in ("own.log", "other.json", "third.txt"):
        (tmp_path / name).write_text(name, encoding="utf-8")
    first = next(iter(tmp_path.rglob("*")))
    rest = {path.name for path in tmp_path.rglob("*")} - {first.name}

    assert set(snapshot_evidence(tmp_path, exclude=first)) == rest


def test_a_file_that_cannot_be_stat_ed_drops_out_and_reads_as_a_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail-closed: evidence that became unreadable is reported, never ignored — and the
    one unreadable file is the first enumerated, so it must not hide the rest."""
    for name in ("counter", "other", "third"):
        (tmp_path / name).write_text("2", encoding="utf-8")
    before = snapshot_evidence(tmp_path)
    doomed = next(iter(tmp_path.rglob("*"))).name

    real_stat = Path.stat

    def _refuse(self: Path, *args: object, **kwargs: object) -> os.stat_result:
        if self.name == doomed:
            raise OSError("gone")
        return real_stat(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "stat", _refuse)
    assert evidence_writes(before, snapshot_evidence(tmp_path)) == (f"removed: {doomed}",)


def test_evidence_writes_names_additions_removals_and_edits() -> None:
    """Every way a generator can touch the gate's evidence area is reported."""
    before = {"keep": "1:1", "gone": "2:2", "edited": "3:3"}
    after = {"keep": "1:1", "edited": "3:4", "new": "5:5"}
    assert evidence_writes(before, after) == (
        "modified: edited",
        "removed: gone",
        "added: new",
    )


def test_evidence_writes_is_silent_when_nothing_moved() -> None:
    """A well-behaved generator produces no report at all."""
    snapshot = {"a": "1:1", "b": "2:2"}
    assert evidence_writes(snapshot, dict(snapshot)) == ()


def test_an_in_place_edit_of_the_same_size_is_still_caught(tmp_path: Path) -> None:
    """Resetting a counter file in place changes no size — the mtime catches it."""
    counter = tmp_path / "counter"
    counter.write_text("2", encoding="utf-8")
    before = snapshot_evidence(tmp_path)
    counter.write_text("0", encoding="utf-8")
    os.utime(counter, ns=(0, 0))  # force a distinct mtime, no sleep, no flake
    assert evidence_writes(before, snapshot_evidence(tmp_path)) == ("modified: counter",)
