"""Alias resolution and alias-planting refusal (PR #169 review, ADR-0058).

Exact values throughout: a git alias is the cheapest bypass of a command guard,
so every seam here is pinned.
"""

import pytest

from meta_harness.trunk_aliases import (
    GIT_BUILTINS,
    alias_floor,
    alias_write_violation,
    inline_aliases,
    resolve_alias,
)

POLICY = "trunk-based policy, ADR-0058"

# --- inline aliases stated on the command line ---------------------------------


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["git", "-c", "alias.p=push", "p"], {"p": "push"}),
        (["git", "-calias.p=push", "p"], {"p": "push"}),
        (["git", "-c", "Alias.P=push", "P"], {"P": "push"}),
        (["git", "--config-env=alias.p=VAR", "p"], {"p": "!<env VAR>"}),
        (["GIT_CONFIG_KEY_0=alias.p", "GIT_CONFIG_VALUE_0=push", "git", "p"], {"p": "push"}),
        (["GIT_CONFIG_KEY_0=alias.p", "git", "p"], {"p": ""}),
        (["GIT_CONFIG_PARAMETERS='alias.p=push'", "git", "p"], {"p": "push"}),
        (
            ["GIT_CONFIG_PARAMETERS=alias.p=push 'alias.l=log'", "git", "p"],
            {"p": "push", "l": "log"},
        ),
        (["GIT_CONFIG_PARAMETERS='oops", "git", "p"], {"?": "!<unparseable>"}),
        (["GIT_CONFIG_PARAMETERS=noequals", "git", "p"], {}),
        (["git", "-c", "user.email=x@y", "commit"], {}),
        (["git", "-c", "commit"], {}),  # -c without k=v: nothing stated
        (["git", "--no-pager", "log"], {}),
        (["git", "-c"], {}),
    ],
)
def test_inline_aliases(argv: list[str], expected: dict[str, str]) -> None:
    assert inline_aliases(argv) == expected


# --- resolution -----------------------------------------------------------------


def test_alias_expands_to_the_real_subcommand() -> None:
    assert resolve_alias("p", ["origin", "main"], {"p": "push"}) == (
        "push",
        ["origin", "main"],
        None,
    )
    assert resolve_alias("p", ["origin"], {"p": "push -u"}) == ("push", ["-u", "origin"], None)


def test_chained_aliases_expand_fully() -> None:
    aliases = {"p": "pp", "pp": "push --force-with-lease"}
    assert resolve_alias("p", ["o", "main"], aliases) == (
        "push",
        ["--force-with-lease", "o", "main"],
        None,
    )


def test_builtins_are_never_shadowed() -> None:
    # git ignores alias.commit; so must the guard (else `alias.commit=log` hides commits).
    assert resolve_alias("commit", ["-m", "x"], {"commit": "log"}) == ("commit", ["-m", "x"], None)
    assert "commit" in GIT_BUILTINS and "push" in GIT_BUILTINS and "update-ref" in GIT_BUILTINS


def test_unknown_word_is_left_alone() -> None:
    assert resolve_alias("foo", ["x"], {}) == ("foo", ["x"], None)


def test_shell_alias_is_opaque() -> None:
    assert resolve_alias("p", ["x"], {"p": "!git push origin main"}) == (
        "p",
        ["x"],
        "p = !git push origin main",
    )


def test_unparseable_empty_and_cyclic_aliases_are_opaque() -> None:
    assert resolve_alias("p", [], {"p": "push 'x"}) == ("p", [], "p = push 'x (unparseable)")
    assert resolve_alias("p", [], {"p": ""}) == ("p", [], "p = (empty)")
    assert resolve_alias("a", [], {"a": "b", "b": "a"}) == ("a", [], "a = b (cyclic)")


def test_alias_depth_is_bounded() -> None:
    chain = {f"a{i}": f"a{i + 1}" for i in range(10)} | {"a10": "log"}
    assert resolve_alias("a0", [], chain) == ("a8", [], "a8 = a9 (cyclic)")


# --- planting an alias ------------------------------------------------------------

CONFIG_REASON = (
    "'git config' would set alias 'p' = '{value}', which runs a branch-writing command "
    f"({POLICY}): aliases cannot be used to dodge the branch guard."
)


@pytest.mark.parametrize(
    ("args", "value"),
    [
        (["alias.p", "push"], "push"),
        (["--global", "alias.p", "push"], "push"),
        (["--system", "alias.p", "push"], "push"),
        (["--worktree", "alias.p", "push"], "push"),
        (["--local", "alias.p", "push --force-with-lease"], "push --force-with-lease"),
        (["-f", "~/.gitconfig", "alias.p", "push"], "push"),
        (["--file", ".git/config", "alias.p", "push"], "push"),
        (["--add", "alias.p", "commit -m x"], "commit -m x"),
        (["--replace-all", "alias.p", "merge --no-ff"], "merge --no-ff"),
        (["alias.p", "rebase -i"], "rebase -i"),
        (["alias.p", "reset --hard"], "reset --hard"),
        (["alias.p", "branch -D"], "branch -D"),
        (["alias.p", "update-ref"], "update-ref"),
        (["alias.p", "symbolic-ref HEAD"], "symbolic-ref HEAD"),
        (["alias.p", "!sh -c 'echo'"], "!sh -c 'echo'"),  # shell alias: opaque ⇒ refused
        (["Alias.p", "push"], "push"),
    ],
)
def test_config_write_of_a_branch_writing_alias_is_refused(args: list[str], value: str) -> None:
    argv = ["git", "config", *args]
    assert alias_write_violation(argv, "config", args) == CONFIG_REASON.format(value=value)


@pytest.mark.parametrize(
    "args",
    [
        ["alias.lg", "log --oneline --graph"],
        ["alias.st", "status --branch"],  # `--branch` is an option, not the verb
        ["alias.co", "checkout"],
        ["--get", "alias.p"],
        ["--get-all", "alias.p"],
        ["--get-regexp", "^alias\\."],
        ["--unset", "alias.p"],
        ["--unset-all", "alias.p"],
        ["--list"],
        ["-l"],
        ["alias.p"],  # no value: a read
        ["user.email", "x@y"],
        ["core.editor", "vim"],
        [],
    ],
)
def test_other_config_invocations_are_allowed(args: list[str]) -> None:
    assert alias_write_violation(["git", "config", *args], "config", args) is None


def test_non_config_subcommands_without_inline_aliases_are_allowed() -> None:
    assert alias_write_violation(["git", "log"], "log", []) is None
    assert alias_write_violation(["git", "-c", "user.email=x", "commit"], "commit", []) is None


INLINE_REASON = (
    "inline config plants alias '{name}' = '{value}', which runs a branch-writing command "
    f"({POLICY}): aliases cannot be used to dodge the branch guard."
)


@pytest.mark.parametrize(
    ("argv", "name", "value"),
    [
        (["git", "-c", "alias.p=push", "p", "origin", "feat/x"], "p", "push"),
        (["git", "-calias.p=push", "p"], "p", "push"),
        (["GIT_CONFIG_KEY_0=alias.p", "GIT_CONFIG_VALUE_0=push", "git", "p"], "p", "push"),
        (["GIT_CONFIG_PARAMETERS='alias.p=commit'", "git", "p"], "p", "commit"),
        (["git", "--config-env=alias.p=VAR", "p"], "p", "!<env VAR>"),
        (["git", "-c", "alias.x=log", "-c", "alias.p=merge", "p"], "p", "merge"),
    ],
)
def test_inline_alias_that_writes_branches_is_refused(
    argv: list[str], name: str, value: str
) -> None:
    assert alias_write_violation(argv, "p", []) == INLINE_REASON.format(name=name, value=value)


def test_inline_alias_that_only_reads_is_allowed() -> None:
    assert alias_write_violation(["git", "-c", "alias.l=log", "l"], "l", []) is None


# --- the floor --------------------------------------------------------------------

FLOOR_REASON = (
    f"command mentions git alias/config together with a branch-writing verb ({POLICY}): "
    "editing aliases that push/commit/merge/rebase/reset/branch is refused (floor) — run it "
    "outside the guard if genuinely intended."
)


@pytest.mark.parametrize(
    "command",
    [
        "echo '[alias] p = push' >> .git/config",
        "printf '[alias]\\n\\tp = push\\n' >> ~/.gitconfig",
        "sed -i 's/^/alias.p=push/' ~/.gitconfig",
        "cat .git/config | grep push",
        "git config --get alias.p && git push",
    ],
)
def test_floor_refuses_alias_or_config_mentions_with_a_verb(command: str) -> None:
    assert alias_floor(command) == FLOOR_REASON


@pytest.mark.parametrize(
    "command",
    [
        "git config --get alias.lg",
        "grep -n 'alias\\.' README.md",
        "cat .git/config",
        "sed -n 1,5p ~/.gitconfig",
        "git push origin feat/x",
        "echo pushing",
        "",
    ],
)
def test_floor_is_silent_without_both_ingredients(command: str) -> None:
    assert alias_floor(command) is None


# --- mutation-driven seams --------------------------------------------------------


def test_assignment_looking_argument_is_not_a_dash_c_option() -> None:
    assert inline_aliases(["git", "log", "alias.p=push"]) == {}


def test_dash_c_as_the_last_word_states_nothing_after_it() -> None:
    assert inline_aliases(["git", "-c", "alias.p=push"]) == {"p": "push"}


def test_values_containing_equals_split_on_the_first_one() -> None:
    assert inline_aliases(["git", "-c", "alias.p=log --format=%h", "p"]) == {"p": "log --format=%h"}
    assert inline_aliases(["git", "-calias.p=log --format=%h", "p"]) == {"p": "log --format=%h"}
    assert inline_aliases(["GIT_CONFIG_PARAMETERS='alias.p=log --format=%h'", "git", "p"]) == {
        "p": "log --format=%h"
    }
    assert inline_aliases(
        ["GIT_CONFIG_KEY_0=alias.p", "GIT_CONFIG_VALUE_0=push -o a=b", "git", "p"]
    ) == {"p": "push -o a=b"}


@pytest.mark.parametrize(
    "command",
    [
        "printf '[alias] p = push' > cfg",  # the [alias] section header alone
        "echo push >> ~/.gitconfig",  # the global config file alone
    ],
)
def test_floor_mentions_are_each_sufficient(command: str) -> None:
    assert alias_floor(command) == FLOOR_REASON
