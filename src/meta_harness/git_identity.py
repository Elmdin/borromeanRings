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


#: git's own global options that consume the following argument.
_GIT_GLOBAL_WITH_VALUE: frozenset[str] = frozenset(
    {"-c", "-C", "--git-dir", "--work-tree", "--namespace", "--config-env"}
)

#: Shell operators that end one command and begin another.
_SEPARATORS: frozenset[str] = frozenset({"&&", "||", ";", "|", "&", "(", ")", "{", "}"})

#: Words that precede and then run another command, e.g. `env git commit`.
_WRAPPERS: frozenset[str] = frozenset(
    {"env", "command", "builtin", "exec", "nohup", "time", "sudo", "nice", "then", "do", "else"}
)

#: Shells whose `-c` argument is itself a command line to look inside.
_SHELLS: frozenset[str] = frozenset({"sh", "bash", "zsh", "dash", "ksh"})


def _tokenize(command: str) -> list[str]:
    """Split a command line into tokens, with shell operators as tokens of their own.

    ``shlex.split`` keeps ``x;`` as a single token, so ``x; git commit`` would look like
    one command whose head is ``x;`` and the git invocation after it would be missed.
    ``punctuation_chars`` makes the lexer break on the operators instead.
    """
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def _split_segments(tokens: Sequence[str]) -> list[list[str]]:
    """Split a token stream on shell operators into individual commands."""
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token in _SEPARATORS:
            segments.append([])
        else:
            segments[-1].append(token)
    return [segment for segment in segments if segment]


def _head_index(segment: Sequence[str]) -> int:
    """Index of the actual command word, past leading assignments and wrapper words."""
    index = 0
    while index < len(segment):
        token = segment[index]
        if (
            "=" in token
            and not token.startswith("-")
            or token.rsplit("/", 1)[-1].lstrip("\\") in _WRAPPERS
        ):
            index += 1
        else:
            break
    return index


def _logical_lines(command: str) -> list[str]:
    """``command`` split into logical lines, backslash continuations joined.

    A command's arguments live on its own logical line. Tokenizing the whole payload at
    once flattens a heredoc body into the argv of the command that opened it, so a commit
    whose MESSAGE mentions an identity flag looks like a commit that USES one.
    Continuations are joined first so a genuinely wrapped invocation is still seen whole.
    """
    return command.replace("\\\n", " ").splitlines() or [command]


def git_invocations(command: str) -> list[list[str]]:
    """Every git invocation in a (possibly compound) command line, as token lists.

    A command line is rarely one command. ``cd dir && git commit``, ``x; git commit``,
    ``( git commit )`` and ``sh -c 'git commit'`` all run git while containing it
    somewhere other than the front — and a parser that only inspects the head of the
    line misses every one of them. That is *narrower* than the substring match this
    replaced, which is a regression a guard cannot afford: precision must not cost
    coverage. Segments the line first, then parses each segment.
    """
    found: list[list[str]] = []
    for line in _logical_lines(command):
        try:
            tokens = _tokenize(line)
        except ValueError:
            continue
        found.extend(_invocations_in_line(tokens))
    return found


def _invocations_in_line(tokens: Sequence[str]) -> list[list[str]]:
    """git invocations within one already-tokenized logical line."""
    found: list[list[str]] = []
    for segment in _split_segments(tokens):
        start = _head_index(segment)
        if start >= len(segment):
            continue
        head = segment[start].rsplit("/", 1)[-1].lstrip("\\")
        if head == "git":
            # The WHOLE segment, assignments included -- they carry overrides.
            found.append(list(segment))
        elif head in _SHELLS and "-c" in segment:
            index = segment.index("-c")
            if index + 1 < len(segment):
                found.extend(git_invocations(segment[index + 1]))
    return found


def _subcommand_of(tokens: Sequence[str]) -> str:
    """The subcommand of one already-isolated git invocation."""
    index = _head_index(tokens) + 1
    while index < len(tokens):
        token = tokens[index]
        if not token.startswith("-"):
            return token
        if token in _GIT_GLOBAL_WITH_VALUE:
            index += 2
            continue
        index += 1
    return ""


def git_subcommands(command: str) -> list[str]:
    """Every git subcommand invoked anywhere in ``command``."""
    return [sub for sub in (_subcommand_of(inv) for inv in git_invocations(command)) if sub]


def git_subcommand(command: str) -> str:
    """The first git subcommand ``command`` invokes, else ``""``."""
    subs = git_subcommands(command)
    return subs[0] if subs else ""


#: Environment variables git honours for authorship, each overriding config for one run.
AUTHOR_ENV_VARS: tuple[str, ...] = (
    "GIT_AUTHOR_NAME",
    "GIT_AUTHOR_EMAIL",
    "GIT_COMMITTER_NAME",
    "GIT_COMMITTER_EMAIL",
)

#: Substrings that mean "this command carries its own identity". Cheap pre-filter: if
#: none appears, there is nothing to parse and nothing to enforce.
OVERRIDE_MARKERS: tuple[str, ...] = (
    "--author",
    "-c user.",
    "-cuser.",
    "--config-env=",
    "GIT_CONFIG_KEY_",
    "GIT_CONFIG_COUNT",
    *AUTHOR_ENV_VARS,
)


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
    if arg.startswith("--config-env="):
        key = arg.split("=", 1)[1].split("=", 1)[0]
        return ("opaque", key) if key in ("user.email", "user.name") else None
    if arg.startswith(("-cuser.email=", "-cuser.name=")):
        key, _, value = arg[2:].partition("=")
        return ("email" if key == "user.email" else "name", value)
    return _env_override(arg)


#: A git invocation in COMMAND position: start of line or just after a shell operator,
#: optionally preceded by environment assignments. Used only when tokenizing failed.
_GIT_AT_COMMAND_START = re.compile(r"(?:^|[;&|(]|\n)\s*(?:\w+=\S*\s+)*(?:\S*/)?git\s", re.MULTILINE)


def _git_command_lines(command: str) -> list[str]:
    """The lines of ``command`` that actually start a git invocation."""
    return [line for line in command.splitlines() if _GIT_AT_COMMAND_START.search(line)]


def _looks_like_git_commit(command: str) -> bool:
    """Best-effort check that an UNPARSEABLE command line really invokes git commit/push.

    The fallback used to accept git appearing anywhere in the text, which flagged any
    unparseable command that merely discussed git -- a heredoc writing these very tests,
    for instance. Requiring command position keeps the fail-closed behaviour for a
    genuinely malformed git invocation without blocking prose that mentions one.
    """
    if not _GIT_AT_COMMAND_START.search(command):
        return False
    return re.search(r"\b(commit|push)\b", command) is not None


def _config_env_pairs(tokens: Sequence[str]) -> list[tuple[str, str]]:
    """Identity overrides supplied through git's numbered config environment variables.

    git's numbered config environment (a count plus indexed key/value pairs) sets
    arbitrary config for one invocation, including ``user.email``. Real git honours it,
    so a guard that does not read it can be walked past with three variables.
    """
    keys: dict[str, str] = {}
    values: dict[str, str] = {}
    for arg in tokens:
        for prefix, sink in (("GIT_CONFIG_KEY_", keys), ("GIT_CONFIG_VALUE_", values)):
            if arg.startswith(prefix):
                number, _, value = arg[len(prefix) :].partition("=")
                sink[number] = value
    found: list[tuple[str, str]] = []
    for number, key in keys.items():
        if key in ("user.email", "user.name"):
            kind = "email" if key == "user.email" else "name"
            found.append((kind, values.get(number, "")) if number in values else ("opaque", key))
    return found


def _overrides_in(tokens: Sequence[str]) -> list[tuple[str, str]]:
    """Identity overrides carried by ``tokens`` as (kind, value) pairs."""
    found: list[tuple[str, str]] = _config_env_pairs(tokens)
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
    if kind == "opaque":
        return (
            f"{value} is set from an environment variable this guard cannot read; "
            "refusing rather than assuming it is correct"
        )
    if not value:
        return None
    if kind == "author":
        return _author_violation(value, declared)
    if kind == "email" and declared.email and value != declared.email:
        return f"an inline override sets user.email={value}, requires {declared.email}"
    if kind == "name" and declared.name and value != declared.name:
        return f"an inline override sets user.name={value}, requires {declared.name}"
    return None


def _unparseable_violation(command: str) -> str | None:
    """Verdict for a command line that could not be tokenized.

    Refusing everything unparseable would block ordinary work; allowing it would make
    the guard evadable by mangling quotes. The middle ground: refuse only when the line
    that actually invokes git carries an identity marker. Anything else on the command
    line -- a heredoc body, a commit message documenting these very flags -- is data,
    not arguments.
    """
    if not _looks_like_git_commit(command):
        return None
    git_lines = _git_command_lines(command)
    if not any(marker in line for line in git_lines for marker in OVERRIDE_MARKERS):
        return None
    return (
        "this command carries a git identity override that could not be parsed "
        "(unbalanced quotes); refusing rather than guessing"
    )


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
        _tokenize(command)  # probe: we only need to know whether the line parses
    except ValueError:
        return _unparseable_violation(command)
    # Scan each invocation separately. A flat scan of the outer tokens misses anything
    # inside a shell -c argument, where the whole inner command is one opaque token.
    for invocation in git_invocations(command):
        if _subcommand_of(invocation) not in {"commit", "push"}:
            continue
        for kind, value in _overrides_in(invocation):
            violation = _override_violation(kind, value, declared)
            if violation:
                return violation
    return None
