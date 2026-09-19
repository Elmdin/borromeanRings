"""12_secrets must never pass without having looked (ADR-0049, ADR-0084, #186).

It scans the files git tracks. Two ways that list can be empty, and neither is a pass:

* git is present and ``git ls-files`` FAILED (a corrupt index, say): the check could not
  enumerate its inputs, so it fails closed. It used to swallow the error, scan an empty
  list, and report ``pass`` — a secret gate green over a tree it never read.
* the repository tracks nothing yet (a freshly initialised project): there is nothing to
  scan, which is legitimate but must be reported as ``noop``, not ``pass``.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
VERIFY = REPO / "verify.sh"

CONFIG = """\
[project]
language = "none"

[checks]
required = ["12_secrets"]
"""


def _repo(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "borromeanrings.toml").write_text(CONFIG, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    return project


def _status(project: Path) -> tuple[str, str, int]:
    proc = subprocess.run(
        ["bash", str(VERIFY)],
        cwd=project,
        env={**os.environ, "BORROMEANRINGS_PROJECT": str(project)},
        capture_output=True,
        text=True,
        timeout=300,
    )
    receipt = sorted((project / ".meta-harness" / "receipts").glob("*/12_secrets.json"))[-1]
    log = receipt.with_suffix(".log").read_text(encoding="utf-8", errors="replace")
    return json.loads(receipt.read_text(encoding="utf-8"))["status"], log, proc.returncode


def test_a_repository_that_tracks_nothing_is_noop_not_pass(tmp_path: Path) -> None:
    project = _repo(tmp_path)

    status, log, code = _status(project)

    assert status == "noop", log
    assert code == 0, "nothing to scan is legitimate — it is reported, not failed"
    assert "no tracked files" in log


def test_a_failed_enumeration_fails_closed(tmp_path: Path) -> None:
    project = _repo(tmp_path)
    subprocess.run(["git", "add", "-A"], cwd=project, check=True)
    (project / ".git" / "index").write_bytes(b"not an index")  # ls-files now errors

    status, log, code = _status(project)

    assert status == "fail", log
    assert code != 0
    assert "could not list tracked files" in log


def test_tracked_files_are_still_scanned_and_pass_when_clean(tmp_path: Path) -> None:
    project = _repo(tmp_path)
    subprocess.run(["git", "add", "-A"], cwd=project, check=True)

    status, log, code = _status(project)

    assert status == "pass", log
    assert code == 0


_AWS_SECRET = "wJalrXUtnFEMI/" + "K7MDENG/bPxRfiCYEXAMPLEKEY"  # built at runtime


def _commit_secret(project: Path) -> Path:
    creds = project / "creds.py"
    creds.write_text(f'aws_secret_access_key = "{_AWS_SECRET}"\n', encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=project, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "c"],
        cwd=project,
        check=True,
    )
    return creds


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a mode-000 file anyway")
def test_an_unreadable_tracked_file_fails_closed_rather_than_passing(tmp_path: Path) -> None:
    """Review of #250: a tracked file the scan cannot open was skipped silently, so a
    real secret in it gated PASS having scanned nothing."""
    project = _repo(tmp_path)
    creds = _commit_secret(project)
    creds.chmod(0)
    try:
        status, log, code = _status(project)
    finally:
        creds.chmod(0o644)
    assert status == "fail", log
    assert code != 0
    assert "could not read" in log and "creds.py" in log


def test_git_environment_redirection_cannot_point_the_scan_elsewhere(tmp_path: Path) -> None:
    """Review of #250: GIT_DIR / GIT_WORK_TREE override `git -C`, so an inherited pair
    pointing at a clean decoy made the gate scan the decoy and pass a project with a
    committed secret. The gate reads the project at PROJECT_ROOT, and only that."""
    project = _repo(tmp_path)
    _commit_secret(project)
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=decoy, check=True)
    (decoy / "clean.txt").write_text("nothing here\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=decoy, check=True)

    proc = subprocess.run(
        ["bash", str(VERIFY)],
        cwd=project,
        env={
            **os.environ,
            "BORROMEANRINGS_PROJECT": str(project),
            "GIT_DIR": str(decoy / ".git"),
            "GIT_WORK_TREE": str(decoy),
        },
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode != 0, proc.stdout
    assert "12_secrets" in proc.stdout and "FAIL" in proc.stdout, proc.stdout
