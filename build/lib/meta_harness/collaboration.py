"""Tier A collaboration gates: branch naming and Conventional-Commit subjects.

Pure decision logic for checks ``08_branch`` and ``09_commits`` (the checks
gather the git facts and call in here). Config-driven via the spine's
``[collaboration]`` table; every rule is opt-in — undeclared (empty) config
turns it off, so ungoverned projects are never surprised. Declared rules fail
closed. See docs/specs/SPEC-collaboration.md and ADR-0021 (Gitflow-lite).
"""

import fnmatch
import re
from collections.abc import Sequence


def branch_violation(
    branch: str, protected_branches: Sequence[str], branch_patterns: Sequence[str]
) -> str | None:
    """Judge a branch name against the declared naming patterns.

    Args:
        branch: current branch name; ``""`` or ``"HEAD"`` means detached.
        protected_branches: integration/release branches where naming rules
            don't apply (CI runs there post-merge).
        branch_patterns: allowed glob patterns (e.g. ``feat/*``); empty ⇒ off.

    Returns:
        A violation message, or None when the branch conforms or the rule
        doesn't apply (off, protected branch, or detached HEAD).
    """
    if not branch_patterns:
        return None  # rule not declared ⇒ off
    if branch in ("", "HEAD"):
        return None  # detached HEAD (PR CI merge ref) — no branch name to judge
    if branch in protected_branches:
        return None  # post-merge CI on main/dev; work-branch rules don't apply
    if any(fnmatch.fnmatch(branch, pattern) for pattern in branch_patterns):
        return None
    allowed = ", ".join(branch_patterns)
    return f"branch '{branch}' matches none of the declared patterns ({allowed})"


def commit_violations(
    commits: Sequence[tuple[str, str]],
    commit_types: Sequence[str],
    subject_max_length: int,
) -> list[str]:
    """Judge commit subjects against Conventional Commits.

    Args:
        commits: ``(sha, subject)`` pairs, merge commits already excluded.
        commit_types: allowed types (e.g. ``feat``, ``fix``); empty ⇒ off.
        subject_max_length: subject length bound; ``0`` ⇒ length rule off.

    Returns:
        One message per non-conforming commit (empty list ⇒ all conform).
    """
    if not commit_types:
        return []  # rule not declared ⇒ off
    types = "|".join(re.escape(t) for t in commit_types)
    subject_re = re.compile(rf"^({types})(\([^)]+\))?!?: \S.*$")

    violations: list[str] = []
    for sha, subject in commits:
        short = sha[:8]
        if not subject_re.match(subject):
            allowed = ", ".join(commit_types)
            violations.append(
                f"{short}: '{subject}' is not Conventional "
                f"(expected 'type(scope)?: subject' with type in: {allowed})"
            )
        elif subject_max_length and len(subject) > subject_max_length:
            violations.append(
                f"{short}: subject is {len(subject)} chars (declared max {subject_max_length})"
            )
    return violations
