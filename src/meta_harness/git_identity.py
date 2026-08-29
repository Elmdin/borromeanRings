"""Git-identity enforcement: commits/pushes must use the declared identity.

A project DECLARES the git identity its commits must use (``[git].name``/``email``
in ``borromeanrings.toml``). A wrong account committing is a correctness/security failure
(broken provenance). This module is the pure decision logic; a PreToolUse guard
uses it preventively (block the bad commit) and a gate check uses it as a backstop
(fail-closed on any commit that slipped through). Not declared ⇒ not enforced.

See docs/specs/SPEC-git-identity.md and ADR-0017.
"""

from __future__ import annotations

import re
import shlex
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


#: git's own global options that take a value, so a subcommand scan can step over them.
_GIT_GLOBAL_WITH_VALUE: frozenset[str] = frozenset(
    {"-c", "-C", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}
)


def git_subcommand(command: str) -> str:
    """The git subcommand ``command`` invokes (``"commit"``, ``"push"``, ...), else ``""``.

    Substring matching on ``"git commit"`` misses every spelling that puts something
    between the two words -- ``git -c user.email=... commit``, ``git -C path commit``, a leading
    ``VAR=value`` environment assignment -- which is exactly how a guard keyed on that
    substring is walked past (issue #54). This steps over leading environment
    assignments and git's global options instead.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return ""
    index = 0
    while index < len(tokens) and "=" in tokens[index] and not tokens[index].startswith("-"):
        index += 1
    if index >= len(tokens) or tokens[index].rsplit("/", 1)[-1] != "git":
        return ""
    index += 1
    while index < len(tokens):
        arg = tokens[index]
        if not arg.startswith("-"):
            return arg
        if arg in _GIT_GLOBAL_WITH_VALUE:
            index += 2
            continue
        index += 1
    return ""


#: Environment variables git honours for authorship, each overriding config for one run.
AUTHOR_ENV_VARS: tuple[str, ...] = (
    "GIT_AUTHOR_NAME",
    "GIT_AUTHOR_EMAIL",
    "GIT_COMMITTER_NAME",
    "GIT_COMMITTER_EMAIL",
)

#: Substrings that mean "this command carries its own identity". Cheap pre-filter: if
#: none appears, there is nothing to parse and nothing to enforce.
OVERRIDE_MARKERS: tuple[str, ...] = ("--author", "-c user.", "-cuser.", *AUTHOR_ENV_VARS)


def _email_of(value: str) -> str:
    """The address inside ``Name <addr>``, or the value itself if already bare."""
    if "<" in value and ">" in value:
        return value[value.index("<") + 1 : value.index(">")].strip()
    return value.strip()


def _name_of(value: str) -> str:
    """The display name in ``Name <addr>``, or "" when the value is a bare address."""
    return value[: value.index("<")].strip() if "<" in value else ""


def _env_override(arg: str) -> tuple[str, str] | None:
    """The identity override carried by a leading ``VAR=value`` assignment, if any."""
    for env in AUTHOR_ENV_VARS:
        if arg.startswith(f"{env}="):
            return ("email" if env.endswith("_EMAIL") else "name", arg.split("=", 1)[1])
    return None


def _override_in_arg(arg: str, nxt: str) -> tuple[str, str] | None:
    """The identity override carried by one argv entry as (kind, value), if any."""
    if arg == "--author":
        return ("author", nxt)
    if arg.startswith("--author="):
        return ("author", arg.split("=", 1)[1])
    if arg == "-c" and nxt.startswith(("user.email=", "user.name=")):
        key, _, value = nxt.partition("=")
        return ("email" if key == "user.email" else "name", value)
    if arg.startswith(("-cuser.email=", "-cuser.name=")):
        key, _, value = arg[2:].partition("=")
        return ("email" if key == "user.email" else "name", value)
    return _env_override(arg)


def _overrides_in(tokens: Sequence[str]) -> list[tuple[str, str]]:
    """Identity overrides carried by ``tokens`` as (kind, value) pairs."""
    found: list[tuple[str, str]] = []
    for index, arg in enumerate(tokens):
        nxt = tokens[index + 1] if index + 1 < len(tokens) else ""
        hit = _override_in_arg(arg, nxt)
        if hit is not None:
            found.append(hit)
    return found


def _author_violation(value: str, declared: Identity) -> str | None:
    """Reason an ``--author`` value conflicts with the declared identity, else ``None``."""
    email, name = _email_of(value), _name_of(value)
    if declared.email and email and email != declared.email:
        return f"--author sets {email}, but this repo requires {declared.email}"
    if declared.name and name and name != declared.name:
        return f"--author sets '{name}', but this repo requires '{declared.name}'"
    return None


def _override_violation(kind: str, value: str, declared: Identity) -> str | None:
    """Reason one parsed override conflicts with the declared identity, else ``None``."""
    if not value:
        return None
    if kind == "author":
        return _author_violation(value, declared)
    if kind == "email" and declared.email and value != declared.email:
        return f"an inline override sets user.email={value}, requires {declared.email}"
    if kind == "name" and declared.name and value != declared.name:
        return f"an inline override sets user.name={value}, requires {declared.name}"
    return None


def command_override_violation(command: str, declared: Identity) -> str | None:
    """Reason ``command`` would commit under a non-declared identity, else ``None``.

    The repo's *configured* identity being correct does not mean the resulting commit
    will be: ``--author``, ``-c user.email=``, and the ``GIT_AUTHOR_*``/``GIT_COMMITTER_*``
    environment variables each override config for a single invocation.
    :func:`configured_violation` cannot see any of them, so a guard built only on it is
    evaded by a one-line change.

    An override that *states the declared identity* is fine — being explicit is not
    evasion. An override this function cannot parse is refused rather than waved
    through, since failing open would make the guard evadable by mangling quotes.
    """
    if not is_enforced(declared):
        return None
    if not any(marker in command for marker in OVERRIDE_MARKERS):
        return None
    try:
        tokens = shlex.split(command)
    except ValueError:
        # Unparseable. Refuse only if this looks like a git commit/push -- otherwise an
        # unbalanced quote anywhere near an identity flag (a shell one-liner, a grep, a
        # heredoc that merely mentions git) would be blocked for no reason.
        if not re.search(r"\bgit\b.*\b(commit|push)\b", command):
            return None
        return (
            "this command carries a git identity override that could not be parsed "
            "(unbalanced quotes); refusing rather than guessing"
        )
    # Only a real git commit/push is this guard's business. Testing merely for a "git"
    # token would flag any script or heredoc that happens to mention one.
    if git_subcommand(command) not in {"commit", "push"}:
        return None

    for kind, value in _overrides_in(tokens):
        violation = _override_violation(kind, value, declared)
        if violation:
            return violation
    return None
