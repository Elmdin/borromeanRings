"""The compaction brief — governance state that must survive context summarisation.

When Claude Code compacts a session, everything the model knew about the last gate
verdict, the obligations still open (a failing ADR or prior-art check, a hollow green),
the enforcement mode and the commit-identity policy is folded into a summary that may
or may not keep it. That is the hollow-green failure class one layer up: the state is
not wrong, it is *gone*. The PreCompact hook writes this brief and the SessionStart
(compact) hook re-injects it, so the post-compaction context starts from evidence, not
from whatever the summary happened to retain. See docs/specs/SPEC-compaction-brief.md
and ADR-0053 (#137).

Pure core (:func:`render_brief`, over :func:`meta_harness.status_assess.obligations`)
plus one I/O gatherer (:func:`gather_brief`) that reuses the self-status readers so
both views agree.
"""

from __future__ import annotations

import json
from pathlib import Path

from meta_harness.spine import load_config
from meta_harness.status_assess import (  # the self-status seam: one import, same readers
    Enforcement,
    Verdict,
    classify_enforcement,
    obligations,
    read_project_verdict,
)

#: Obligations listed in full before the brief truncates (it is re-injected context,
#: not a report; the full record stays in .meta-harness/).
MAX_LISTED = 10


def _verdict_line(verdict: Verdict | None) -> str:
    if verdict is None:
        return "Last gate: never run here"
    run = f"run {verdict.run_id}, " if verdict.run_id else ""
    version = verdict.harness_version or "unknown version"
    return f"Last gate: {'PASS' if verdict.ok else 'FAIL'} ({run}borromeanRings {version})"


def _obligation_lines(verdict: Verdict | None) -> list[str]:
    open_items = obligations(verdict)
    if not open_items:
        return ["Open obligations: none recorded"]
    lines = ["Open obligations:"] + [f"  - {item}" for item in open_items[:MAX_LISTED]]
    if len(open_items) > MAX_LISTED:
        lines.append(f"  … and {len(open_items) - MAX_LISTED} more (see .meta-harness/)")
    return lines


def _identity_line(identity: tuple[str, str] | None) -> str:
    if identity is None:
        return "Commit identity: no [git] identity declared"
    return f"Commit identity policy: {identity[0]} <{identity[1]}>; author overrides are blocked"


def render_brief(
    *,
    project: str,
    verdict: Verdict | None,
    enforcement: Enforcement,
    identity: tuple[str, str] | None,
    harness_home: str,
) -> str:
    """The brief as plain text (pure). Honest on every missing fact; bounded in size."""
    name = project.rstrip("/").rsplit("/", maxsplit=1)[-1] or project
    marker = "" if enforcement.mode == "auto" else "⚠ "
    lines = [
        f"borromeanRings context restored after compaction — {name}",
        "",
        _verdict_line(verdict),
        *_obligation_lines(verdict),
        f"{marker}Enforcement: {enforcement.mode.upper()} — {enforcement.detail}",
        _identity_line(identity),
        f"Re-gate: {harness_home}/verify.sh",
    ]
    return "\n".join(lines)


def _read_settings(project: Path) -> dict[str, object] | None:
    path = project / ".claude" / "settings.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def gather_brief(project: Path | str, harness_home: Path | str) -> str:
    """Read the facts from the governed project and render the brief (the only I/O)."""
    project, harness_home = Path(project), Path(harness_home)
    config = load_config(project / "borromeanrings.toml")
    identity = (config.git_name, config.git_email) if config.git_name and config.git_email else None
    return render_brief(
        project=str(project),
        verdict=read_project_verdict(project),
        enforcement=classify_enforcement(_read_settings(project), str(harness_home)),
        identity=identity,
        harness_home=str(harness_home),
    )
