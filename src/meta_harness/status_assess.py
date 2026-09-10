"""Project-status assessment & presentation — the pure core of the roster view.

Given already-gathered facts about one governed project, decide its health row
(:func:`build_status`) and render a roster of rows as a table (:func:`render`,
:func:`summarize`). Kept free of filesystem/process I/O so it is fully unit-testable;
:mod:`meta_harness.status` does the git/fs reads and calls in here.

It reuses the single sources of truth for the two things it judges: adoption drift via
``plan_adoption``/``RECOMMENDED`` (:mod:`meta_harness.adopt`) and the last gate outcome
via the persisted :class:`~meta_harness.verdict.Verdict`. See docs/specs/SPEC-status.md
and ADR-0046.

It serves BOTH scopes, because they are one responsibility at two granularities: the
roster view across projects, and the **self-status** view of a single project — is
borromeanRings governing me, is enforcement actually on, and was that green real? The
latter is the default report (ADR-0049); see docs/specs/SPEC-self-status.md.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from meta_harness.adopt import plan_adoption
from meta_harness.verdict import (
    RewriteTally,
    SelfReportTally,
    Verdict,
    is_failing,
    read_last_verdict,
    read_rewrite_tally,
    read_self_report_tally,
)

__all__ = [
    "HOOK_EVENTS",
    "HOOK_SCRIPTS",
    "NOOP",
    "Enforcement",
    "ProjectStatus",
    "RewriteTally",
    "SelfReportTally",
    "Verdict",
    "build_status",
    "classify_enforcement",
    "hollow_checks",
    "obligations",
    "read_project_verdict",
    "read_rewrite_tally",
    "read_self_report_tally",
    "render",
    "render_rewrite_line",
    "render_self_report_line",
    "render_self_status",
    "summarize",
]


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
        # Uses the gate's own classifier: a check that merely inspected nothing ("noop")
        # is not a failure, and listing it as one would bury the check that actually broke.
        failed = [cid for cid, st in last_verdict.checks if is_failing(st)]
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


# --- single-project self-status (ADR-0049) ------------------------------------

#: The Claude Code hook events borromeanRings wires to govern a project automatically,
#: each mapped to the hook script it installs.
#:
#: Detection keys off the SCRIPT NAME, not the path: a referenced install spells the
#: command with an absolute ``$BORROMEANRINGS_HOME``, while a repo that governs itself
#: (borromeanRings's own) spells it ``${CLAUDE_PROJECT_DIR}``. Both are enforcement;
#: matching on a path would silently misreport the self-governing case as unenforced.
HOOK_SCRIPTS: dict[str, str] = {
    "UserPromptSubmit": "prompt_rewrite.sh",
    "Stop": "stop_gate.sh",
    "PostToolUse": "post_edit_format.sh",
    "PreToolUse": "pre_bash_guard.sh",
    # Compaction is where governance state is silently lost (#137, ADR-0053): the
    # snapshot before, and the re-injection after, are part of enforcement.
    "PreCompact": "pre_compact.sh",
    "SessionStart": "session_start.sh",
}

#: The hook events borromeanRings wires; all present ⇒ enforcement is automatic.
HOOK_EVENTS: tuple[str, ...] = tuple(HOOK_SCRIPTS)

#: Status a check reports when it ran but had nothing to inspect (see ADR-0049).
NOOP = "noop"


@dataclass(frozen=True)
class Enforcement:
    """Whether the gate runs automatically here, and the evidence for that answer."""

    mode: str
    detail: str


def _wired_events(hooks: Any) -> list[str]:
    """Hook events wired to a borromeanRings hook script (fail-soft on any shape)."""
    if not isinstance(hooks, Mapping):
        return []
    wired: list[str] = []
    for event, script in HOOK_SCRIPTS.items():
        entries = hooks.get(event)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            inner = entry.get("hooks")
            if not isinstance(inner, list):
                continue
            if any(
                isinstance(hook, Mapping) and script in str(hook.get("command", ""))
                for hook in inner
            ):
                wired.append(event)
                break
    return wired


def classify_enforcement(settings: Mapping[str, Any] | None, harness_home: str) -> Enforcement:
    """Decide whether this project's own settings put the gate on automatic.

    ``settings`` is the parsed ``.claude/settings.json`` (``None`` when absent). Hooks
    parked under a renamed key — the usual way enforcement gets switched off — are
    reported as *disabled* rather than *absent*, because the two call for different
    responses: one is a decision someone made, the other is a project never set up.
    """
    if settings is None:
        return Enforcement("manual", "no .claude/settings.json — the gate runs only when invoked")

    wired = _wired_events(settings.get("hooks"))
    total = len(HOOK_EVENTS)
    if len(wired) == total:
        return Enforcement("auto", f"{total}/{total} hooks wired to this borromeanRings")
    if wired:
        return Enforcement(
            "partial",
            f"{len(wired)}/{total} hooks wired ({', '.join(wired)}) — enforcement is incomplete",
        )

    parked = [
        key
        for key, value in settings.items()
        if key != "hooks" and "hook" in key.lower() and _wired_events(value)
    ]
    if parked:
        return Enforcement(
            "manual",
            f"hooks present but DISABLED (parked under '{parked[0]}') — nothing auto-gates",
        )
    return Enforcement("manual", "no borromeanRings hooks wired — the gate runs only when invoked")


def obligations(verdict: Verdict | None) -> list[str]:
    """What the last verdict still demands: failing checks first, then hollow ones.

    The wording is what the compaction brief re-injects (ADR-0053); an empty list means
    a clean pass, or no verdict at all — the caller says which.
    """
    if verdict is None:
        return []
    failing = [
        f"{cid}: {status.upper()} — fix before the next Stop gate"
        for cid, status in verdict.checks
        if is_failing(status)
    ]
    hollow = [
        f"{cid}: inspected nothing (noop) — a green here proves less than it looks"
        for cid, status in verdict.checks
        if status == NOOP
    ]
    return failing + hollow


def hollow_checks(verdict: Verdict | None) -> tuple[str, ...]:
    """The checks in ``verdict`` that ran but inspected nothing."""
    if verdict is None:
        return ()
    return tuple(cid for cid, status in verdict.checks if status == NOOP)


def render_rewrite_line(tally: RewriteTally | None) -> str:
    """The rewrite-contract line of the self-status report (ADR-0059).

    How often replies opened with the reading the UserPromptSubmit directive asks for.
    A statement about the RECORD: exempt and unknown verdicts are shown as such, never
    folded into either side of the tally.
    """
    if tally is None or tally.total == 0:
        return "no record"
    line = f"honoured {tally.honoured} of {tally.judged} in this project"
    aside = [f"{tally.exempt} exempt"] if tally.exempt else []
    if tally.unknown:
        aside.append(f"{tally.unknown} unknown")
    return f"{line} ({', '.join(aside)})" if aside else line


def render_self_report_line(tally: SelfReportTally | None) -> str:
    """The self-report line of the self-status report (ADR-0066).

    How often replies ended with the structural VERIFICATION STATUS block. A statement
    about the RECORD: malformed, graded, exempt and unknown verdicts are shown as such.
    """
    if tally is None or tally.total == 0:
        return "no record"
    line = f"present {tally.present} of {tally.judged}"
    aside = [
        f"{count} {name}"
        for name, count in (
            ("malformed", tally.malformed),
            ("graded", tally.graded),
            ("exempt", tally.exempt),
            ("unknown", tally.unknown),
        )
        if count
    ]
    return f"{line} ({', '.join(aside)})" if aside else line


def render_self_status(
    *,
    project: str,
    governed: bool,
    required: Sequence[str],
    last_verdict: Verdict | None,
    enforcement: Enforcement,
    harness_home: str,
    installed_version: str = "",
    rewrite_tally: RewriteTally | None = None,
    self_report_tally: SelfReportTally | None = None,
) -> str:
    """Render the one-project report (pure; safe on missing/partial facts)."""
    name = project.rstrip("/").rsplit("/", maxsplit=1)[-1] or project
    lines = [
        "",
        f"  borromeanRings status — {name}   (this project only)",
        f"  {'-' * 60}",
    ]
    if not governed:
        lines += [
            f"  NOT GOVERNED — no borromeanrings.toml in {project}",
            f"  Adopt it:     {harness_home}/init.sh {project}",
            "",
        ]
        return "\n".join(lines)

    lines.append(f"  Governed:     yes · {len(required)} required check(s)")

    if last_verdict is None:
        lines.append("  Last verdict: never gated here")
    else:
        version = last_verdict.harness_version or "unknown"
        lines.append(
            f"  Last verdict: {'PASS' if last_verdict.ok else 'FAIL'}"
            f"{f' · run {last_verdict.run_id}' if last_verdict.run_id else ''}"
            f" · by borromeanRings {version}"
        )
        hollow = hollow_checks(last_verdict)
        if hollow:
            lines += [
                f"  ⚠ Hollow:     {len(hollow)} of {len(last_verdict.checks)} checks"
                " inspected NOTHING —",
                f"                {', '.join(hollow)}",
                "                a green resting on these proves less than it looks like.",
            ]
        elif last_verdict.checks:
            # Deliberately a statement about the RECORD, not a claim about reality: a
            # verdict written before `noop` existed could not report hollowness, so
            # "no hollow checks recorded" is all this evidence can honestly support.
            # Claiming "all checks did real work" from it would be the very over-claim
            # this report exists to expose (ADR-0049).
            lines.append(
                f"  Reality:      0 of {len(last_verdict.checks)} checks recorded as"
                " inspecting nothing"
            )

    marker = {"auto": "", "partial": "⚠ ", "manual": "⚠ "}[enforcement.mode]
    lines.append(f"  {marker}Enforcement: {enforcement.mode.upper()} — {enforcement.detail}")
    lines.append(f"  Rewrite:      contract {render_rewrite_line(rewrite_tally)}")
    lines.append(f"  Self-report:  {render_self_report_line(self_report_tally)}")
    if installed_version:
        lines.append(f"  Installed:    borromeanRings {installed_version} at {harness_home}")
    lines += [f"  Re-gate:      {harness_home}/verify.sh", ""]
    return "\n".join(lines)
