"""Effectiveness ledger — did governing this project actually catch anything, over time?

`status` answers "is it green *now*"; the ledger answers "has the gate *done anything*"
by summarising each project's append-only verdict history (:data:`~meta_harness.verdict.
VERDICT_HISTORY_FILE`, written by ``verify.sh`` every run): how many times it ran, how
many of those runs it **caught a failure** (the evidence the gate is load-bearing, not
decorative), and the current pass/fail streak. A project with many runs and zero
failures ever is either genuinely clean or under-tested; one that has caught failures is
demonstrably doing work. Threshold-free — counts and a streak, no score.

Pure summary (:func:`summarize_history`) + rendering, with the filesystem walk delegated
to :func:`~meta_harness.status.discover_projects`. See docs/specs/SPEC-ledger.md and
ADR-0047.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from meta_harness.status import discover_projects
from meta_harness.verdict import Verdict, read_history


@dataclass(frozen=True)
class LedgerSummary:
    """One project's gate history distilled: runs, failures caught, current streak."""

    path: str
    runs: int
    failures_caught: int
    current_streak: int
    streak_kind: str  # "green" | "red" | "none"


def summarize_history(path: str, history: Sequence[Verdict]) -> LedgerSummary:
    """Distil a project's verdict history into run/failure/streak counts (pure)."""
    runs = len(history)
    failures = sum(1 for v in history if not v.ok)
    streak = 0
    kind = "none"
    if history:
        latest = history[-1].ok
        kind = "green" if latest else "red"
        for verdict in reversed(history):
            if verdict.ok != latest:
                break
            streak += 1
    return LedgerSummary(path, runs, failures, streak, kind)


def _short(path: str) -> str:
    home = str(Path.home())
    return "~" + path[len(home) :] if path.startswith(home) else path


def render(summaries: Sequence[LedgerSummary]) -> str:
    """Render the ledger as an aligned table."""
    if not summaries:
        return "no governed projects with recorded history."
    header = f"{'PROJECT':<42} {'RUNS':<5} {'CAUGHT':<7} {'STREAK':<8}"
    lines = [header, "-" * len(header)]
    for s in summaries:
        streak = f"{s.current_streak} {s.streak_kind}" if s.runs else "—"
        lines.append(f"{_short(s.path):<42} {s.runs:<5} {s.failures_caught:<7} {streak:<8}")
    return "\n".join(lines)


def summarize(summaries: Sequence[LedgerSummary]) -> str:
    """A one-line tally across the portfolio's recorded history."""
    gated = sum(1 for s in summaries if s.runs)
    total_runs = sum(s.runs for s in summaries)
    total_caught = sum(s.failures_caught for s in summaries)
    return (
        f"{len(summaries)} governed · {gated} with history · "
        f"{total_runs} gate runs · {total_caught} failures caught"
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint: render the effectiveness ledger for the discovered projects.

    Positional args are roots to scan (default: the user's home). Read-only; exits 0.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    roots = [a for a in args if not a.startswith("--")] or [str(Path.home())]
    summaries = [
        summarize_history(str(project), read_history(project))
        for project in discover_projects(roots)
    ]
    print(render(summaries))
    print(summarize(summaries))
    return 0
