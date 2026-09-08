"""Trunk-based branch policy: nothing lands on a protected branch except via PR + gate.

Pure decision logic for two enforcement layers (ADR-0058, issue #75):

* the PreToolUse guard (``.claude/hooks/pre_bash_guard.sh``) calls
  :func:`branch_policy_violation` with the command about to run, the current HEAD
  branch and the declared ``[collaboration].protected_branches`` — and denies with
  the returned reason;
* the gate check ``08_branch`` calls :func:`direct_commit_violation` with the count
  of local commits the protected branch has beyond its remote ref — the backstop for
  a commit that was made outside the guard.

The command parser here segments a shell line (``a && git push …``, ``sh -c '…'``,
heredocs skipped) and reads git's real subcommand and arguments, so a push to
``main`` is recognised in every spelling (``origin main``, ``HEAD:main``, ``+main``,
``refs/heads/main``, ``--delete``, ``--all``). It is deliberately *never narrower*
than the substring match it replaces: while HEAD is protected, any command that
merely mentions ``git commit``/``git push`` is still refused (the floor, see PR #126).
Undeclared protection (empty tuple) turns everything off. See
docs/specs/SPEC-branch-policy.md.
"""

from __future__ import annotations

import fnmatch
import shlex
from collections.abc import Sequence
from dataclasses import dataclass

#: git global options that consume the following argument.
_GIT_GLOBAL_WITH_VALUE: frozenset[str] = frozenset(
    {"-c", "-C", "--git-dir", "--work-tree", "--namespace", "--config-env", "--exec-path"}
)
#: Shell operators that end one simple command (redirections included: what follows
#: a redirect is a filename, never a command head).
_SEPARATORS: frozenset[str] = frozenset(
    {"&&", "||", ";", "|", "&", "(", ")", "{", "}", ">", "<", ">>", "<<", ">&", "<&", "|&"}
)
#: Words that merely precede and then run another command.
_WRAPPERS: frozenset[str] = frozenset(
    {"env", "command", "builtin", "exec", "nohup", "time", "sudo", "nice", "then", "do", "else"}
)
_HEREDOC = "<<"
#: Shells whose ``-c`` argument is itself a command line to look inside.
_SHELLS: frozenset[str] = frozenset({"sh", "bash", "zsh", "dash", "ksh"})

#: Subcommands that create or move commits on the current branch.
_LANDS_ON_HEAD: frozenset[str] = frozenset(
    {"commit", "merge", "rebase", "cherry-pick", "revert", "am"}
)
_RESET_MOVES_HEAD: frozenset[str] = frozenset({"--hard", "--soft", "--mixed", "--merge", "--keep"})
#: `git branch` options that delete or force-move the named branch.
_BRANCH_REWRITE_FLAGS: frozenset[str] = frozenset(
    {"-d", "-D", "--delete", "-f", "--force", "-m", "-M", "--move"}
)
_PUSH_WITH_VALUE: frozenset[str] = frozenset(
    {"--repo", "--receive-pack", "--exec", "-o", "--push-option"}
)

POLICY = "trunk-based policy, ADR-0058"
COMMIT_HINT = "create a feature branch (git switch -c feat/<name>); land via PR + gate"


@dataclass(frozen=True)
class PushSpec:
    """What one ``git push`` argument list targets."""

    remote: str
    destinations: tuple[str, ...]  # branch names (or globs) written on the remote
    force: bool  # --force / -f / --force-with-lease / +refspec
    implicit: bool  # no refspec ⇒ the current branch is pushed
    everything: bool  # --all / --mirror ⇒ every branch, protected ones included
    deletes: bool  # --delete / -d / ":branch" ⇒ the destinations are removed


# --- tokenizing a shell command line ---------------------------------------------


def _tokenize(line: str) -> list[str]:
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def _segments(tokens: Sequence[str]) -> list[list[str]]:
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token in _SEPARATORS:
            segments.append([])
        else:
            segments[-1].append(token)
    return [segment for segment in segments if segment]


def _basename(token: str) -> str:
    """The program name of a command word (``/usr/bin/git`` → ``git``); shlex has
    already removed any alias-bypassing backslash (``\\git`` → ``git``)."""
    return token.rsplit("/", 1)[-1]


def _head_index(segment: Sequence[str]) -> int:
    """Index of the command word, past leading ``VAR=value`` and wrapper words."""
    index = 0
    while index < len(segment):
        token = segment[index]
        is_assignment = "=" in token and not token.startswith("-")
        if is_assignment or _basename(token) in _WRAPPERS:
            index += 1
        else:
            break
    return index


def _heredoc_tags(tokens: Sequence[str]) -> list[str]:
    """Terminators of the heredocs a line opens (``<<TAG``, ``<<'TAG'``, ``<<-TAG``)."""
    return [
        tokens[i + 1].lstrip("-")
        for i, word in enumerate(tokens)
        if word == _HEREDOC and i + 1 < len(tokens)
    ]


def _invocations_in_line(tokens: Sequence[str]) -> list[list[str]]:
    found: list[list[str]] = []
    for segment in _segments(tokens):
        start = _head_index(segment)
        if start >= len(segment):
            continue
        head = _basename(segment[start])
        if head == "git":
            found.append(list(segment))
        elif head in _SHELLS and "-c" in segment:
            index = segment.index("-c")
            if index + 1 < len(segment):
                found.extend(git_invocations(segment[index + 1]))
    return found


def git_invocations(command: str) -> list[list[str]]:
    """Every git invocation in a (possibly compound, multi-line) command, as argv lists.

    Heredoc bodies are skipped: a file being WRITTEN that mentions ``git push`` is
    not a push. Backslash continuations are joined first. A line that fails to lex
    (unbalanced quote) is skipped — the substring floor still covers it.
    """
    found: list[list[str]] = []
    pending: list[str] = []  # heredoc terminators still to be consumed
    for line in command.replace("\\\n", " ").splitlines():
        if pending:
            if line.strip() == pending[0]:
                pending.pop(0)
            continue
        try:
            tokens = _tokenize(line)
        except ValueError:
            continue
        found.extend(_invocations_in_line(tokens))
        pending.extend(_heredoc_tags(tokens))
    return found


def git_subcommand(argv: Sequence[str]) -> tuple[str, list[str]]:
    """``(subcommand, args)`` of one git invocation, stepping over global options."""
    index = _head_index(argv) + 1
    while index < len(argv):
        token = argv[index]
        if not token.startswith("-"):
            return token, list(argv[index + 1 :])
        index += 2 if token in _GIT_GLOBAL_WITH_VALUE else 1
    return "", []


# --- git push ---------------------------------------------------------------------


def _destination(refspec: str) -> tuple[str | None, bool]:
    """``(branch-or-glob, forced)`` a refspec writes; branch None for tags/other refs.

    Returns ``("", False)`` for a bare ``HEAD`` (destination follows the current
    branch) so the caller can treat it as an implicit push.
    """
    forced = refspec.startswith("+")
    spec = refspec.lstrip("+")
    dest = spec.split(":", 1)[1] if ":" in spec else spec
    if dest.startswith("refs/heads/"):
        return dest[len("refs/heads/") :], forced
    if dest.startswith("refs/") or dest == "":
        return None, forced
    if dest == "HEAD":
        return "", forced
    return dest, forced


_LONG_PUSH_FLAGS: dict[str, str] = {
    "--force": "force",
    "--force-with-lease": "force",
    "--force-if-includes": "force",
    "--delete": "delete",
    "--dry-run": "dry_run",
    "--all": "everything",
    "--mirror": "everything",
    "--tags": "tags",
}
_SHORT_PUSH_FLAGS: dict[str, str] = {"f": "force", "d": "delete", "n": "dry_run"}


def _long_push_flag(arg: str) -> str | None:
    """The policy-relevant meaning of one ``--long`` push option, if any."""
    if arg.startswith("--force-with-lease="):
        return "force"
    return _LONG_PUSH_FLAGS.get(arg)


def _short_push_flags(cluster: str) -> tuple[set[str], bool]:
    """Meanings in a ``-xyz`` cluster, and whether it ends in ``-o`` (consumes a value)."""
    found: set[str] = set()
    for flag in cluster[1:]:
        if flag == "o":
            return found, True
        if flag in _SHORT_PUSH_FLAGS:
            found.add(_SHORT_PUSH_FLAGS[flag])
    return found, False


def _push_words(args: Sequence[str]) -> tuple[set[str], list[str]]:
    """``(flag meanings, positional words)`` of a push argument list."""
    flags: set[str] = set()
    positional: list[str] = []
    index = 0
    while index < len(args):
        arg = args[index]
        index += 1
        if arg in _PUSH_WITH_VALUE:
            index += 1
        elif arg.startswith("--"):
            meaning = _long_push_flag(arg)
            if meaning:
                flags.add(meaning)
        elif arg.startswith("-"):
            found, takes_value = _short_push_flags(arg)
            flags |= found
            index += takes_value
        else:
            positional.append(arg)
    return flags, positional


def _written_branches(refspecs: Sequence[str], delete: bool) -> tuple[list[str], bool, bool]:
    """``(branches written, any forced, follows HEAD)`` for the refspecs of a push."""
    branches: list[str] = []
    forced = follows_head = False
    for refspec in refspecs:
        if delete:
            branches.append(refspec.lstrip(":").removeprefix("refs/heads/"))
            continue
        dest, plus = _destination(refspec)
        forced |= plus
        if dest == "":
            follows_head = True
        elif dest is not None:
            branches.append(dest)
    return branches, forced, follows_head


def push_spec(args: Sequence[str]) -> PushSpec:
    """Parse ``git push`` arguments into the refs they would write."""
    flags, positional = _push_words(args)
    remote = positional[0] if positional else ""
    if "dry_run" in flags:
        return PushSpec(remote, (), False, False, False, False)
    refspecs = positional[1:]
    deletes = "delete" in flags or any(r.startswith(":") for r in refspecs)
    branches, forced, follows_head = _written_branches(refspecs, deletes)
    implicit = follows_head or not (refspecs or flags & {"delete", "everything", "tags"})
    return PushSpec(
        remote,
        tuple(branches),
        "force" in flags or forced,
        implicit,
        "everything" in flags,
        deletes,
    )


def _first_protected(targets: Sequence[str], protected: Sequence[str]) -> str | None:
    """The first declared protected branch a target (name or glob) matches."""
    for target in targets:
        for name in protected:
            if fnmatch.fnmatch(name, target):
                return name
    return None


def _push_reason(hit: str, spec: PushSpec) -> str:
    if spec.deletes:
        return (
            f"'git push' deletes protected branch '{hit}' ({POLICY}): "
            f"protected branches are never deleted."
        )
    if spec.force:
        return (
            f"'git push' force-updates protected branch '{hit}' ({POLICY}): protected "
            f"history is never rewritten; push a feature branch and land via PR + gate."
        )
    return (
        f"'git push' targets protected branch '{hit}' ({POLICY}): "
        f"push a feature branch and land via PR + gate."
    )


def _push_violation(args: Sequence[str], head: str, protected: Sequence[str]) -> str | None:
    spec = push_spec(args)
    if spec.everything:
        return (
            f"'git push --all/--mirror' pushes every branch, including protected "
            f"'{protected[0]}' ({POLICY}): push the feature branch by name."
        )
    targets = [*spec.destinations, *([head] if spec.implicit else [])]
    hit = _first_protected(targets, protected)
    return _push_reason(hit, spec) if hit is not None else None


# --- local branch rewrites --------------------------------------------------------


def _branch_violation(args: Sequence[str], protected: Sequence[str]) -> str | None:
    flag = next((a for a in args if a in _BRANCH_REWRITE_FLAGS), None)
    if flag is None:
        flag = next(
            (
                a
                for a in args
                if a.startswith("-") and not a.startswith("--") and set(a[1:]) & set("dDfmM")
            ),
            None,
        )
    if flag is None:
        return None
    names = [a for a in args if not a.startswith("-")]
    return _rewrite_reason(f"git branch {flag}", names, protected)


def _switch_violation(sub: str, args: Sequence[str], protected: Sequence[str]) -> str | None:
    flags = {"checkout": ("-B",), "switch": ("-C", "--force-create")}[sub]
    for index, arg in enumerate(args):
        if arg in flags and index + 1 < len(args):
            return _rewrite_reason(f"git {sub} {arg}", [args[index + 1]], protected)
    return None


def _update_ref_violation(args: Sequence[str], protected: Sequence[str]) -> str | None:
    return _rewrite_reason(
        "git update-ref", [a for a in args if a.startswith("refs/heads/")], protected
    )


def _rewrite_reason(label: str, names: Sequence[str], protected: Sequence[str]) -> str | None:
    hit = next(
        (
            n.removeprefix("refs/heads/")
            for n in names
            if n.removeprefix("refs/heads/") in protected
        ),
        None,
    )
    if hit is None:
        return None
    return (
        f"'{label}' deletes/rewrites protected branch '{hit}' ({POLICY}): "
        f"protected branches are never deleted or force-moved locally."
    )


# --- the guard's decision -----------------------------------------------------------


def _lands_on_head(sub: str, args: Sequence[str], head: str) -> bool:
    if sub in _LANDS_ON_HEAD:
        return True
    if sub == "reset":
        return any(a in _RESET_MOVES_HEAD for a in args)
    if sub == "pull":
        positional = [a for a in args if not a.startswith("-")]
        return any(ref != head for ref in positional[1:])
    return False


def _floor_violation(command: str, head: str) -> str | None:
    for needle in ("git commit", "git push"):
        if needle in command:
            return (
                f"'{head}' is a protected branch ({POLICY}): a command mentioning "
                f"'{needle}' is refused here (substring floor) — {COMMIT_HINT}."
            )
    return None


def _ref_violation(
    sub: str, args: Sequence[str], head: str, protected: Sequence[str]
) -> str | None:
    """Reason one git invocation writes a protected ref (from ANY branch), else None."""
    if sub == "push":
        return _push_violation(args, head, protected)
    if sub == "branch":
        return _branch_violation(args, protected)
    if sub in ("checkout", "switch"):
        return _switch_violation(sub, args, protected)
    if sub == "update-ref":
        return _update_ref_violation(args, protected)
    return None


def branch_policy_violation(command: str, head: str, protected: Sequence[str]) -> str | None:
    """Reason ``command`` would violate the protected-branch policy, else None.

    Args:
        command: the shell command about to run.
        head: current branch (``""``/``"HEAD"`` = detached).
        protected: declared ``[collaboration].protected_branches``; empty ⇒ off.
    """
    if not protected:
        return None
    on_protected = head in protected
    for argv in git_invocations(command):
        sub, args = git_subcommand(argv)
        if on_protected and _lands_on_head(sub, args, head):
            return (
                f"'{head}' is a protected branch ({POLICY}): 'git {sub}' would land work "
                f"directly on it — {COMMIT_HINT}."
            )
        reason = _ref_violation(sub, args, head, protected)
        if reason:
            return reason
    return _floor_violation(command, head) if on_protected else None


# --- the gate's decision (08_branch backstop) ------------------------------------------


def direct_commit_violation(
    branch: str, protected: Sequence[str], ahead: int | None, remote_ref: str
) -> str | None:
    """Fail when a protected branch carries commits its remote ref does not.

    Args:
        branch: current branch (``""``/``"HEAD"`` = detached ⇒ not judged).
        protected: declared protected branches; empty ⇒ off.
        ahead: ``git rev-list --count <remote_ref>..HEAD``; None when no remote ref
            exists to compare against (cannot judge ⇒ pass; the platform is the backstop).
        remote_ref: the ref compared against, for the message.
    """
    if branch not in protected or not ahead:
        return None
    return (
        f"DIRECT COMMITS ON PROTECTED BRANCH: '{branch}' has {ahead} commit(s) not on "
        f"{remote_ref} — work lands on protected branches only via PR + gate ({POLICY}). "
        f"Move them: git switch -c feat/<name> && git branch -f {branch} {remote_ref}."
    )
