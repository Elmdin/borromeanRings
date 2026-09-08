"""The PreToolUse guard enforces the trunk-based branch policy (ADR-0058, #75).

One test per row of the command matrix in docs/specs/SPEC-branch-policy.md, driven
through the REAL hook with a crafted PreToolUse payload on stdin against a real
governed git repo: denied rows must emit a deny decision whose reason names the
policy; allowed rows must emit no decision at all. Both HEAD states (protected
``main`` and feature ``feat/x``) are exercised, so "allowed" is proven, not assumed.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
HOOK = BORROMEANRINGS_HOME / ".claude" / "hooks" / "pre_bash_guard.sh"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"},
    )  # fmt: skip


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A governed repo declaring ``protected_branches = ["main"]`` (no [git], so the
    identity guard fails open), with branches ``main`` and ``feat/x``."""
    (tmp_path / "borromeanrings.toml").write_text(
        '[project]\nlanguage = "none"\npackage = "x"\n\n'
        '[checks]\nrequired = ["05_hygiene"]\n\n[hygiene]\nrequires = []\n\n'
        '[collaboration]\nprotected_branches = ["main"]\n'
    )
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "init")
    _git(tmp_path, "branch", "feat/x")
    return tmp_path


def _checkout(repo: Path, branch: str) -> None:
    _git(repo, "checkout", "-q", branch)


def _decision(repo: Path, command: str) -> str | None:
    """Run the guard on ``command``; the deny reason, or None when it lets it through."""
    payload = json.dumps({"tool_input": {"command": command}})
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    env["BORROMEANRINGS_HOOK_STDIN_TIMEOUT"] = "5"
    out = subprocess.run(
        ["bash", str(HOOK)], input=payload, capture_output=True, text=True, env=env, timeout=30
    ).stdout
    if not out.strip():
        return None
    verdict = json.loads(out)["hookSpecificOutput"]
    assert verdict["permissionDecision"] == "deny"
    reason: str = verdict["permissionDecisionReason"]
    return reason


# --- denied while HEAD is protected ---------------------------------------------

ON_PROTECTED_DENIED = [
    "git commit -m x",
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
    "git reset --hard HEAD~1",
    "git reset --soft HEAD~1",
    "git pull origin feat/x",
    "git push",
    "git push origin main",
    "git push -u origin HEAD",
    "git push origin feat/x",  # the floor: any push while ON a protected branch
    "echo 'git commit' > notes.txt",  # the floor: a mere mention, refused as before
]


@pytest.mark.parametrize("command", ON_PROTECTED_DENIED)
def test_denied_on_protected_branch(repo: Path, command: str) -> None:
    _checkout(repo, "main")
    reason = _decision(repo, command)
    assert reason is not None, f"{command!r} must be denied on main"
    # A hard reset (and a bare force push) is refused by the older, global
    # deny-list before the branch policy runs — denied either way, earlier reason.
    assert "ADR-0058" in reason or "--hard" in reason or "force-push" in reason


# --- the same commands are allowed on a feature branch ---------------------------

ON_FEATURE_ALLOWED = [
    "git commit -m x",
    "git commit --amend --no-edit",
    "git -c user.email=x@y commit -m x",
    "GIT_AUTHOR_EMAIL=x@y git commit -m x",
    "cd sub && git commit -m x",
    "git merge main",
    "git rebase main",
    "git cherry-pick abc123",
    "git revert abc123",
    "git pull origin feat/x",
    "git push",
    "git push origin feat/x",
    "git push -u origin feat/x",
    "git push -u origin HEAD",
    "git push --force-with-lease origin feat/x",
    "git push origin HEAD:refs/heads/feat/x",
    "git push origin feat/main",
    "git push --tags origin",
    "git push --dry-run origin main",
    "echo 'git commit' > notes.txt",
    "grep -r 'git push --force' docs/",
    "cat > f <<'EOF'\ngit push origin main\nEOF",
]


@pytest.mark.parametrize("command", ON_FEATURE_ALLOWED)
def test_allowed_on_feature_branch(repo: Path, command: str) -> None:
    _checkout(repo, "feat/x")
    assert _decision(repo, command) is None, f"{command!r} must be allowed on feat/x"


# --- pushes to a protected ref are denied from ANY branch -------------------------

PUSH_TO_PROTECTED = [
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
    "git push --delete origin main",
    "git push origin :main",
    "git push origin 'refs/heads/*:refs/heads/*'",
    "git push --all origin",
    "git push --mirror origin",
    "git -C . push origin main",
    "cd sub && git push origin main",
    "bash -c 'git push origin main'",
    "git fetch && git push origin main",
]


@pytest.mark.parametrize("command", PUSH_TO_PROTECTED)
def test_push_to_protected_ref_denied_from_feature_branch(repo: Path, command: str) -> None:
    _checkout(repo, "feat/x")
    reason = _decision(repo, command)
    assert reason is not None, f"{command!r} must be denied"
    # Bare --force/-f is refused by the older global force-push deny first.
    assert "main" in reason or "force-push" in reason


# --- local rewrites of a protected branch ----------------------------------------

REWRITE_DENIED = [
    "git branch -D main",
    "git branch -d main",
    "git branch --delete main",
    "git branch -f main HEAD~3",
    "git branch -M main",
    "git checkout -B main",
    "git switch -C main",
    "git update-ref refs/heads/main abc123",
]


@pytest.mark.parametrize("command", REWRITE_DENIED)
def test_rewriting_protected_branch_denied(repo: Path, command: str) -> None:
    _checkout(repo, "feat/x")
    reason = _decision(repo, command)
    assert reason is not None and "ADR-0058" in reason


REWRITE_ALLOWED = [
    "git branch -D feat/old",
    "git branch feat/new",
    "git checkout main",
    "git switch main",
    "git checkout -b feat/y",
    "git switch -c feat/y",
    "git checkout -B feat/y",
]


@pytest.mark.parametrize("command", REWRITE_ALLOWED)
def test_branch_operations_on_feature_refs_allowed(repo: Path, command: str) -> None:
    _checkout(repo, "feat/x")
    assert _decision(repo, command) is None


# --- read-only git is allowed everywhere -----------------------------------------

READ_ONLY = [
    "git fetch",
    "git fetch origin main",
    "git log main",
    "git log origin/main..HEAD",
    "git diff main...HEAD",
    "git status",
    "git rev-parse --abbrev-ref HEAD",
    "git show main:README.md",
    "git pull",
    "git pull --rebase origin main",
    "ls",
]


@pytest.mark.parametrize("command", READ_ONLY)
@pytest.mark.parametrize("head", ["main", "feat/x"])
def test_read_only_allowed_everywhere(repo: Path, head: str, command: str) -> None:
    _checkout(repo, head)
    assert _decision(repo, command) is None


# --- reasons carry the fix hint; undeclared protection is off -------------------


def test_commit_reason_carries_the_fix_hint(repo: Path) -> None:
    _checkout(repo, "main")
    reason = _decision(repo, "git commit -m x")
    assert reason == (
        "'main' is a protected branch (trunk-based policy, ADR-0058): 'git commit' would "
        "land work directly on it — create a feature branch (git switch -c feat/<name>); "
        "land via PR + gate."
    )


def test_push_reason_names_the_target(repo: Path) -> None:
    _checkout(repo, "feat/x")
    assert _decision(repo, "git push origin HEAD:main") == (
        "'git push' targets protected branch 'main' (trunk-based policy, ADR-0058): "
        "push a feature branch and land via PR + gate."
    )


def test_undeclared_protection_turns_the_guard_off(repo: Path) -> None:
    (repo / "borromeanrings.toml").write_text(
        '[project]\nlanguage = "none"\npackage = "x"\n\n'
        '[checks]\nrequired = ["05_hygiene"]\n\n[hygiene]\nrequires = []\n'
    )
    _checkout(repo, "main")
    assert _decision(repo, "git commit -m x") is None
    assert _decision(repo, "git push origin main") is None
