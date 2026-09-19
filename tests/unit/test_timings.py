"""Where a gate run's time went, read off the receipts it already writes (#253).

`40_test` timed out at 900s on dev and the bound was raised to 1800s to unblock the
queue. Nothing in the run said which check spent the time, so the only way to find out
was to re-run the suite locally with `--durations`. A bound that grows on no evidence
stops meaning anything; these are the pure functions the gate prints its own measurement
with. Threshold-free: they report, they never judge.
"""

from __future__ import annotations

import pytest

from meta_harness.timings import format_duration_ms, slowest, timings_line


@pytest.mark.parametrize(
    ("ms", "text"),
    [
        (0, "0.0s"),
        (7, "0.0s"),
        (940, "0.9s"),
        (1_500, "1.5s"),
        (59_949, "59.9s"),
        (60_000, "1m 00s"),
        (92_400, "1m 32s"),
        (3_600_000, "60m 00s"),
    ],
)
def test_a_duration_reads_as_a_human_reads_a_stopwatch(ms: int, text: str) -> None:
    assert format_duration_ms(ms) == text


def test_the_slowest_come_first_and_ties_keep_the_run_order() -> None:
    entries = (("05_hygiene", 10), ("40_test", 900), ("13_adr", 10), ("60_mutation", 500))

    assert slowest(entries, 3) == (("40_test", 900), ("60_mutation", 500), ("05_hygiene", 10))


def test_asking_for_more_than_there_are_returns_what_there_is() -> None:
    assert slowest((("40_test", 900),), 3) == (("40_test", 900),)


def test_a_check_with_no_recorded_duration_is_left_out_not_counted_as_instant() -> None:
    """A receipt from an older harness (or copied in by the worktree executor) carries no
    duration. Reading that as 0 would rank it fastest and quietly claim a measurement
    that was never made."""
    assert slowest((("40_test", 900), ("13_adr", None)), 3) == (("40_test", 900),)


def test_the_line_names_each_check_with_its_own_time() -> None:
    entries = (("40_test", 92_400), ("60_mutation", 1_500), ("13_adr", 10))

    assert timings_line(entries, 2) == "slowest: 40_test 1m 32s · 60_mutation 1.5s"


def test_nothing_measured_prints_no_line_rather_than_an_empty_claim() -> None:
    assert timings_line((), 3) is None
    assert timings_line((("13_adr", None),), 3) is None


def test_a_negative_duration_is_refused_rather_than_reported() -> None:
    """A clock that went backwards mid-run is a broken measurement, not a fast check."""
    with pytest.raises(ValueError, match="negative"):
        format_duration_ms(-1)
