"""Gate backstop for the trunk-based branch policy: ``08_branch`` fails when HEAD is
a protected branch carrying commits its remote ref lacks (ADR-0058, #75).

Drives the REAL check script against a real repo with a bare ``origin``. The guard
prevents a direct commit up front; this is the layer that catches one made outside
the guard (another tool, ``--no-verify``, a hand-run git). Pattern checks stay as
they were.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
CHECK = BORROMEANRINGS_HOME / "checks" / "shared" / "08_branch.sh"

_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@x",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@x",
}


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, **_ENV},
    ).stdout.strip()


def _commit(repo: Path, name: str) -> None:
    (repo / name).write_text(name)
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", f"chore: {name}")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Governed repo on ``main`` with a bare origin that already has main."""
    work = tmp_path / "work"
    work.mkdir()
    (work / "borromeanrings.toml").write_text(
        '[project]\nlanguage = "none"\npackage = "x"\n\n'
        '[checks]\nrequired = ["08_branch"]\n\n[hygiene]\nrequires = []\n\n'
        '[collaboration]\nprotected_branches = ["main"]\nbranch_patterns = ["feat/*"]\n'
    )
    _git(work, "init", "-q", "-b", "main")
    _git(work, "add", ".")
    _git(work, "commit", "-q", "-m", "chore: init")
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    _git(work, "remote", "add", "origin", str(bare))
    _git(work, "push", "-q", "-u", "origin", "main")
    return work


def _run_check(repo: Path, tmp_path: Path) -> tuple[int, str, str]:
    """Run 08_branch against ``repo``; (exit code, receipt status, log text)."""
    receipts = tmp_path / "receipts"
    receipts.mkdir(exist_ok=True)
    env = dict(os.environ)
    env.update(
        PROJECT_ROOT=str(repo),
        RECEIPT_DIR=str(receipts),
        BORROMEANRINGS_HOME=str(BORROMEANRINGS_HOME),
    )
    proc = subprocess.run(["bash", str(CHECK)], env=env, capture_output=True, text=True)
    status = json.loads((receipts / "08_branch.json").read_text())["status"]
    return proc.returncode, status, (receipts / "08_branch.log").read_text()


def test_protected_branch_in_sync_with_remote_passes(repo: Path, tmp_path: Path) -> None:
    code, status, log = _run_check(repo, tmp_path)
    assert (code, status) == (0, "pass")
    assert "protected 'main' carries no direct commits (in sync with origin/main)" in log


def test_direct_commits_on_protected_branch_fail(repo: Path, tmp_path: Path) -> None:
    _commit(repo, "a.txt")
    _commit(repo, "b.txt")
    code, status, log = _run_check(repo, tmp_path)
    assert (code, status) == (1, "fail")
    assert log.strip() == (
        "DIRECT COMMITS ON PROTECTED BRANCH: 'main' has 2 commit(s) not on origin/main — "
        "work lands on protected branches only via PR + gate (trunk-based policy, "
        "ADR-0058). Move them: git switch -c feat/<name> && git branch -f main origin/main."
    )


def test_feature_branch_ahead_of_remote_passes(repo: Path, tmp_path: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "feat/x")
    _commit(repo, "a.txt")
    code, status, log = _run_check(repo, tmp_path)
    assert (code, status) == (0, "pass")
    assert "'feat/x' conforms" in log


def test_naming_rule_still_enforced(repo: Path, tmp_path: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "my-branch")
    code, status, log = _run_check(repo, tmp_path)
    assert (code, status) == (1, "fail")
    assert "BRANCH VIOLATION" in log and "my-branch" in log


def test_protected_branch_without_remote_ref_cannot_judge(repo: Path, tmp_path: Path) -> None:
    _git(repo, "remote", "remove", "origin")
    _commit(repo, "a.txt")
    code, status, log = _run_check(repo, tmp_path)
    assert (code, status) == (0, "pass")
    assert "no remote ref to compare" in log


def test_upstream_is_preferred_over_origin_convention(repo: Path, tmp_path: Path) -> None:
    # A protected branch tracking a differently-named remote ref is judged against it.
    _git(repo, "push", "-q", "origin", "main:trunk")
    _git(repo, "branch", "-q", "--set-upstream-to=origin/trunk", "main")
    _commit(repo, "a.txt")
    code, status, log = _run_check(repo, tmp_path)
    assert (code, status) == (1, "fail")
    assert "not on origin/trunk" in log


def test_undeclared_policy_is_off(repo: Path, tmp_path: Path) -> None:
    (repo / "borromeanrings.toml").write_text(
        '[project]\nlanguage = "none"\npackage = "x"\n\n'
        '[checks]\nrequired = ["08_branch"]\n\n[hygiene]\nrequires = []\n'
    )
    _commit(repo, "a.txt")
    code, status, log = _run_check(repo, tmp_path)
    assert (code, status) == (0, "pass")
    assert "rule off" in log
