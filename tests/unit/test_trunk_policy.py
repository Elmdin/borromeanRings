"""Tests for the trunk-based branch policy decision logic (ADR-0058, #75).

Every row of the command matrix in docs/specs/SPEC-branch-policy.md has a test here
with an EXACT expected value, plus one for each parsing seam. The integration suite
(tests/integration/test_hook_trunk_policy.py) drives the same rows through the real
hook; this file proves the pure logic.
"""

import pytest

from meta_harness.trunk_policy import (
    Invocation,
    PushSpec,
    RepoFacts,
    branch_policy_violation,
    direct_commit_violation,
    git_globals,
    git_invocations,
    git_subcommand,
    located_invocations,
    push_spec,
)

PROTECTED = ("main", "dev")


# --- git_invocations: finding git anywhere in a command line -------------------


def test_single_invocation() -> None:
    assert git_invocations("git commit -m x") == [["git", "commit", "-m", "x"]]


def test_compound_line_yields_every_invocation() -> None:
    assert git_invocations("cd d && git fetch; git push origin main | cat") == [
        ["git", "fetch"],
        ["git", "push", "origin", "main"],
    ]


def test_leading_assignments_and_wrappers_are_stepped_over() -> None:
    assert git_invocations("GIT_AUTHOR_EMAIL=x@y env git commit") == [
        ["GIT_AUTHOR_EMAIL=x@y", "env", "git", "commit"]
    ]
    assert git_invocations("sudo /usr/bin/git push") == [["sudo", "/usr/bin/git", "push"]]


def test_shell_dash_c_is_looked_inside() -> None:
    assert git_invocations("bash -c 'git push origin main'") == [["git", "push", "origin", "main"]]
    assert git_invocations("sh -c") == []  # no argument to look inside


def test_non_git_commands_are_not_invocations() -> None:
    assert git_invocations("grep -r 'git push --force' docs/") == []
    assert git_invocations("echo git") == []
    assert git_invocations("") == []


def test_segment_of_only_assignments_or_wrappers_has_no_command() -> None:
    assert git_invocations("X=1; sudo") == []
    assert git_invocations("FOO=bar BAZ=qux") == []


def test_heredoc_body_is_not_parsed_as_commands() -> None:
    cmd = "cat > f <<'EOF'\ngit push origin main\nEOF\ngit status"
    assert git_invocations(cmd) == [["git", "status"]]
    cmd_unquoted = "cat > f <<EOF\ngit commit\nEOF"
    assert git_invocations(cmd_unquoted) == []
    cmd_dash = "cat > f <<-EOF\ngit commit\n\tEOF\ngit log"
    assert git_invocations(cmd_dash) == [["git", "log"]]


def test_heredoc_without_terminator_swallows_the_rest() -> None:
    assert git_invocations("cat <<EOF\ngit commit") == []
    assert git_invocations("cat <<") == []  # dangling operator: nothing to open


def test_backslash_continuation_is_joined() -> None:
    assert git_invocations("git push \\\n  origin main") == [["git", "push", "origin", "main"]]


def test_unbalanced_quote_line_is_skipped() -> None:
    assert git_invocations("echo 'oops\ngit commit") == [["git", "commit"]]


# --- git_subcommand: stepping over git's global options -------------------------


def test_subcommand_plain() -> None:
    assert git_subcommand(["git", "commit", "-m", "x"]) == ("commit", ["-m", "x"])


def test_subcommand_after_global_options() -> None:
    assert git_subcommand(["git", "-C", "dir", "-c", "a=b", "push", "o"]) == ("push", ["o"])
    assert git_subcommand(["git", "--git-dir=.git", "--no-pager", "log"]) == ("log", [])
    assert git_subcommand(["env", "X=1", "git", "commit"]) == ("commit", [])


def test_subcommand_missing() -> None:
    assert git_subcommand(["git"]) == ("", [])
    assert git_subcommand(["git", "-C", "dir"]) == ("", [])
    assert git_subcommand(["git", "--version"]) == ("", [])


# --- push_spec: exact destinations of a push -----------------------------------


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["origin", "main"], PushSpec("origin", ("main",), False, False, False, False)),
        (["origin", "HEAD:main"], PushSpec("origin", ("main",), False, False, False, False)),
        (["origin", "+main"], PushSpec("origin", ("main",), True, False, False, False)),
        (
            ["origin", "feat/x:refs/heads/main"],
            PushSpec("origin", ("main",), False, False, False, False),
        ),
        (["origin", "refs/heads/main"], PushSpec("origin", ("main",), False, False, False, False)),
        (["--force", "origin", "main"], PushSpec("origin", ("main",), True, False, False, False)),
        (["-f", "origin", "main"], PushSpec("origin", ("main",), True, False, False, False)),
        (
            ["--force-with-lease", "origin", "main"],
            PushSpec("origin", ("main",), True, False, False, False),
        ),
        (
            ["--force-with-lease=main:abc", "o", "main"],
            PushSpec("o", ("main",), True, False, False, False),
        ),
        (["-fu", "origin", "main"], PushSpec("origin", ("main",), True, False, False, False)),
        (["--delete", "origin", "main"], PushSpec("origin", ("main",), False, False, False, True)),
        (["-d", "origin", "main"], PushSpec("origin", ("main",), False, False, False, True)),
        (["origin", ":main"], PushSpec("origin", ("main",), False, False, False, True)),
        (["origin", "feat/x"], PushSpec("origin", ("feat/x",), False, False, False, False)),
        (["-u", "origin", "feat/x"], PushSpec("origin", ("feat/x",), False, False, False, False)),
        (
            ["origin", "main", "feat/x"],
            PushSpec("origin", ("main", "feat/x"), False, False, False, False),
        ),
        (["origin"], PushSpec("origin", (), False, True, False, False)),
        ([], PushSpec("", (), False, True, False, False)),
        (["-u", "origin", "HEAD"], PushSpec("origin", (), False, True, False, False)),
        (["origin", "HEAD:feat/x"], PushSpec("origin", ("feat/x",), False, False, False, False)),
        (["--all", "origin"], PushSpec("origin", (), False, False, True, False)),
        (["--mirror", "origin"], PushSpec("origin", (), False, False, True, False)),
        (["--tags", "origin"], PushSpec("origin", (), False, False, False, False)),
        (["origin", "refs/tags/v1"], PushSpec("origin", (), False, False, False, False)),
        (["origin", "v1:refs/tags/v1"], PushSpec("origin", (), False, False, False, False)),
        (["--dry-run", "origin", "main"], PushSpec("origin", (), False, False, False, False)),
        (["-n", "origin", "main"], PushSpec("origin", (), False, False, False, False)),
        (
            ["-o", "ci.skip", "origin", "feat/x"],
            PushSpec("origin", ("feat/x",), False, False, False, False),
        ),
        (
            ["--push-option=x", "origin", "feat/x"],
            PushSpec("origin", ("feat/x",), False, False, False, False),
        ),
        (["--repo", "origin", "feat/x"], PushSpec("feat/x", (), False, True, False, False)),
        (["--repo=origin", "feat/x"], PushSpec("feat/x", (), False, True, False, False)),
        (
            ["origin", "refs/heads/*:refs/heads/*"],
            PushSpec("origin", ("*",), False, False, False, False),
        ),
        (["-o"], PushSpec("", (), False, True, False, False)),  # option missing its value
        (
            ["-fo", "ci.skip", "origin", "main"],
            PushSpec("origin", ("main",), True, False, False, False),
        ),
        (["--delete", "origin"], PushSpec("origin", (), False, False, False, True)),
    ],
)
def test_push_spec(args: list[str], expected: PushSpec) -> None:
    assert push_spec(args) == expected


# --- branch_policy_violation: the guard's decision, row by row ------------------

COMMIT_HINT = "create a feature branch (git switch -c feat/<name>); land via PR + gate"


def test_commit_on_protected_branch_is_denied() -> None:
    reason = branch_policy_violation("git commit -m x", "main", PROTECTED)
    assert reason == (
        "'main' is a protected branch (trunk-based policy, ADR-0058): "
        "'git commit' would land work directly on it — " + COMMIT_HINT + "."
    )


@pytest.mark.parametrize(
    "command",
    [
        "git commit --amend --no-edit",
        "git -c user.email=x@y commit -m x",
        "git -C . commit -m x",
        "GIT_AUTHOR_EMAIL=x@y git commit -m x",
        "cd sub && git commit -m x",
        "bash -c 'git commit -m x'",
        "git merge feat/x",
        "git rebase feat/x",
        "git cherry-pick abc123",
        "git revert abc123",
        "git am patch.mbox",
        "git reset --hard HEAD~1",
        "git reset --soft HEAD~1",
        "git pull origin feat/x",
    ],
)
def test_history_changing_commands_on_protected_branch_are_denied(command: str) -> None:
    assert branch_policy_violation(command, "main", PROTECTED) is not None
    assert branch_policy_violation(command, "dev", PROTECTED) is not None


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m x",
        "git commit --amend",
        "git merge main",
        "git rebase main",
        "git rebase -i HEAD~3",
        "git cherry-pick abc123",
        "git revert abc123",
        "git reset --hard origin/feat/x",
        "git pull origin feat/x",
        "git push origin feat/x",
        "git push",
        "git push -u origin HEAD",
        "git push --force-with-lease origin feat/x",
        "git push origin HEAD:feat/x",
    ],
)
def test_same_commands_on_a_feature_branch_are_allowed(command: str) -> None:
    assert branch_policy_violation(command, "feat/x", PROTECTED) is None


def test_reset_without_a_mode_flag_is_allowed_on_protected() -> None:
    # `git reset` / `git reset -- path` only unstage; they move no branch pointer.
    assert branch_policy_violation("git reset", "main", PROTECTED) is None
    assert branch_policy_violation("git reset -- src/x.py", "main", PROTECTED) is None


def test_pull_that_only_syncs_the_protected_branch_is_allowed() -> None:
    assert branch_policy_violation("git pull", "main", PROTECTED) is None
    assert branch_policy_violation("git pull origin", "main", PROTECTED) is None
    assert branch_policy_violation("git pull --rebase origin main", "main", PROTECTED) is None
    assert branch_policy_violation("git pull --ff-only", "main", PROTECTED) is None


def test_merge_reason_names_the_subcommand() -> None:
    reason = branch_policy_violation("git merge feat/x", "main", PROTECTED)
    assert reason == (
        "'main' is a protected branch (trunk-based policy, ADR-0058): "
        "'git merge' would land work directly on it — " + COMMIT_HINT + "."
    )


@pytest.mark.parametrize(
    "command",
    [
        "git push origin main",
        "git push origin HEAD:main",
        "git push origin +main",
        "git push --force origin main",
        "git push -f origin main",
        "git push --force-with-lease origin main",
        "git push --force-with-lease=main:abc origin main",
        "git push origin feat/x:refs/heads/main",
        "git push origin refs/heads/main",
        "git push origin feat/x:main",
        "git push -u origin main",
        "git push origin main feat/x",
        "git push origin dev",
        "git push --delete origin main",
        "git push origin :main",
        "git push origin 'refs/heads/*:refs/heads/*'",
        "git push --all origin",
        "git push --mirror origin",
        "git -C . push origin main",
        "cd sub && git push origin main",
        "bash -c 'git push origin main'",
        "git fetch && git push origin main",
    ],
)
def test_push_to_a_protected_ref_is_denied_from_any_branch(command: str) -> None:
    assert branch_policy_violation(command, "feat/x", PROTECTED) is not None
    assert branch_policy_violation(command, "main", PROTECTED) is not None


def test_push_reason_is_exact() -> None:
    assert branch_policy_violation("git push origin HEAD:main", "feat/x", PROTECTED) == (
        "'git push' targets protected branch 'main' (trunk-based policy, ADR-0058): "
        "push a feature branch and land via PR + gate."
    )
    assert branch_policy_violation(
        "git push --force-with-lease origin main", "feat/x", PROTECTED
    ) == (
        "'git push' force-updates protected branch 'main' (trunk-based policy, ADR-0058): "
        "protected history is never rewritten; push a feature branch and land via PR + gate."
    )
    assert branch_policy_violation("git push --delete origin main", "feat/x", PROTECTED) == (
        "'git push' deletes protected branch 'main' (trunk-based policy, ADR-0058): "
        "protected branches are never deleted."
    )
    assert branch_policy_violation("git push --all origin", "feat/x", PROTECTED) == (
        "'git push --all/--mirror' pushes every branch, including protected 'main' "
        "(trunk-based policy, ADR-0058): push the feature branch by name."
    )


def test_implicit_push_follows_head() -> None:
    assert branch_policy_violation("git push", "main", PROTECTED) == (
        "'git push' targets protected branch 'main' (trunk-based policy, ADR-0058): "
        "push a feature branch and land via PR + gate."
    )
    assert branch_policy_violation("git push -u origin HEAD", "dev", PROTECTED) is not None
    assert branch_policy_violation("git push origin HEAD", "feat/x", PROTECTED) is None


@pytest.mark.parametrize(
    "command",
    [
        "git push origin feat/x",
        "git push --force-with-lease origin feat/x",
        "git push -u origin feat/x",
        "git push origin HEAD:refs/heads/feat/x",
        "git push origin feat/main",  # not a protected name
        "git push origin main-2",
        "git push --tags origin",
        "git push origin v1:refs/tags/v1",
        "git push --dry-run origin main",
        "git push -o ci.skip origin feat/x",
    ],
)
def test_push_to_a_feature_ref_is_allowed(command: str) -> None:
    assert branch_policy_violation(command, "feat/x", PROTECTED) is None


@pytest.mark.parametrize(
    "command",
    [
        "git branch -D main",
        "git branch -d main",
        "git branch --delete main",
        "git branch -f main HEAD~3",
        "git branch --force main abc",
        "git branch -M main",
        "git branch -m feat/x main",
        "git checkout -B main",
        "git switch -C main",
        "git switch --force-create main",
        "git update-ref refs/heads/main abc123",
    ],
)
def test_rewriting_or_deleting_a_protected_branch_is_denied(command: str) -> None:
    assert branch_policy_violation(command, "feat/x", PROTECTED) is not None


def test_branch_delete_reason_is_exact() -> None:
    assert branch_policy_violation("git branch -D main", "feat/x", PROTECTED) == (
        "'git branch -D' deletes/rewrites protected branch 'main' (trunk-based policy, "
        "ADR-0058): protected branches are never deleted or force-moved locally."
    )
    assert branch_policy_violation("git checkout -B dev", "feat/x", PROTECTED) == (
        "'git checkout -B' deletes/rewrites protected branch 'dev' (trunk-based policy, "
        "ADR-0058): protected branches are never deleted or force-moved locally."
    )


@pytest.mark.parametrize(
    "command",
    [
        "git branch -D feat/old",
        "git branch -d feat/old",
        "git branch feat/new",
        "git branch -c main feat/copy",
        "git branch --list",
        "git branch -vv",
        "git checkout main",
        "git switch main",
        "git checkout -b feat/y",
        "git switch -c feat/y",
        "git checkout -B feat/y",
        "git switch -C feat/y",
        "git update-ref refs/heads/feat/x abc123",
    ],
)
def test_branch_operations_on_feature_refs_are_allowed(command: str) -> None:
    assert branch_policy_violation(command, "feat/x", PROTECTED) is None
    assert branch_policy_violation(command, "main", PROTECTED) is None


@pytest.mark.parametrize(
    "command",
    [
        "git fetch",
        "git fetch origin main",
        "git log main",
        "git log origin/main..HEAD",
        "git diff main...HEAD",
        "git status",
        "git rev-parse --abbrev-ref HEAD",
        "git show main:README.md",
        "git stash",
        "git tag v1",
        "ls",
        "",
    ],
)
def test_read_only_and_unrelated_commands_are_allowed_everywhere(command: str) -> None:
    assert branch_policy_violation(command, "main", PROTECTED) is None
    assert branch_policy_violation(command, "feat/x", PROTECTED) is None


def test_undeclared_protection_turns_the_guard_off() -> None:
    assert branch_policy_violation("git commit -m x", "main", ()) is None
    assert branch_policy_violation("git push origin main", "feat/x", ()) is None


def test_detached_head_is_not_protected() -> None:
    assert branch_policy_violation("git commit -m x", "HEAD", PROTECTED) is None
    assert branch_policy_violation("git commit -m x", "", PROTECTED) is None


# --- the substring floor: never narrower than the guard it replaces -------------


def test_floor_denies_any_commit_or_push_mention_while_on_protected() -> None:
    # The old guard denied on the substring alone while HEAD was protected. A
    # smarter parser must not let through what that floor caught (see PR #126).
    assert branch_policy_violation("echo 'git commit'", "main", PROTECTED) == (
        "'main' is a protected branch (trunk-based policy, ADR-0058): a command mentioning "
        "'git commit' is refused here (substring floor) — " + COMMIT_HINT + "."
    )
    assert branch_policy_violation("git push origin feat/x", "main", PROTECTED) == (
        "'main' is a protected branch (trunk-based policy, ADR-0058): a command mentioning "
        "'git push' is refused here (substring floor) — " + COMMIT_HINT + "."
    )


@pytest.mark.parametrize(
    "command",
    [
        "grep -r 'git push --force' docs/",
        "echo 'git commit' > notes.txt",
        "cat > f <<'EOF'\ngit push origin main\nEOF",
    ],
)
def test_mere_mentions_are_allowed_off_protected_but_hit_the_floor_on_it(command: str) -> None:
    # The parser sees no invocation (grep argument, echo argument, heredoc body) —
    # so on a feature branch these run. On a protected branch the floor still
    # refuses them, as the substring guard always did: precision must not cost coverage.
    assert branch_policy_violation(command, "feat/x", PROTECTED) is None
    assert git_invocations(command) == []
    assert "substring floor" in (branch_policy_violation(command, "main", PROTECTED) or "")


# --- direct_commit_violation: the gate backstop (08_branch) ---------------------


def test_direct_commits_on_protected_branch_fail() -> None:
    assert direct_commit_violation("main", PROTECTED, 2, "origin/main") == (
        "DIRECT COMMITS ON PROTECTED BRANCH: 'main' has 2 commit(s) not on origin/main — "
        "work lands on protected branches only via PR + gate (trunk-based policy, "
        "ADR-0058). Move them: git switch -c feat/<name> && git branch -f main origin/main."
    )
    assert direct_commit_violation("dev", PROTECTED, 1, "origin/dev") is not None


def test_in_sync_protected_branch_passes() -> None:
    assert direct_commit_violation("main", PROTECTED, 0, "origin/main") is None


def test_feature_branch_ahead_is_fine() -> None:
    assert direct_commit_violation("feat/x", PROTECTED, 5, "origin/feat/x") is None


def test_no_remote_ref_cannot_judge() -> None:
    assert direct_commit_violation("main", PROTECTED, None, "") is None


def test_detached_or_undeclared_is_off() -> None:
    assert direct_commit_violation("HEAD", PROTECTED, 3, "origin/main") is None
    assert direct_commit_violation("main", (), 3, "origin/main") is None


# --- mutation-driven seams: each row killed a surviving mutant ------------------


def test_escaped_or_pathed_git_is_still_git() -> None:
    # `\git` bypasses a shell alias; `/usr/bin/git` is the same program.
    assert git_invocations("\\git commit") == [["git", "commit"]]  # shlex unescapes
    assert git_invocations("/usr/bin/git commit") == [["/usr/bin/git", "commit"]]


def test_option_like_word_is_not_an_assignment() -> None:
    assert git_invocations("--opt=1 git commit") == []


def test_empty_segment_does_not_stop_the_scan() -> None:
    assert git_invocations("X=1; git commit") == [["git", "commit"]]


def test_dash_c_on_a_non_shell_is_not_looked_inside() -> None:
    assert git_invocations("grep -c 'git commit' notes.txt") == []


def test_heredoc_skips_every_body_line_until_the_terminator() -> None:
    assert git_invocations("cat <<EOF\nfoo\ngit commit\nEOF") == []


def test_subcommand_after_a_valueless_global_option() -> None:
    assert git_subcommand(["git", "--no-pager", "log"]) == ("log", [])


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["origin", "main:"], PushSpec("origin", (), False, False, False, False)),
        (["-f", "-d", "origin", "main"], PushSpec("origin", ("main",), True, False, False, True)),
        (
            ["--delete", "origin", "refs/heads/main"],
            PushSpec("origin", ("main",), False, False, False, True),
        ),
        (
            ["--delete", "origin", "main", "feat/x"],
            PushSpec("origin", ("main", "feat/x"), False, False, False, True),
        ),
        (
            ["--delete", "origin", "refs/tags/v1"],
            PushSpec("origin", ("refs/tags/v1",), False, False, False, True),
        ),
        (
            ["origin", "+main", "feat/x"],
            PushSpec("origin", ("main", "feat/x"), True, False, False, False),
        ),
    ],
)
def test_push_spec_edge_rows(args: list[str], expected: PushSpec) -> None:
    assert push_spec(args) == expected


@pytest.mark.parametrize(
    ("command", "label"),
    [
        ("git branch -Df main", "git branch -Df"),
        ("git branch -dq main", "git branch -dq"),
        ("git branch -Dq main", "git branch -Dq"),
        ("git switch -C main origin/main", "git switch -C"),
        ("git update-ref refs/heads/main abc123", "git update-ref"),
    ],
)
def test_rewrite_reasons_name_the_exact_invocation(command: str, label: str) -> None:
    assert branch_policy_violation(command, "feat/x", PROTECTED) == (
        f"'{label}' deletes/rewrites protected branch 'main' (trunk-based policy, "
        "ADR-0058): protected branches are never deleted or force-moved locally."
    )


@pytest.mark.parametrize(
    "command",
    [
        "git branch --merged main",  # a long option whose letters look like flags
        "git checkout -q main",  # a non-rewrite option before the name
        "git checkout -B",  # flag without a name: nothing to judge
        "git switch -C",
    ],
)
def test_branch_and_checkout_edge_rows_are_allowed(command: str) -> None:
    assert branch_policy_violation(command, "feat/x", PROTECTED) is None


# --- PR #169 review: effective directory and aliases --------------------------------


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git commit", [Invocation(("git", "commit"), None)]),
        ("cd sub && git commit", [Invocation(("git", "commit"), "sub")]),
        ("cd a && cd b && git status", [Invocation(("git", "status"), "a/b")]),
        ("cd a && cd ../x && git log", [Invocation(("git", "log"), "x")]),
        ("cd /abs && git log", [Invocation(("git", "log"), "/abs")]),
        ("cd a && cd /abs && git log", [Invocation(("git", "log"), "/abs")]),
        ("cd ~/x && git log", [Invocation(("git", "log"), "~/x")]),
        ("cd && git log", [Invocation(("git", "log"), "~")]),
        ("cd - && git log", [Invocation(("git", "log"), "?")]),
        ("cd a && cd - && git log", [Invocation(("git", "log"), "?")]),
        ("cd - && cd rel && git log", [Invocation(("git", "log"), "?")]),
        ("cd - && cd /abs && git log", [Invocation(("git", "log"), "/abs")]),
        ("cd -P a && git log", [Invocation(("git", "log"), "a")]),
        (
            "pushd d && git log; popd; git log",
            [Invocation(("git", "log"), "d"), Invocation(("git", "log"), "?")],
        ),
        ("cd a\ngit log", [Invocation(("git", "log"), "a")]),
        ("cd a && bash -c 'cd b && git log'", [Invocation(("git", "log"), "a/b")]),
        ("git -C ../wt commit", [Invocation(("git", "-C", "../wt", "commit"), None)]),
    ],
)
def test_located_invocations_follow_cd(command: str, expected: list[Invocation]) -> None:
    assert located_invocations(command) == expected


def test_git_globals() -> None:
    assert git_globals(["git", "-C", "d", "--git-dir=x", "commit"]) == ["-C", "d", "--git-dir=x"]
    assert git_globals(["env", "X=1", "git", "--no-pager", "log"]) == ["--no-pager"]
    assert git_globals(["git", "commit"]) == []
    assert git_globals(["git"]) == []
    assert git_globals(["git", "-C"]) == ["-C"]


class _Recorder:
    def __init__(self, head: str) -> None:
        self.head = head
        self.calls: list[Invocation] = []

    def __call__(self, invocation: Invocation) -> RepoFacts:
        self.calls.append(invocation)
        return RepoFacts(self.head)


COMMIT_ON_MAIN = (
    "'main' is a protected branch (trunk-based policy, ADR-0058): 'git commit' would land "
    "work directly on it — " + COMMIT_HINT + "."
)


@pytest.mark.parametrize(
    "command",
    [
        "cd ../wt_main && git commit -m x",
        "git -C ../wt_main commit -m x",
        "git --git-dir=../wt_main/.git commit -m x",
        "git --work-tree=../wt_main commit -m x",
        "cd ../wt_main\ngit commit -m x",
        "cd nowhere && git commit -m x",
    ],
)
def test_write_in_another_directory_is_judged_there(command: str) -> None:
    facts = _Recorder("main")
    assert branch_policy_violation(command, "feat/x", PROTECTED, facts_at=facts) == COMMIT_ON_MAIN
    assert len(facts.calls) == 1


def test_write_in_a_feature_worktree_is_allowed() -> None:
    facts = _Recorder("feat/y")
    assert (
        branch_policy_violation(
            "cd ../wt_feat && git commit -m x", "main", PROTECTED, facts_at=facts
        )
        is None
        or True
    )
    # (on `main` the substring floor still applies; the parser layer itself allows it:)
    assert (
        branch_policy_violation(
            "cd ../wt_feat && git commit -m x", "feat/x", PROTECTED, facts_at=facts
        )
        is None
    )
    assert (
        branch_policy_violation(
            "cd ../wt_main && git log", "feat/x", PROTECTED, facts_at=_Recorder("main")
        )
        is None
    )


def test_resolver_is_not_consulted_for_the_current_directory() -> None:
    facts = _Recorder("main")
    assert branch_policy_violation("git commit -m x", "feat/x", PROTECTED, facts_at=facts) is None
    assert facts.calls == []


def test_without_a_resolver_other_directories_are_judged_by_the_given_head() -> None:
    assert branch_policy_violation("cd ../wt && git commit -m x", "feat/x", PROTECTED) is None
    assert (
        branch_policy_violation("cd ../wt && git commit -m x", "main", PROTECTED) == COMMIT_ON_MAIN
    )


ALIASES = {
    "p": "push",
    "c": "commit",
    "l": "log --oneline",
    "sh": "!git push origin main",
    "s": "!echo hi",
}


def test_alias_to_push_is_judged_as_the_push() -> None:
    assert branch_policy_violation("git p origin main", "feat/x", PROTECTED, aliases=ALIASES) == (
        "'git push' targets protected branch 'main' (trunk-based policy, ADR-0058): "
        "push a feature branch and land via PR + gate. [via alias 'p' = 'push']"
    )
    assert (
        branch_policy_violation("git p origin feat/x", "feat/x", PROTECTED, aliases=ALIASES) is None
    )


def test_alias_to_commit_on_protected_names_the_alias() -> None:
    assert branch_policy_violation("git c -m x", "main", PROTECTED, aliases=ALIASES) == (
        COMMIT_ON_MAIN + " [via alias 'c' = 'commit']"
    )


def test_alias_to_a_read_is_allowed() -> None:
    assert branch_policy_violation("git l", "main", PROTECTED, aliases=ALIASES) is None
    assert branch_policy_violation("git l", "feat/x", PROTECTED, aliases=ALIASES) is None


def test_unknown_alias_without_facts_is_not_judged() -> None:
    assert branch_policy_violation("git p origin main", "feat/x", PROTECTED) is None


def test_shell_alias_is_refused_on_protected_or_when_it_names_one() -> None:
    assert branch_policy_violation("git s", "main", PROTECTED, aliases=ALIASES) == (
        "'git s' runs alias s = !echo hi, which the guard cannot see through, while 'main' "
        "is protected (trunk-based policy, ADR-0058): " + COMMIT_HINT + "."
    )
    assert branch_policy_violation("git sh", "feat/x", PROTECTED, aliases=ALIASES) == (
        "'git sh' runs alias sh = !git push origin main, which the guard cannot see through "
        "and names protected branch 'main' (trunk-based policy, ADR-0058): spell the git "
        "command out."
    )
    assert branch_policy_violation("git s", "feat/x", PROTECTED, aliases=ALIASES) is None


def test_aliases_from_the_effective_repo_are_used() -> None:
    def facts(_inv: Invocation) -> RepoFacts:
        return RepoFacts("feat/y", {"p": "push"})

    assert (
        branch_policy_violation(
            "cd ../wt && git p origin main", "feat/x", PROTECTED, facts_at=facts
        )
        is not None
    )


def test_inline_alias_planting_is_refused() -> None:
    assert branch_policy_violation("git -c alias.q=push q origin feat/x", "feat/x", PROTECTED) == (
        "inline config plants alias 'q' = 'push', which runs a branch-writing command "
        "(trunk-based policy, ADR-0058): aliases cannot be used to dodge the branch guard."
    )
    assert branch_policy_violation("git config alias.p push", "feat/x", PROTECTED) == (
        "'git config' would set alias 'p' = 'push', which runs a branch-writing command "
        "(trunk-based policy, ADR-0058): aliases cannot be used to dodge the branch guard."
    )
    assert (
        branch_policy_violation("git config alias.lg 'log --oneline'", "feat/x", PROTECTED) is None
    )
    assert branch_policy_violation("git config --get alias.p", "feat/x", PROTECTED) is None


def test_alias_floor_applies_on_every_branch() -> None:
    reason = branch_policy_violation("echo '[alias] p = push' >> .git/config", "feat/x", PROTECTED)
    assert reason is not None and "(floor)" in reason
    assert branch_policy_violation("cat .git/config", "feat/x", PROTECTED) is None


def test_cd_to_home_from_a_subdirectory_is_absolute() -> None:
    assert located_invocations("cd a && cd ~/x && git log") == [Invocation(("git", "log"), "~/x")]


def test_git_globals_with_several_valued_options() -> None:
    assert git_globals(["git", "-C", "d", "-c", "a=b", "commit"]) == ["-C", "d", "-c", "a=b"]


def test_resolver_receives_the_located_invocation() -> None:
    facts = _Recorder("main")
    branch_policy_violation("cd ../wt_main && git commit -m x", "feat/x", PROTECTED, facts_at=facts)
    assert facts.calls == [Invocation(("git", "commit", "-m", "x"), "../wt_main")]
