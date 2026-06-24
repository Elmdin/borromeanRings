"""Git-identity enforcement: commits/pushes must use the declared identity.

A project DECLARES the git identity its commits must use (``[git].name``/``email``
in ``borromeanrings.toml``). A wrong account committing is a correctness/security failure
(broken provenance). This module is the pure decision logic; a PreToolUse guard
uses it preventively (block the bad commit) and a gate check uses it as a backstop
(fail-closed on any commit that slipped through). Not declared ⇒ not enforced.

See docs/specs/SPEC-git-identity.md and ADR-0017.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Identity:
    """A git author identity. Empty fields mean "unset / unconstrained"."""

    name: str
    email: str


def is_enforced(declared: Identity) -> bool:
    """True iff the project declared an identity to enforce (any field set)."""
    return bool(declared.email or declared.name)


def configured_violation(configured: Identity, declared: Identity) -> str | None:
    """Reason the repo's *configured* identity violates the declared one, else None.

    Only declared fields are checked: declaring an email but no name leaves the
    name unconstrained.
    """
    if not is_enforced(declared):
        return None
    problems: list[str] = []
    if declared.name and configured.name != declared.name:
        problems.append(f"user.name '{configured.name or '(unset)'}' != '{declared.name}'")
    if declared.email and configured.email != declared.email:
        problems.append(f"user.email '{configured.email or '(unset)'}' != '{declared.email}'")
    return "; ".join(problems) or None


def author_violations(authors: Sequence[Identity], declared: Identity) -> list[str]:
    """The subset of commit authors that are not the declared identity."""
    if not is_enforced(declared):
        return []
    offenders: list[str] = []
    for author in authors:
        name_bad = bool(declared.name) and author.name != declared.name
        email_bad = bool(declared.email) and author.email != declared.email
        if name_bad or email_bad:
            offenders.append(f"{author.name} <{author.email}>")
    return offenders
