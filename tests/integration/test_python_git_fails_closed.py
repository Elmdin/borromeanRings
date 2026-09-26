"""The Python half of #186: `subprocess.run(...)` whose failure reads as "nothing found".

Two checks read git from inside their embedded Python, and both took only `.stdout`:

* ``74_secret_history`` — ``git rev-list --all --objects``; an empty result printed
  "empty history — nothing to scan" and **exited 0**. A repository whose object store
  cannot be read therefore passed a scan of every blob it never read.
* ``34_api_diff`` — ``git show <base>:<file>`` per source file; every failure mode
  (a bad merge-base, a packfile error, git missing) read as "new file — no prior API to
  break", so a whole-repository failure reported "no breaking changes" having compared
  nothing.

`subprocess.run` without ``check=`` returns an object whose ``.stdout`` is empty on
failure, which is indistinguishable from a command that succeeded and found nothing —
the same ambiguity as ``|| true`` in the shell half (ADR-0088), one language down.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
GATE_TIMEOUT_S = 300

# `none`: 74_secret_history lives in checks/ci/ and is reached by `--heavy`, independent
# of the fixture's language, so the python lane costs these two tests ~7.7s a call and
# buys them nothing (review of #266). DIFF_CONFIG below keeps `python` — 34_api_diff only
# exists in that lane.
HISTORY_CONFIG = """\
[project]
language = "none"
package = "thing"
src_dir = "src"

[checks]
required = ["05_hygiene"]
heavy = ["74_secret_history"]

[hygiene]
requires = []
"""

DIFF_CONFIG = """\
[project]
language = "python"
package = "thing"
src_dir = "src"

[checks]
required = ["34_api_diff"]
"""

SOURCE = '''"""One public function."""


def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
'''


def _git(project: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=project,
        check=True,
        capture_output=True,
    )


def _project(tmp_path: Path, config: str) -> Path:
    project = tmp_path / "proj"
    (project / "src" / "thing").mkdir(parents=True)
    (project / "borromeanrings.toml").write_text(config, encoding="utf-8")
    (project / "src" / "thing" / "__init__.py").write_text(SOURCE, encoding="utf-8")
    _git(project, "init", "-q", "-b", "main")
    _git(project, "add", "-A")
    _git(project, "commit", "-qm", "chore: base")
    return project


def _gate(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(VERIFY), *args],
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


def _drop_one_object(project: Path) -> None:
    """Remove a single object the history needs.

    Measured, not assumed: making `.git/objects` unreadable is NOT this case — git then
    answers "fatal: not a git repository" to the probe as well, exactly as it does for a
    directory with no repository at all (ADR-0087 records the same discovery), and
    `noop` is the honest verdict there. Removing one object leaves the repository
    perfectly readable — `rev-parse` says true — while every query that needs that
    object fails. That is the case where "it failed" and "there is nothing" differ.
    """
    blob = subprocess.run(
        ["git", "rev-parse", "HEAD:src/thing/__init__.py"],
        cwd=project,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    (project / ".git" / "objects" / blob[:2] / blob[2:]).unlink()


def test_the_history_scan_passes_on_a_clean_repository(tmp_path: Path) -> None:
    """The control."""
    project = _project(tmp_path, HISTORY_CONFIG)

    proc = _gate(project, "--heavy")
    status, log = _receipt(project, "74_secret_history")

    assert status == "pass", log
    assert proc.returncode == 0, proc.stdout


def test_a_history_that_cannot_be_listed_fails_closed_rather_than_reading_as_empty(
    tmp_path: Path,
) -> None:
    """`git rev-list --all --objects` fails, `.stdout` is empty, and the check printed
    "empty history — nothing to scan" and exited 0: a secret gate green over a history
    nobody read."""
    project = _project(tmp_path, HISTORY_CONFIG)
    _drop_one_object(project)

    proc = _gate(project, "--heavy")
    status, log = _receipt(project, "74_secret_history")

    assert status == "fail", f"scanned a history it could not list:\n{log}"
    assert proc.returncode != 0
    assert "empty history" not in log


def test_the_api_diff_passes_on_a_clean_repository(tmp_path: Path) -> None:
    """The control."""
    project = _project(tmp_path, DIFF_CONFIG)
    _git(project, "checkout", "-q", "-b", "feat/x")
    (project / "src" / "thing" / "__init__.py").write_text(
        SOURCE + '\n\ndef mul(a: int, b: int) -> int:\n    """Multiply."""\n    return a * b\n',
        encoding="utf-8",
    )
    _git(project, "add", "-A")
    _git(project, "commit", "-qm", "feat: add mul")

    proc = _gate(project)
    status, log = _receipt(project, "34_api_diff")

    assert status in {"pass", "noop"}, log
    assert proc.returncode == 0, proc.stdout


def test_an_unreadable_prior_version_fails_closed_rather_than_looking_new(
    tmp_path: Path,
) -> None:
    """A file whose previous version cannot be read is not a new file, and "no prior API
    to break" is not something this check may conclude from a failure."""
    project = _project(tmp_path, DIFF_CONFIG)
    _git(project, "checkout", "-q", "-b", "feat/x")
    # A breaking change: the public function is gone.
    (project / "src" / "thing" / "__init__.py").write_text(
        '"""Nothing public any more."""\n', encoding="utf-8"
    )
    _git(project, "add", "-A")
    _git(project, "commit", "-qm", "feat: remove add")
    _drop_one_object(project)

    proc = _gate(project)
    status, log = _receipt(project, "34_api_diff")

    assert status == "fail", f"compared against a history it could not read:\n{log}"
    assert proc.returncode != 0
