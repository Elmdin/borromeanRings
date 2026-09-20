"""Asking git something, with "it failed" distinguishable from "there is nothing" (#186).

`subprocess.run(...).stdout` is empty both when git found nothing and when git failed.
Every check that read git from Python took that empty string for an answer: an
unreadable history became "empty history — nothing to scan", and a file whose previous
version could not be read became "a new file — no prior API to break".
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from meta_harness.git_read import (
    DEFAULT_TIMEOUT_S,
    TIMEOUT_ENV,
    GitUnavailable,
    git_bytes,
    git_show,
    git_text,
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    (root / "kept.txt").write_text("one\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "one")
    return root


def test_a_successful_query_returns_what_git_said(repo: Path) -> None:
    assert git_text(str(repo), "rev-parse", "--abbrev-ref", "HEAD").strip() == "main"
    assert git_bytes(str(repo), "show", "HEAD:kept.txt") == b"one\n"


def test_a_query_that_found_nothing_is_not_an_error(repo: Path) -> None:
    """The distinction only means something if "nothing" still comes back as nothing."""
    assert git_text(str(repo), "log", "--format=%H", "--author=nobody@example.com") == ""


def test_a_failed_query_raises_with_gits_own_words(repo: Path) -> None:
    with pytest.raises(GitUnavailable) as caught:
        git_text(str(repo), "show", "no-such-ref:kept.txt")

    message = str(caught.value)
    assert "exited" in message
    assert "no-such-ref" in message


def test_git_missing_or_unrunnable_raises_rather_than_returning_empty(tmp_path: Path) -> None:
    with pytest.raises(GitUnavailable) as caught:
        git_text(str(tmp_path / "not-a-directory"), "status")

    assert "could not be run" in str(caught.value) or "exited" in str(caught.value)


def test_show_returns_none_only_when_the_path_was_absent(repo: Path) -> None:
    assert git_show(str(repo), "HEAD", "kept.txt") == "one\n"
    assert git_show(str(repo), "HEAD", "never-existed.txt") is None


def test_show_raises_when_the_revision_itself_cannot_be_read(repo: Path) -> None:
    """The case that mattered: every failure used to read as "a new file", so a broken
    repository reported no breaking changes having compared nothing."""
    with pytest.raises(GitUnavailable):
        git_show(str(repo), "no-such-ref", "kept.txt")


def test_a_hanging_git_fails_closed_rather_than_holding_the_gate(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#256: a read against the governed project must be bounded. `git -c alias…` is not
    needed — a sleep through git's own `-c` config is enough to hold the call open."""
    monkeypatch.setenv(TIMEOUT_ENV, "1")

    with pytest.raises(GitUnavailable) as caught:
        git_text(str(repo), "-c", "alias.zzz=!sleep 30", "zzz")

    assert "timed out" in str(caught.value)


def test_the_bound_can_be_lifted_deliberately(monkeypatch: pytest.MonkeyPatch, repo: Path) -> None:
    """`0` is how the rest of the harness spells "no wall-clock limit"."""
    monkeypatch.setenv(TIMEOUT_ENV, "0")

    assert git_text(str(repo), "rev-parse", "HEAD").strip()


@pytest.mark.parametrize("raw", ["", "   ", "not-a-number"])
def test_an_unreadable_bound_falls_back_to_the_default(
    raw: str, monkeypatch: pytest.MonkeyPatch, repo: Path
) -> None:
    """A garbled limit must not mean "unbounded"."""
    monkeypatch.setenv(TIMEOUT_ENV, raw)

    assert git_text(str(repo), "rev-parse", "HEAD").strip()
    assert DEFAULT_TIMEOUT_S > 0
