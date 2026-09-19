"""The impure git-facts layer for the branch guard, against real temporary repos.

Every function shells out with a fixed argv and fails soft; the resolver answers
conservatively when a command's directory cannot be followed (PR #169 review).
"""

import os
import subprocess
from pathlib import Path

import pytest

from meta_harness import trunk_policy_git as tpg
from meta_harness.trunk_policy import Invocation, RepoFacts

_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@x",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@x",
}


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, env={**os.environ, **_ENV}
    )


@pytest.fixture
def repos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """A repo on ``feat/x`` with worktrees ``wt_main`` (main) and ``wt_feat`` (feat/y).

    HOME is isolated so the developer's own global aliases cannot leak in.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "f").write_text("f")
    _git(repo, "add", "f")
    _git(repo, "commit", "-q", "-m", "init")
    _git(repo, "checkout", "-q", "-b", "feat/x")
    _git(repo, "worktree", "add", "-q", str(tmp_path / "wt_main"), "main")
    _git(repo, "worktree", "add", "-q", "-b", "feat/y", str(tmp_path / "wt_feat"))
    _git(repo, "config", "alias.p", "push")
    _git(repo, "config", "alias.lg", "log --oneline")
    return {"repo": repo, "wt_main": tmp_path / "wt_main", "wt_feat": tmp_path / "wt_feat"}


def test_head_branch(repos: dict[str, Path], tmp_path: Path) -> None:
    assert tpg.head_branch(str(repos["repo"])) == "feat/x"
    assert tpg.head_branch(str(repos["wt_main"])) == "main"
    assert tpg.head_branch(str(repos["repo"]), ["-C", str(repos["wt_main"])]) == "main"
    (tmp_path / "plain").mkdir()
    assert tpg.head_branch(str(tmp_path / "plain")) is None


def test_repo_aliases(repos: dict[str, Path], tmp_path: Path) -> None:
    assert tpg.repo_aliases(str(repos["repo"])) == {"p": "push", "lg": "log --oneline"}
    (tmp_path / "plain").mkdir()
    assert tpg.repo_aliases(str(tmp_path / "plain")) == {}


def test_checked_out_branches(repos: dict[str, Path]) -> None:
    assert tpg.checked_out_branches(str(repos["repo"])) == {"feat/x", "main", "feat/y"}
    assert tpg.checked_out_branches(str(repos["repo"] / "nope")) == set()


def test_git_failures_are_soft(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def boom(*_args: object, **_kw: object) -> None:
        raise OSError("no git")

    monkeypatch.setattr(tpg.subprocess, "run", boom)
    assert tpg.head_branch(str(tmp_path)) is None
    assert tpg.repo_aliases(str(tmp_path)) == {}
    assert tpg.checked_out_branches(str(tmp_path)) == set()

    def slow(*_args: object, **_kw: object) -> None:
        raise subprocess.TimeoutExpired(cmd="git", timeout=1)

    monkeypatch.setattr(tpg.subprocess, "run", slow)
    assert tpg.head_branch(str(tmp_path)) is None


def test_resolver_reads_the_effective_directory(repos: dict[str, Path]) -> None:
    resolve = tpg.facts_resolver(str(repos["repo"]), ("main",))
    assert resolve(Invocation(("git", "commit"), "../wt_main")) == RepoFacts(
        "main", {"p": "push", "lg": "log --oneline"}
    )
    assert resolve(Invocation(("git", "commit"), "../wt_feat")).head == "feat/y"
    assert resolve(Invocation(("git", "commit"), str(repos["wt_main"]))).head == "main"
    assert resolve(Invocation(("git", "-C", str(repos["wt_main"]), "commit"), None)).head == "main"
    assert resolve(Invocation(("git", "commit"), None)).head == "feat/x"


def test_resolver_home_is_not_a_repo_so_falls_back(repos: dict[str, Path]) -> None:
    # `cd ~ && git commit`: HOME (isolated, not a repo) cannot be read ⇒ conservative.
    resolve = tpg.facts_resolver(str(repos["repo"]), ("main",))
    assert resolve(Invocation(("git", "commit"), "~")).head == "main"


def test_resolver_is_conservative_when_the_directory_is_unknown(repos: dict[str, Path]) -> None:
    resolve = tpg.facts_resolver(str(repos["repo"]), ("main",))
    # Unresolvable directory, but `main` is checked out in some worktree ⇒ report it.
    assert resolve(Invocation(("git", "commit"), "does/not/exist")).head == "main"
    assert resolve(Invocation(("git", "commit"), "?")).head == "main"
    assert resolve(Invocation(("git", "commit"), "?")).aliases == {
        "p": "push",
        "lg": "log --oneline",
    }


def test_resolver_falls_back_to_project_head_when_no_protected_is_checked_out(
    repos: dict[str, Path],
) -> None:
    resolve = tpg.facts_resolver(str(repos["repo"]), ("dev",))
    assert resolve(Invocation(("git", "commit"), "?")).head == "feat/x"


def test_resolver_reports_detached_when_nothing_is_readable(tmp_path: Path) -> None:
    (tmp_path / "plain").mkdir()
    resolve = tpg.facts_resolver(str(tmp_path / "plain"), ("main",))
    assert resolve(Invocation(("git", "commit"), "?")) == RepoFacts("HEAD", {})


def test_resolver_reads_aliases_of_the_target_repo(repos: dict[str, Path], tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "-q", "-b", "feat/z")
    (other / "g").write_text("g")
    _git(other, "add", "g")
    _git(other, "commit", "-q", "-m", "init")
    _git(other, "config", "alias.q", "push")
    resolve = tpg.facts_resolver(str(repos["repo"]), ("main",))
    assert resolve(Invocation(("git", "-C", str(other), "q"), None)) == RepoFacts(
        "feat/z", {"q": "push"}, governed=False
    )


def test_common_dir_is_shared_by_worktrees(repos: dict[str, Path], tmp_path: Path) -> None:
    assert tpg.common_dir(str(repos["wt_main"])) == tpg.common_dir(str(repos["repo"]))
    assert tpg.common_dir(str(repos["repo"])) == str((repos["repo"] / ".git").resolve())
    (tmp_path / "plain").mkdir()
    assert tpg.common_dir(str(tmp_path / "plain")) is None


def test_unrelated_repo_on_main_is_not_governed(repos: dict[str, Path], tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "-q", "-b", "main")
    (other / "g").write_text("g")
    _git(other, "add", "g")
    _git(other, "commit", "-q", "-m", "init")
    resolve = tpg.facts_resolver(str(repos["repo"]), ("main",))
    assert resolve(Invocation(("git", "commit"), "../other")) == RepoFacts(
        "main", {}, governed=False
    )
    # This project's own worktree on main stays governed.
    assert resolve(Invocation(("git", "commit"), "../wt_main")).governed is True


def test_project_that_is_not_a_repo_governs_everything(tmp_path: Path) -> None:
    (tmp_path / "plain").mkdir()
    (tmp_path / "r").mkdir()
    _git(tmp_path / "r", "init", "-q", "-b", "main")
    (tmp_path / "r" / "g").write_text("g")
    _git(tmp_path / "r", "add", "g")
    _git(tmp_path / "r", "commit", "-q", "-m", "init")
    resolve = tpg.facts_resolver(str(tmp_path / "plain"), ("main",))
    assert resolve(Invocation(("git", "commit"), "../r")).governed is True
