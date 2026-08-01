"""Mutation testing — parse mutmut's result counts and compute a score.

Mutation testing measures *oracle/assertion strength*, not mere execution:
coverage tells you a line ran; mutation tells you a test would have **caught** a
change to it. This is borromeanRings's answer to the coverage-Goodhart trap (a
100%-coverage suite with vacuous assertions kills no mutants). The score feeds
the T1 :mod:`meta_harness.ratchet` so it may not regress. Run as a CI-tier heavy
check (mutation runs the suite once per mutant — too slow for the inner gate);
see checks/ci/60_mutation.sh and ADR-0022.

Only the parsing + score math live here (deterministic, unit-tested); invoking
mutmut is the shell check's job (the tool is a module secret).
"""

import re
from dataclasses import dataclass

# mutmut 3.x renders a progress/summary line with emoji category counters, e.g.
#   "… 3/3  🎉 2 🫥 0  ⏰ 0  🤔 0  🙁 1  🔇 0  🧙 0"
# Emojis are matched by escape (source stays ASCII, robust to encoding). The line
# is rewritten in place during the run, so the FINAL value of each counter is the
# last match. Legend below is per mutmut's own key.
_KILLED = "\U0001f389"  # 🎉 caught (test failed on the mutant — good)
_SURVIVED = "\U0001f641"  # 🙁 survived (no test caught it — a gap)
_TIMEOUT = "\U000023f0"  # ⏰ mutant caused a timeout (counted as caught)
_SUSPICIOUS = "\U0001f914"  # 🤔 suspicious (ambiguous — counted as NOT caught)
_SKIPPED = "\U0001f507"  # 🔇 skipped
_NO_TESTS = "\U0001fae5"  # 🫥 no tests covered the line


@dataclass(frozen=True)
class MutationCounts:
    """The mutant tallies mutmut reports for a run."""

    killed: int
    survived: int
    timeout: int
    suspicious: int
    skipped: int
    no_tests: int


def _last_count(text: str, emoji: str) -> int:
    """The final value of ``emoji <n>`` in mutmut's rewritten progress line."""
    matches = re.findall(rf"{emoji}\s*(\d+)", text)
    return int(matches[-1]) if matches else 0


def parse_mutmut_summary(text: str) -> MutationCounts:
    """Parse mutmut 3.x summary/progress output into :class:`MutationCounts`."""
    return MutationCounts(
        killed=_last_count(text, _KILLED),
        survived=_last_count(text, _SURVIVED),
        timeout=_last_count(text, _TIMEOUT),
        suspicious=_last_count(text, _SUSPICIOUS),
        skipped=_last_count(text, _SKIPPED),
        no_tests=_last_count(text, _NO_TESTS),
    )


def total_evaluated(counts: MutationCounts) -> int:
    """Mutants mutmut actually evaluated (caught + escaped).

    Zero means mutmut produced no verdicts — a *setup failure* (e.g. the clean
    test run failed), NOT a perfect suite. The check must fail closed on zero
    rather than trust the vacuous 1.0 score. See checks/ci/60_mutation.sh.
    """
    return counts.killed + counts.survived + counts.timeout + counts.suspicious


def mutation_score(counts: MutationCounts) -> float:
    """Fraction of *evaluated* mutants the suite caught (higher is better).

    caught = killed + timeout; escaped = survived + suspicious. Skipped and
    no-tests mutants are excluded from the denominator (they were not evaluated).
    A run with no evaluated mutants scores 1.0 (nothing escaped) — vacuous but
    safe for the ratchet (matches the empty-gold convention in recall).
    """
    caught = counts.killed + counts.timeout
    escaped = counts.survived + counts.suspicious
    denominator = caught + escaped
    return caught / denominator if denominator else 1.0
