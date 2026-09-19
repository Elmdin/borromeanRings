"""Git aliases and the branch policy: resolve them, and refuse planting them.

A git alias is the cheapest way around a command guard: ``git config alias.p push``
then ``git p origin main`` contains neither ``push`` nor a recognisable subcommand.
Two pure pieces close that (PR #169 review, ADR-0058):

* :func:`resolve_alias` — expand an alias (from the repo's config, supplied by the
  caller, merged with any ``-c alias.x=…`` / ``GIT_CONFIG_*`` on the command line)
  into the real subcommand so the policy judges what git will actually run. A
  shell alias (``!…``), an unparseable one, or one whose value the guard cannot
  see (``--config-env``) is *opaque* and reported as such — the caller treats it
  conservatively.
* :func:`alias_write_violation` / :func:`alias_floor` — refuse ``git config`` (any
  scope), inline ``-c``, and ``GIT_CONFIG_*`` writes that create or change an
  alias whose expansion runs a branch-writing verb, and — as a floor — any
  command that mentions ``alias.``/``.git/config``/``.gitconfig`` together with
  such a verb (an alias planted by redirection cannot be parsed, only refused).
"""

from __future__ import annotations

import fnmatch
import re
import shlex
from collections.abc import Mapping, Sequence

POLICY = "trunk-based policy, ADR-0058"

#: git builtins that an alias can never shadow (git ignores ``alias.commit``).
GIT_BUILTINS: frozenset[str] = frozenset(
    """add am apply archive bisect blame branch bundle cat-file check-attr check-ignore
    check-mailmap check-ref-format checkout checkout-index cherry cherry-pick citool clean
    clone column commit commit-tree config count-objects credential daemon describe diff
    diff-files diff-index diff-tree difftool fast-export fast-import fetch filter-branch
    fmt-merge-msg for-each-ref format-patch fsck gc grep gui hash-object help hook
    index-pack init instaweb interpret-trailers log ls-files ls-remote ls-tree
    maintenance merge merge-base merge-file merge-tree mergetool mktag mktree mv name-rev
    notes pack-objects pack-refs patch-id prune prune-packed pull push range-diff read-tree
    rebase receive-pack reflog remote repack replace request-pull rerere reset restore
    revert rm rev-list rev-parse send-email shortlog show show-branch show-index show-ref
    sparse-checkout stage stash status stripspace submodule switch symbolic-ref tag
    unpack-objects update-index update-ref update-server-info upload-pack var
    verify-commit verify-pack verify-tag whatchanged worktree write-tree""".split()  # noqa: SIM905
)

#: Subcommands an alias must not be allowed to smuggle in.
ALIAS_VERBS: re.Pattern[str] = re.compile(
    r"(?<![\w-])(push|commit|merge|rebase|reset|branch|update-ref|symbolic-ref)(?![\w-])"
)
_MAX_ALIAS_DEPTH = 8
#: Refspec-ish separators: a word names every branch it contains in any spelling.
_REF_SEPARATORS = ("=", ":")
_CONFIG_READS: frozenset[str] = frozenset(
    {"--get", "--get-all", "--get-regexp", "-l", "--list", "--unset", "--unset-all"}
)


def _env_pair(word: str) -> tuple[str, str, str] | None:
    """``(kind, n, text)`` for a ``GIT_CONFIG_KEY_n=``/``GIT_CONFIG_VALUE_n=`` word."""
    for kind in ("KEY", "VALUE"):
        prefix = f"GIT_CONFIG_{kind}_"
        if word.startswith(prefix):
            name, _, text = word[len(prefix) :].partition("=")
            return kind, name, text
    return None


def _option_pair(word: str, following: str) -> tuple[str, str] | None:
    """The ``(key, value)`` a ``-c``/``-ck=v``/``--config-env=`` option states."""
    if word == "-c" and "=" in following:
        key, _, value = following.partition("=")
        return key, value
    if word.startswith("-c") and not word.startswith("--") and "=" in word:
        key, _, value = word[2:].partition("=")
        return key, value
    if word.startswith("--config-env="):
        key, _, var = word[len("--config-env=") :].partition("=")
        return key, f"!<env {var}>"
    return None


def _config_pairs(argv: Sequence[str]) -> list[tuple[str, str]]:
    """``(key, value)`` config entries stated on the command line itself.

    Sources: leading ``GIT_CONFIG_KEY_n=…``/``GIT_CONFIG_VALUE_n=…`` pairs,
    ``GIT_CONFIG_PARAMETERS='k=v …'``, and git's ``-c k=v`` / ``-ck=v`` /
    ``--config-env=k=VAR`` (value unreadable ⇒ ``"!<env VAR>"``, i.e. opaque).
    """
    pairs: list[tuple[str, str]] = []
    env: dict[str, dict[str, str]] = {"KEY": {}, "VALUE": {}}
    for index, token in enumerate(argv):
        following = argv[index + 1] if index + 1 < len(argv) else ""
        env_pair = _env_pair(token)
        if env_pair is not None:
            kind, name, text = env_pair
            env[kind][name] = text
        elif token.startswith("GIT_CONFIG_PARAMETERS="):
            pairs.extend(_split_parameters(token.split("=", 1)[1]))
        else:
            option = _option_pair(token, following)
            if option is not None:
                pairs.append(option)
    pairs.extend((env["KEY"][n], env["VALUE"].get(n, "")) for n in sorted(env["KEY"]))
    return pairs


def _split_parameters(text: str) -> list[tuple[str, str]]:
    try:
        words = shlex.split(text)
    except ValueError:
        return [("alias.?", "!<unparseable>")]
    return [tuple(w.partition("=")[::2]) for w in words if "=" in w]  # type: ignore[misc]


def inline_aliases(argv: Sequence[str]) -> dict[str, str]:
    """Aliases the command line itself defines (``-c alias.x=…``, ``GIT_CONFIG_*``)."""
    return {
        key[len("alias.") :]: value
        for key, value in _config_pairs(argv)
        if key.lower().startswith("alias.")
    }


def resolve_alias(
    sub: str, args: Sequence[str], aliases: Mapping[str, str]
) -> tuple[str, list[str], str | None]:
    """``(subcommand, args, opaque)`` after expanding ``sub`` through ``aliases``.

    ``opaque`` is None when the result is a real subcommand; otherwise it is the
    alias text the guard could not see through (a ``!`` shell alias, an unparseable
    or cyclic expansion), and ``sub``/``args`` are returned unexpanded.
    """
    seen: list[str] = []
    current, current_args = sub, list(args)
    while current not in GIT_BUILTINS and current in aliases:
        if current in seen or len(seen) >= _MAX_ALIAS_DEPTH:
            return current, current_args, f"{current} = {aliases[current]} (cyclic)"
        seen.append(current)
        expansion = aliases[current]
        if expansion.startswith("!"):
            return current, current_args, f"{current} = {expansion}"
        try:
            words = shlex.split(expansion)
        except ValueError:
            return current, current_args, f"{current} = {expansion} (unparseable)"
        if not words:
            return current, current_args, f"{current} = (empty)"
        current, current_args = words[0], [*words[1:], *current_args]
    return current, current_args, None


def _planted_alias(pairs: Sequence[tuple[str, str]]) -> tuple[str, str] | None:
    for key, value in pairs:
        if key.lower().startswith("alias.") and (ALIAS_VERBS.search(value) or "!" in value):
            return key[len("alias.") :], value
    return None


def _config_write(args: Sequence[str]) -> tuple[str, str] | None:
    """``(alias, value)`` a ``git config`` invocation would set, if it sets an alias."""
    if any(a in _CONFIG_READS for a in args):
        return None
    positional = [a for a in args if not a.startswith("-")]
    for index, word in enumerate(positional):  # `-f file` may precede the key: scan all
        if word.lower().startswith("alias."):
            value = positional[index + 1] if index + 1 < len(positional) else ""
            return word[len("alias.") :], value
    return None


def alias_write_violation(argv: Sequence[str], sub: str, args: Sequence[str]) -> str | None:
    """Reason this invocation plants a branch-writing alias, else None.

    Covers ``git config [--global|--local|--system|--worktree|-f …] alias.X value``
    (``--add``/``--replace-all`` included), inline ``-c alias.X=…`` on any git
    command, and ``GIT_CONFIG_*`` environment pairs. Reads (``--get``, ``--list``,
    ``--unset``) are not writes.
    """
    inline = _planted_alias(_config_pairs(argv))
    if inline is not None:
        name, value = inline
        return (
            f"inline config plants alias '{name}' = '{value}', which runs a branch-writing "
            f"command ({POLICY}): aliases cannot be used to dodge the branch guard."
        )
    if sub != "config":
        return None
    write = _config_write(args)
    if write is None:
        return None
    name, value = write
    if not (ALIAS_VERBS.search(value) or value.startswith("!")):
        return None
    return (
        f"'git config' would set alias '{name}' = '{value}', which runs a branch-writing "
        f"command ({POLICY}): aliases cannot be used to dodge the branch guard."
    )


def shell_alias_command(definition: str, args: Sequence[str]) -> str:
    """The shell command git runs for a ``!`` alias: its text plus the trailing words.

    git executes ``sh -c '<definition> "$@"' <definition> <args…>``, so the
    invocation's arguments are appended to whatever the alias text is.
    """
    body = definition[1:] if definition.startswith("!") else definition
    return f"{body} {shlex.join(args)}".strip()


def args_name_protected(args: Sequence[str], protected: Sequence[str]) -> str | None:
    """The first protected branch an argument names in any refspec spelling, else None.

    ``main``, ``+main``, ``HEAD:main``, ``feat/x:refs/heads/main``,
    ``--force-with-lease=main:abc`` and glob refspecs all name ``main``.
    """
    for arg in args:
        pieces = [arg.lstrip("+")]
        for sep in _REF_SEPARATORS:
            pieces = [piece for word in pieces for piece in word.split(sep)]
        for piece in pieces:
            name = piece.removeprefix("refs/heads/")
            hit = next((p for p in protected if fnmatch.fnmatch(p, name)), None)
            if hit is not None and name:
                return hit
    return None


def alias_floor(command: str) -> str | None:
    """Refuse any command that mentions an alias/config location AND a branch verb.

    An alias planted by redirection (``echo '[alias] p = push' >> .git/config``,
    ``sed -i … ~/.gitconfig``) cannot be parsed, only refused. Conservative by
    design: the floor never lets through what the parser might miss.
    """
    mentions = ("alias.", "[alias]", ".git/config", ".gitconfig")
    if any(m in command for m in mentions) and ALIAS_VERBS.search(command):
        return (
            f"command mentions git alias/config together with a branch-writing verb "
            f"({POLICY}): editing aliases that push/commit/merge/rebase/reset/branch is "
            f"refused (floor) — run it outside the guard if genuinely intended."
        )
    return None
