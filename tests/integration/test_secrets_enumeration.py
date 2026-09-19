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
