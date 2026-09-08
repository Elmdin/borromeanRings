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

import os
import subprocess  # nosec B404 — used only to query git (fixed argv, no shell, no external input)
import sys
from collections.abc import Sequence
from pathlib import Path

from meta_harness.spine import CONFIG_NAME, LEGACY_CONFIG_NAME, load_config, resolve_config_path
from meta_harness.status_assess import (
    ProjectStatus,
    build_status,
    read_project_verdict,
    render,
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
_CONFIG_NAME = CONFIG_NAME
# Both spellings mark a governed project; the legacy one loads via spine's fallback.
_CONFIG_NAMES = (CONFIG_NAME, LEGACY_CONFIG_NAME)


def discover_projects(roots: Sequence[Path | str], *, max_depth: int = 6) -> list[Path]:
    """Every directory containing ``borromeanrings.toml`` under ``roots`` (depth-bounded).

    A legacy ``borromeo.toml`` (pre-rename, issue #62) also marks a governed project.

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
            if any(name in filenames for name in _CONFIG_NAMES):
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


def _config_dirty(path: Path, config_name: str = _CONFIG_NAME) -> bool:
    # Only the file that was actually resolved counts: an untracked stray borromeo.toml
    # next to a clean canonical config is not "config uncommitted" (PR #165 review).
    try:
        result = subprocess.run(  # nosec B603 B607 — fixed argv, no shell; only queries git
            ["git", "-C", str(path), "status", "--porcelain", "--", config_name],
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
    config = resolve_config_path(project / _CONFIG_NAME)  # warns once for a legacy name
    try:
        required = load_config(config).required_checks
    except (OSError, ValueError) as exc:
        # Report the real git state even on config error (the GIT column stays honest).
        return ProjectStatus(
            str(project), _is_git_repo(project), False, 0, "never", (), f"config error: {exc}"
        )
    is_git = _is_git_repo(project)
    dirty = _config_dirty(project, config.name) if is_git else False
    return build_status(
        str(project),
        is_git=is_git,
        config_dirty=dirty,
        required=required,
        has_changelog=(project / "CHANGELOG.md").exists(),
        last_verdict=read_project_verdict(project),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint. ``--list`` prints discovered paths; otherwise renders the table.

    Positional args are roots to scan (default: the user's home). The read-only report
    always exits 0 — it reports state, it does not gate.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    list_only = "--list" in args
    roots = [a for a in args if not a.startswith("--")] or [str(Path.home())]
    projects = discover_projects(roots)
    if list_only:
        print("\n".join(str(p) for p in projects))
        return 0
    statuses = [gather(p) for p in projects]
    print(render(statuses))
    print(summarize(statuses))
    return 0
