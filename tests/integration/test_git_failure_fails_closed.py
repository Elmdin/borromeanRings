"""A check that cannot read its inputs must fail, never pass over them (#186).

Three checks decide their verdict from what git tells them changed on this branch:

* ``09_commits`` — the commit subjects, against the commit-message policy;
* ``11_changelog`` — whether a source change came with a changelog entry;
* ``13_adr`` — whether new surface came with an ADR.

Each read git as ``x="$(git … 2>/dev/null || true)"`` and then judged ``$x``. An empty
``$x`` means "nothing changed" — and a crashed git, a corrupt index or a missing object
store produces exactly that, so a broken repository reported a clean pass over commits
and files nobody read. The audit for #186 found this shape in twelve places.

The fixture here is a repository whose object store has been emptied: `git rev-parse`
still says "this is a repository", every query about its contents fails, and there IS a
violation to find — so a pass could only mean the check never looked.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
GATE_TIMEOUT_S = 300

CONFIG = """\
[project]
language = "none"
src_dir = "src"

[collaboration]
branch_patterns = ["feat/*"]
commit_types = ["feat", "fix", "chore", "docs", "test", "refactor"]
max_subject_length = 72

[changelog]
enabled = true
require_entry_on_src_change = true

[checks]
required = ["{check}"]
"""


def _git(project: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=project,
        check=True,
        capture_output=True,
    )


def _project(tmp_path: Path, check: str) -> Path:
    """A branch with a real violation of each of the three checks."""
    project = tmp_path / "proj"
    (project / "src").mkdir(parents=True)
    (project / "docs" / "adr").mkdir(parents=True)
    (project / "borromeanrings.toml").write_text(CONFIG.format(check=check), encoding="utf-8")
    (project / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n", encoding="utf-8")
    _git(project, "init", "-q", "-b", "main")
    _git(project, "add", "-A")
    _git(project, "commit", "-qm", "chore: base")
    _git(project, "checkout", "-q", "-b", "feat/x")
    (project / "src" / "thing.txt").write_text("new surface\n", encoding="utf-8")
    _git(project, "add", "-A")
    # Not Conventional (09_commits), source changed without a changelog entry
    # (11_changelog) and without an ADR (13_adr): all three have something to find.
    _git(project, "commit", "-qm", "did stuff")
    return project


def _break_the_object_store(project: Path) -> None:
    for obj in (project / ".git" / "objects").rglob("*"):
        if obj.is_file():
            obj.unlink()


def _gate(project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(VERIFY)],
        cwd=project,
        env={**os.environ, "BORROMEANRINGS_PROJECT": str(project)},
        capture_output=True,
        text=True,
        timeout=GATE_TIMEOUT_S,
    )


def _receipt(project: Path, check: str) -> tuple[str, str]:
    run_dir = sorted((project / ".meta-harness" / "receipts").glob("*/"))[-1]
    status = json.loads((run_dir / f"{check}.json").read_text(encoding="utf-8"))["status"]
    return status, (run_dir / f"{check}.log").read_text(encoding="utf-8", errors="replace")


CHECKS = ["09_commits", "11_changelog", "13_adr"]


@pytest.mark.parametrize("check", CHECKS)
def test_the_violation_is_found_when_git_works(tmp_path: Path, check: str) -> None:
    """The control. Without it, the test below could pass on a check that fails for any
    reason at all, and prove nothing about reading the repository."""
    project = _project(tmp_path, check)

    proc = _gate(project)
    status, log = _receipt(project, check)

    assert status == "fail", log
    assert proc.returncode != 0


@pytest.mark.parametrize("check", CHECKS)
def test_a_git_failure_fails_closed_rather_than_reading_as_no_changes(
    tmp_path: Path, check: str
) -> None:
    project = _project(tmp_path, check)
    _break_the_object_store(project)

    proc = _gate(project)
    status, log = _receipt(project, check)

    assert status == "fail", f"{check} passed over a repository it could not read:\n{log}"
    assert proc.returncode != 0
    assert "git" in log.lower(), log


@pytest.mark.parametrize("check", CHECKS)
def test_a_repository_with_no_commits_is_still_legitimate(tmp_path: Path, check: str) -> None:
    """Measured, not assumed: in a repository with no commits `git rev-parse --abbrev-ref
    HEAD` exits 128, because HEAD names a branch that does not exist yet. That is a
    fresh project, not a broken one — failing it would make `init.sh`'s own output red
    (review of #258). `symbolic-ref` still knows the branch's name."""
    project = tmp_path / "proj"
    (project / "src").mkdir(parents=True)
    (project / "borromeanrings.toml").write_text(CONFIG.format(check=check), encoding="utf-8")
    (project / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project, check=True)

    proc = _gate(project)
    status, log = _receipt(project, check)

    assert status in {"pass", "noop"}, f"a fresh repository is not a broken one:\n{log}"
    assert proc.returncode == 0, proc.stdout


@pytest.mark.parametrize("check", CHECKS)
def test_a_repository_whose_head_cannot_be_read_fails_closed(tmp_path: Path, check: str) -> None:
    """Both ways of asking which branch this is now fail, so the check cannot know which
    rule applies to it. It used to default to the literal "HEAD", which matches no
    feature-branch prefix — a pass over a branch nobody identified."""
    project = _project(tmp_path, check)
    (project / ".git" / "HEAD").unlink()

    proc = _gate(project)
    status, log = _receipt(project, check)

    assert status == "fail", log
    assert proc.returncode != 0
