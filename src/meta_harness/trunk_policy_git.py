"""Git facts for the branch policy guard: HEAD and aliases of a command's repo.

The decision logic (``trunk_policy``, ``trunk_aliases``) is pure; this thin module
reads what it needs from git with a **fixed argv** (never a shell, never user text
as a program) and fails soft — an unreadable repo yields None/empty and the caller
falls back conservatively. Used by ``pre_bash_guard.sh``; see ADR-0058.
"""

from __future__ import annotations

import os
import subprocess  # nosec B404 — used only to query git (fixed argv, no shell, no external input)
from collections.abc import Callable, Sequence

from meta_harness.trunk_policy import Invocation, RepoFacts, git_globals

_TIMEOUT_S = 5


def _git(args: Sequence[str], cwd: str) -> str | None:
    """stdout of ``git <args>`` run in ``cwd``; None when git fails or is absent."""
    try:
        result = subprocess.run(  # nosec B603 B607 — fixed argv, no shell; only queries git
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


def head_branch(cwd: str, globals_: Sequence[str] = ()) -> str | None:
    """Current branch of the repo at ``cwd`` (``HEAD`` when detached); None if unreadable."""
    out = _git([*globals_, "rev-parse", "--abbrev-ref", "HEAD"], cwd)
    return out.strip() if out else None


def repo_aliases(cwd: str, globals_: Sequence[str] = ()) -> dict[str, str]:
    """Every ``alias.*`` git sees from ``cwd`` (all scopes), as ``{name: expansion}``."""
    out = _git([*globals_, "config", "--get-regexp", r"^alias\."], cwd)
    aliases: dict[str, str] = {}
    for line in (out or "").splitlines():
        key, _, value = line.partition(" ")  # every line matched ^alias\. by construction
        aliases[key[len("alias.") :]] = value
    return aliases


def checked_out_branches(cwd: str) -> set[str]:
    """Branches checked out in ANY worktree of the repo at ``cwd``."""
    out = _git(["worktree", "list", "--porcelain"], cwd) or ""
    return {
        line[len("branch refs/heads/") :]
        for line in out.splitlines()
        if line.startswith("branch refs/heads/")
    }


def _resolve_dir(project_dir: str, cwd: str | None) -> str | None:
    """The directory a ``cd`` chain lands in, or None when it cannot be resolved."""
    if cwd is None:
        return project_dir
    if cwd == "?":
        return None
    target = os.path.expanduser(cwd)
    resolved = target if os.path.isabs(target) else os.path.join(project_dir, target)
    return resolved if os.path.isdir(resolved) else None


def facts_resolver(project_dir: str, protected: Sequence[str]) -> Callable[[Invocation], RepoFacts]:
    """A ``facts_at`` callback for :func:`trunk_policy.branch_policy_violation`.

    Reads HEAD and aliases from the invocation's *effective* repo (its ``cd`` chain
    plus ``-C``/``--git-dir``/``--work-tree``). When that repo cannot be resolved,
    it answers conservatively: HEAD is reported as the first declared protected
    branch checked out in **any** worktree of the governed repo, so a write in an
    unknown directory is refused rather than waved through.
    """

    def resolve(invocation: Invocation) -> RepoFacts:
        globals_ = git_globals(invocation.argv)
        directory = _resolve_dir(project_dir, invocation.cwd)
        head = head_branch(directory, globals_) if directory is not None else None
        if head is not None and directory is not None:
            return RepoFacts(head=head, aliases=repo_aliases(directory, globals_))
        checked_out = checked_out_branches(project_dir)
        fallback = next((p for p in protected if p in checked_out), None)
        return RepoFacts(
            head=fallback or head_branch(project_dir) or "HEAD",
            aliases=repo_aliases(project_dir),
        )

    return resolve
