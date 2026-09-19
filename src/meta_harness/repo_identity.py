"""Does git's repository for a project belong to that project?

A `.git` FILE links a directory to a repository kept elsewhere. Git itself then treats
the directory holding that file as the working tree, so ``git rev-parse
--show-toplevel`` names the project whatever the pointer says, and cannot tell a
legitimate link from a wrong one. The pointer's target can:

* a **linked worktree**'s gitdir holds a ``gitdir`` file naming this project's ``.git``;
* a **submodule** or ``--separate-git-dir`` repository sets ``core.worktree`` to this
  project in its config;
* anything else, such as another project's own ``.git``, has a working tree that is not
  this project, and whatever git reports about "tracked files" describes that one.

Every borromeanRings project shares scaffold filenames, so a pointer to a sibling
resolves some of its paths: counting overlaps cannot catch it (review of #250).
"""

from __future__ import annotations

import subprocess  # nosec B404 — fixed argv, no shell; only reads a config file
from pathlib import Path

_POINTER = "gitdir:"


def _resolve(base: Path, value: str) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else base / path).resolve()


def _configured_worktree(gitdir: Path) -> Path | None:
    config = gitdir / "config"
    if not config.is_file():
        return None
    done = subprocess.run(  # nosec B603 B607 — fixed argv, no shell
        ["git", "config", "--file", str(config), "--get", "core.worktree"],
        capture_output=True,
        text=True,
        check=False,
    )
    value = done.stdout.strip()
    return _resolve(gitdir, value) if done.returncode == 0 and value else None


def _pointer(dotgit: Path) -> tuple[Path | None, str]:
    """The gitdir a ``.git`` file names, or ``(None, reason)`` when it names none."""
    try:
        content = dotgit.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"cannot read {dotgit}: {exc}"
    if not content.startswith(_POINTER):
        return None, f"{dotgit} is a file but not a gitdir pointer"
    return _resolve(dotgit.parent, content[len(_POINTER) :].strip()), ""


def _linked_worktree(gitdir: Path, dotgit: Path) -> str:
    """A linked worktree's metadata must name THIS ``.git`` file as its checkout."""
    backlink = gitdir / "gitdir"
    try:
        named = _resolve(gitdir, backlink.read_text(encoding="utf-8").strip())
    except (OSError, UnicodeDecodeError) as exc:
        return f"cannot read {backlink}: {exc}"
    if named == dotgit.resolve():
        return ""
    return (
        f"{dotgit} points at worktree metadata {gitdir}, which belongs to another "
        f"checkout ({named.parent})"
    )


def _store(gitdir: Path, root: Path, dotgit: Path) -> str:
    """A repository with no linked-worktree metadata: whose working tree is it?"""
    worktree = _configured_worktree(gitdir)
    if worktree is None and gitdir.name == ".git" and gitdir.parent != root:
        worktree = gitdir.parent  # another directory's OWN repository
    if worktree is None or worktree == root:
        # A submodule or a store configured for this directory, or a detached store
        # (--separate-git-dir), which belongs to whoever points at it.
        return ""
    return (
        f"{dotgit} points at {gitdir}, a repository whose working tree is "
        f"{worktree}, not this project"
    )


def foreign_repository(project_root: Path | str) -> str:
    """``""`` when git's repository for ``project_root`` is its own; else the reason.

    A ``.git`` directory, or no ``.git`` at all (the project sits inside a larger
    repository), is git's ordinary discovery and is accepted as it is.
    """
    root = Path(project_root).resolve()
    dotgit = root / ".git"
    if not dotgit.is_file():
        return ""
    gitdir, reason = _pointer(dotgit)
    if gitdir is None:
        return reason
    if (gitdir / "gitdir").is_file():
        return _linked_worktree(gitdir, dotgit)
    return _store(gitdir, root, dotgit)
