"""Project-status assessment & presentation — the pure core of the roster view.

Given already-gathered facts about one governed project, decide its health row
(:func:`build_status`) and render a roster of rows as a table (:func:`render`,
:func:`summarize`). Kept free of filesystem/process I/O so it is fully unit-testable;
:mod:`meta_harness.status` does the git/fs reads and calls in here.

It reuses the single sources of truth for the two things it judges: adoption drift via
``plan_adoption``/``RECOMMENDED`` (:mod:`meta_harness.adopt`) and the last gate outcome
via the persisted :class:`~meta_harness.verdict.Verdict`. See docs/specs/SPEC-status.md
and ADR-0046.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from meta_harness.adopt import plan_adoption
from meta_harness.verdict import Verdict, read_last_verdict


@dataclass(frozen=True)
class ProjectStatus:
    """One governed project's health row for the roster view."""

    path: str
    is_git: bool
    config_dirty: bool
    required_count: int
    verdict: str  # "pass" | "fail" | "never"
    missing_recommended: tuple[str, ...]
    note: str


def build_status(
    path: str,
    *,
    is_git: bool,
    config_dirty: bool,
    required: Sequence[str],
    has_changelog: bool,
    last_verdict: Verdict | None,
) -> ProjectStatus:
    """Assemble a :class:`ProjectStatus` from already-gathered facts (pure)."""
    verdict = "never" if last_verdict is None else ("pass" if last_verdict.ok else "fail")
    missing = plan_adoption(tuple(required), has_changelog=has_changelog).add_checks
    notes: list[str] = []
    if not is_git:
        notes.append("not a git repo")
    elif config_dirty:
        notes.append("config uncommitted")
    if verdict == "fail" and last_verdict is not None:
        # Name the failing checks so a red row is diagnosable without a manual cd.
        failed = [cid for cid, st in last_verdict.checks if st != "pass"]
        if failed:
            notes.append("failed: " + ", ".join(failed))
    if missing:
        notes.append(f"drift: +{len(missing)}")
    return ProjectStatus(
        path=path,
        is_git=is_git,
        config_dirty=config_dirty,
        required_count=len(required),
        verdict=verdict,
        missing_recommended=missing,
        note="; ".join(notes),
    )


def read_project_verdict(project_root: Path | str) -> Verdict | None:
    """The project's last recorded gate verdict, or ``None`` if never gated/unreadable."""
    return read_last_verdict(project_root)


def _short(path: str) -> str:
    home = str(Path.home())
    return "~" + path[len(home) :] if path.startswith(home) else path


def render(statuses: Sequence[ProjectStatus]) -> str:
    """Render the roster as an aligned text table."""
    if not statuses:
        return "no governed projects found."
    header = f"{'PROJECT':<42} {'GIT':<4} {'REQ':<4} {'VERDICT':<8} NOTES"
    lines = [header, "-" * len(header)]
    for s in statuses:
        git = "yes" if s.is_git else "NO"
        lines.append(f"{_short(s.path):<42} {git:<4} {s.required_count:<4} {s.verdict:<8} {s.note}")
    return "\n".join(lines)


def summarize(statuses: Sequence[ProjectStatus]) -> str:
    """A one-line tally of the roster's health."""
    total = len(statuses)
    green = sum(1 for s in statuses if s.verdict == "pass")
    failing = sum(1 for s in statuses if s.verdict == "fail")
    never = sum(1 for s in statuses if s.verdict == "never")
    drifted = sum(1 for s in statuses if s.missing_recommended)
    non_git = sum(1 for s in statuses if not s.is_git)
    return (
        f"{total} governed · {green} green · {failing} failing · "
        f"{never} never-gated · {drifted} drifted · {non_git} non-git"
    )
