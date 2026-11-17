"""Changelog discipline (Keep a Changelog).

Two opt-in rules, each a pure function (inputs in, violation string or ``None``
out); the check script wires git and config around them:

  - :func:`presence_violation` — the changelog exists and has an *Unreleased*
    heading, a home for pending changes. Non-retroactive: it constrains the
    repository's current state, not a diff, so turning it on never fails an
    unrelated in-flight branch.
  - :func:`src_change_violation` — *strict*: if source changed on this branch,
    the changelog must be among the changed files. Retroactive (diff-based), so
    it is enabled deliberately, once a PR queue is clear.

See docs/specs/SPEC-changelog.md and ADR-0028.
"""

from __future__ import annotations

_UNRELEASED = "unreleased"


def presence_violation(changelog_text: str | None, changelog_path: str) -> str | None:
    """The changelog must exist and carry an 'Unreleased' section."""
    if changelog_text is None:
        return (
            f"missing {changelog_path} — Keep a Changelog: create it with an "
            f"'## [Unreleased]' section for pending changes"
        )
    if _UNRELEASED not in changelog_text.lower():
        return (
            f"{changelog_path} has no 'Unreleased' section — add '## [Unreleased]' "
            f"so pending changes have a home (Keep a Changelog)"
        )
    return None


def src_change_violation(changed_paths: list[str], src_dir: str, changelog_path: str) -> str | None:
    """If any source file changed, the changelog must have changed too."""
    prefix = src_dir.rstrip("/") + "/"
    src_changed = [p for p in changed_paths if p == src_dir or p.startswith(prefix)]
    if not src_changed:
        return None
    if changelog_path in changed_paths:
        return None
    return (
        f"{len(src_changed)} source file(s) under '{src_dir}/' changed but "
        f"'{changelog_path}' was not updated — record the change (Keep a Changelog)"
    )
