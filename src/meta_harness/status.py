"""Portfolio status — the roster health view across every governed project.

borromeanRings governs invariants *inside* each repo; this is the missing view *across*
repos. It answers, in one table, the questions a maintainer running borromeanRings on
many projects otherwise has to ``cd`` around to learn: which projects are governed, how
many checks each enforces, whether its last gate was green, whether its config drifted
behind the recommended set, and whether it is even a git repo (history checks such as
``12_secrets`` fail closed when it is not).

This module does the filesystem/process reads (discover projects, query git, read each
project's persisted verdict) and delegates the judgement and rendering to the pure
:mod:`meta_harness.status_assess`. Keeping the I/O here and the logic there keeps both
focused and low-coupling — consistent with borromeanRings's architecture, where the bash
entrypoints (``verify.sh``, ``status.sh``) are the composition roots and the Python
modules stay narrow. Advisory, never a gate: the default read-only report always exits 0;
re-gating for freshness (``--run``) is orchestrated by ``status.sh``. See
docs/specs/SPEC-status.md and ADR-0046.
"""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404 — used only to query git (fixed argv, no shell, no external input)
import sys
from collections.abc import Sequence
from pathlib import Path

from meta_harness.spine import load_config
from meta_harness.status_assess import (
    ProjectStatus,
    build_status,
    classify_enforcement,
    read_project_verdict,
    read_rewrite_tally,
    read_self_report_tally,
    render,
    render_self_status,
    summarize,
)

#: Directories never worth descending into when discovering governed projects.
_SKIP_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".meta-harness",
        "dist",
        "build",
        ".venv",
        "venv",
    }
)
_CONFIG_NAME = "borromeanrings.toml"


def discover_projects(roots: Sequence[Path | str], *, max_depth: int = 6) -> list[Path]:
    """Every directory containing ``borromeanrings.toml`` under ``roots`` (depth-bounded).

    Build-output, vendored, and cache directories are pruned from the walk.
    """
    found: set[Path] = set()
    for raw in roots:
        root = Path(raw)
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            depth = len(Path(dirpath).relative_to(root).parts)
            if depth >= max_depth:
                dirnames[:] = []
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            if _CONFIG_NAME in filenames:
                # Resolve so a symlinked alias and its real path collapse to one row.
                found.add(Path(dirpath).resolve())
    return sorted(found)


def _is_git_repo(path: Path) -> bool:
    # Fail-soft: if git is absent from PATH, subprocess raises OSError — degrade to
    # "not a repo" rather than crash the roster view (the module's fail-soft contract).
    try:
        result = subprocess.run(  # nosec B603 B607 — fixed argv, no shell; only queries git
            ["git", "-C", str(path), "rev-parse", "--git-dir"],
            capture_output=True,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0


def _config_dirty(path: Path) -> bool:
    try:
        result = subprocess.run(  # nosec B603 B607 — fixed argv, no shell; only queries git
            ["git", "-C", str(path), "status", "--porcelain", _CONFIG_NAME],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    return bool(result.stdout.strip())


def gather(path: Path | str) -> ProjectStatus:
    """Read one project's real state (config, git, persisted verdict) into a row."""
    project = Path(path)
    try:
        required = load_config(project / _CONFIG_NAME).required_checks
    except (OSError, ValueError) as exc:
        # Report the real git state even on config error (the GIT column stays honest).
        return ProjectStatus(
            str(project), _is_git_repo(project), False, 0, "never", (), f"config error: {exc}"
        )
    is_git = _is_git_repo(project)
    dirty = _config_dirty(project) if is_git else False
    return build_status(
        str(project),
        is_git=is_git,
        config_dirty=dirty,
        required=required,
        has_changelog=(project / "CHANGELOG.md").exists(),
        last_verdict=read_project_verdict(project),
    )


def find_enclosing_project(start: Path | str) -> Path | None:
    """The nearest ancestor of ``start`` holding a ``borromeanrings.toml`` (or ``None``).

    Lets the self-report work from anywhere inside a governed tree, not only its root.
    """
    current = Path(start).resolve()
    for candidate in (current, *current.parents):
        if (candidate / _CONFIG_NAME).is_file():
            return candidate
    return None


def _self_report(project_hint: Path | str) -> str:
    """Render the single-project report for the project enclosing ``project_hint``."""
    harness_home = os.environ.get("BORROMEANRINGS_HOME", "")
    project = find_enclosing_project(project_hint)
    if project is None:
        return render_self_status(
            project=str(Path(project_hint).resolve()),
            governed=False,
            required=(),
            last_verdict=None,
            enforcement=classify_enforcement(None, harness_home),
            harness_home=harness_home,
        )
    try:
        required = load_config(project / _CONFIG_NAME).required_checks
    except (OSError, ValueError):
        required = ()
    settings_path = project / ".claude" / "settings.json"
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        settings = None
    return render_self_status(
        project=str(project),
        governed=True,
        required=required,
        last_verdict=read_project_verdict(project),
        enforcement=classify_enforcement(settings, harness_home),
        harness_home=harness_home,
        installed_version=os.environ.get("HARNESS_VERSION", ""),
        rewrite_tally=read_rewrite_tally(project),
        self_report_tally=read_self_report_tally(project),
    )


def _self_scope_output(args: Sequence[str]) -> str:
    """The answer for THIS project, in whichever format was asked for.

    ``--list`` yields just its path (what ``status.sh --run`` consumes to decide what to
    re-gate); otherwise the full report.
    """
    hint = os.environ.get("BORROMEANRINGS_PROJECT") or Path.cwd()
    if "--list" in args:
        project = find_enclosing_project(hint)
        return str(project) if project else ""
    return _self_report(hint)


def _wants_roster(args: Sequence[str], roots: Sequence[str]) -> bool:
    """Was a scope WIDER than the current project asked for?

    Scope is opt-in by design: walking every governed project under ``$HOME`` answers a
    portfolio question, and answering it by default surprises someone who only asked
    about the project in front of them.

    ``--list`` deliberately does NOT widen scope — it only changes the output format.
    ``status.sh --run`` discovers its work through ``--list``, so treating it as a roster
    request would make a re-gate from inside one project run the gate over every other
    governed project on the machine, writing receipts into unrelated repos and returning
    an exit code describing their health rather than this project's.
    """
    return bool(roots) or "--all" in args


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint. Reports **this project** unless a wider scope is asked for.

    ``--all`` (or explicit roots) requests the roster; ``--list`` prints discovered
    paths. The read-only report always exits 0 — it reports state, it does not gate.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    roots = [a for a in args if not a.startswith("--")]
    if not _wants_roster(args, roots):
        print(_self_scope_output(args))
        return 0

    projects = discover_projects(roots or [str(Path.home())])
    if "--list" in args:
        print("\n".join(str(p) for p in projects))
        return 0
    statuses = [gather(p) for p in projects]
    print(render(statuses))
    print(summarize(statuses))
    return 0
