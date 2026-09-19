"""Tests for the T1 ratchet primitive and mutation-score parsing.

The ratchet is the single non-regression mechanism shared by every T1 check; the
mutation parser turns mutmut's output into a score for it. See
docs/ENFORCEMENT-COVERAGE.md and ADR-0022.
"""

from meta_harness.mutation import (
    MutationCounts,
    mutation_score,
    parse_mutmut_summary,
    summary_line,
    total_evaluated,
)
from meta_harness.ratchet import RatchetDecision, decide_ratchet

# A real mutmut 3.6 progress line (rewritten in place → counters repeat; the
# FINAL 3/3 tally is killed=2, survived=1). Captured from a live run.
_REAL_SUMMARY = (
    "⠇ 0/3  \U0001f389 0 \U0001fae5 0  \U000023f0 0  \U0001f914 0  "
    "\U0001f641 0  \U0001f507 0  \U0001f9d9 0"
    "⠋ 3/3  \U0001f389 2 \U0001fae5 0  \U000023f0 0  \U0001f914 0  "
    "\U0001f641 1  \U0001f507 0  \U0001f9d9 0"
)


# --- ratchet: higher-is-better (coverage, mutation score) ---


def test_ratchet_passes_when_equal() -> None:
    assert decide_ratchet(0.80, 0.80) == RatchetDecision(True, False, 0.80, 0.80)


def test_ratchet_passes_on_improvement() -> None:
    assert decide_ratchet(0.90, 0.80).passed is True


def test_ratchet_fails_closed_on_drop() -> None:
    decision = decide_ratchet(0.70, 0.80)
    assert decision.passed is False and decision.regressed is True


def test_ratchet_epsilon_absorbs_float_noise() -> None:
    assert decide_ratchet(0.80 - 1e-12, 0.80).passed is True


# --- ratchet: lower-is-better (complexity, duplication) ---


def test_ratchet_lower_is_better_fails_on_rise() -> None:
    # complexity going UP is a regression when lower is better.
    assert decide_ratchet(12.0, 10.0, higher_is_better=False).regressed is True


def test_ratchet_lower_is_better_passes_on_drop() -> None:
    assert decide_ratchet(8.0, 10.0, higher_is_better=False).passed is True


# --- mutation: parse real mutmut output + score ---


def test_parse_mutmut_takes_final_counters() -> None:
    counts = parse_mutmut_summary(_REAL_SUMMARY)
    assert counts.killed == 2  # last 🎉 value, not the earlier 0
    assert counts.survived == 1  # last 🙁 value


def test_parse_mutmut_empty_output_is_all_zero() -> None:
    counts = parse_mutmut_summary("no counters here")
    assert counts == MutationCounts(0, 0, 0, 0, 0, 0)


def test_mutation_score_from_real_run() -> None:
    # killed 2, survived 1 → caught 2 / evaluated 3.
    assert mutation_score(parse_mutmut_summary(_REAL_SUMMARY)) == 2 / 3


def test_mutation_score_counts_timeout_as_caught() -> None:
    counts = MutationCounts(killed=1, survived=1, timeout=1, suspicious=0, skipped=0, no_tests=0)
    assert mutation_score(counts) == 2 / 3  # (1 killed + 1 timeout) / 3 evaluated


def test_mutation_score_suspicious_counts_as_escaped() -> None:
    counts = MutationCounts(killed=1, survived=0, timeout=0, suspicious=1, skipped=0, no_tests=0)
    assert mutation_score(counts) == 0.5  # suspicious is NOT a clean kill


def test_mutation_score_excludes_skipped_and_no_tests() -> None:
    counts = MutationCounts(killed=2, survived=0, timeout=0, suspicious=0, skipped=5, no_tests=9)
    assert mutation_score(counts) == 1.0  # only evaluated mutants count


def test_mutation_score_no_evaluated_mutants_is_vacuously_one() -> None:
    assert mutation_score(MutationCounts(0, 0, 0, 0, 3, 4)) == 1.0


def test_total_evaluated_counts_caught_and_escaped_only() -> None:
    assert total_evaluated(parse_mutmut_summary(_REAL_SUMMARY)) == 3  # 2 killed + 1 survived
    assert total_evaluated(MutationCounts(1, 1, 1, 1, 9, 9)) == 4  # skipped/no_tests excluded


def test_total_evaluated_zero_signals_setup_failure() -> None:
    # The false-pass guard: no verdicts (only skipped/no-tests) → the check must fail closed.
    assert total_evaluated(MutationCounts(0, 0, 0, 0, 5, 5)) == 0


# --- mutation: the one-line receipt summary the gate prints on the 60_mutation row ---
#
# A score with no count is unreadable (a vacuous run scores 1.0); the count is what
# tells a reader whether mutmut did any work. See ADR-0022, issue #187.


def test_summary_line_carries_count_and_score() -> None:
    counts = parse_mutmut_summary(_REAL_SUMMARY)  # 2 killed + 1 survived
    assert summary_line(counts, decide_ratchet(2 / 3, 0.5, higher_is_better=True)) == (
        "evaluated 3, score 0.67"
    )


def test_summary_line_zero_evaluated_names_the_count_not_a_vacuous_score() -> None:
    counts = MutationCounts(0, 0, 0, 0, skipped=3, no_tests=4)
    decision = decide_ratchet(mutation_score(counts), 0.8, higher_is_better=True)
    assert summary_line(counts, decision) == "evaluated 0"


def test_summary_line_shows_the_baseline_on_regression() -> None:
    counts = MutationCounts(killed=1, survived=1, timeout=0, suspicious=0, skipped=0, no_tests=0)
    decision = decide_ratchet(0.5, 0.8, higher_is_better=True)
    assert decision.regressed
    assert summary_line(counts, decision) == "evaluated 2, score 0.50 < baseline 0.80"
