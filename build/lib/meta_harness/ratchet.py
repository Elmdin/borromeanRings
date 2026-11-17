"""The non-regression **ratchet** — borromeanRings's T1 enforcement primitive.

A ratchet admits improvement and holds the line against regression: a metric may
not move past a recorded baseline (no arbitrary target — a *meaningful non-
regression* signal, per project policy). It is the single mechanism shared by
every T1 check (coverage, mutation score, complexity, duplication, …), so the
"how do we ratchet" decision lives in exactly one place (CS130 Single Choice /
DRY). See docs/ENFORCEMENT-COVERAGE.md §1.

``higher_is_better`` selects direction: coverage/mutation-score ratchet *up*
(a drop is a regression); complexity/duplication ratchet *down* (a rise is a
regression). ``epsilon`` absorbs float-representation noise so only a real move
fails.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RatchetDecision:
    """Outcome of a non-regression check against a recorded baseline."""

    passed: bool
    regressed: bool
    current: float
    baseline: float


def decide_ratchet(
    current: float,
    baseline: float,
    *,
    higher_is_better: bool = True,
    epsilon: float = 1e-9,
) -> RatchetDecision:
    """Decide whether ``current`` regresses against ``baseline`` (fail-closed).

    For ``higher_is_better`` metrics a drop below baseline regresses; otherwise a
    rise above baseline regresses. Equality (within ``epsilon``) always passes.
    """
    regressed = current + epsilon < baseline if higher_is_better else current - epsilon > baseline
    return RatchetDecision(
        passed=not regressed, regressed=regressed, current=current, baseline=baseline
    )
