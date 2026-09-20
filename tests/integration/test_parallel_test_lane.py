"""The full test lane runs in parallel, and says which way it ran (#253, ADR-0086).

The suite outgrew the 900s per-check bound on `dev`, and #252 raised the bound to 1800s
to unblock the merge queue. Serially this suite takes ~19 minutes; the same suite across
one worker per CPU takes ~4. The bound is the same either way — what changed is how much
of it the suite needs.

Two things have to stay true, and both are asserted here against a real gate run:

* a project whose environment has **no** pytest-xdist still gates exactly as before —
  borromeanRings never requires a governed project to install anything;
* the **fast** lane stays serial: it is already narrowed to a handful of paths, and
  worker start-up would cost more than it saves.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
GATE_TIMEOUT_S = 300

CONFIG = """\
[project]
language = "python"
package = "thing"
src_dir = "src"
tests_dir = "tests"

[checks]
required = ["40_test"]

[test]
fast_paths = ["tests/test_thing.py"]
"""

SOURCE = "def add(a: int, b: int) -> int:\n    return a + b\n"
TEST = "from thing import add\n\n\ndef test_add() -> None:\n    assert add(1, 2) == 3\n"


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    (project / "src" / "thing").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "borromeanrings.toml").write_text(CONFIG, encoding="utf-8")
    (project / "src" / "thing" / "__init__.py").write_text(SOURCE, encoding="utf-8")
    (project / "tests" / "test_thing.py").write_text(TEST, encoding="utf-8")
    (project / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["setuptools"]\n\n[project]\nname = "thing"\nversion = "0"\n\n'
        '[tool.pytest.ini_options]\npythonpath = ["src"]\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "add", "-A"], cwd=project, check=True)
    return project


def _gate(project: Path, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(VERIFY), *args],
        cwd=project,
        env={**os.environ, "BORROMEANRINGS_PROJECT": str(project), **env},
        capture_output=True,
        text=True,
        timeout=GATE_TIMEOUT_S,
    )


def _log(project: Path) -> str:
    run_dir = sorted((project / ".meta-harness" / "receipts").glob("*/"))[-1]
    return (run_dir / "40_test.log").read_text(encoding="utf-8", errors="replace")


def _status(project: Path) -> str:
    run_dir = sorted((project / ".meta-harness" / "receipts").glob("*/"))[-1]
    return json.loads((run_dir / "40_test.json").read_text(encoding="utf-8"))["status"]


@pytest.mark.skipif(
    shutil.which("python3") is None, reason="the lane runs the project's own python3"
)
def test_the_full_lane_runs_in_parallel_and_says_so(tmp_path: Path) -> None:
    project = _project(tmp_path)

    proc = _gate(project, BORROMEANRINGS_TEST_WORKERS="2")

    log = _log(project)
    assert proc.returncode == 0, proc.stdout + log
    assert _status(project) == "pass", log
    assert "running the full suite in parallel: pytest -n 2 --dist loadgroup" in log, log
    assert "2 workers" in log or "passed" in log, log


def test_without_pytest_xdist_the_lane_runs_serially_and_still_gates(tmp_path: Path) -> None:
    """A governed project is never required to install anything: the check asks whether
    xdist is there, and runs the suite either way."""
    project = _project(tmp_path)
    # A sandboxed import path where `xdist` cannot be found, without touching the
    # environment this suite itself runs in.
    blocker = tmp_path / "noxdist"
    blocker.mkdir()
    (blocker / "sitecustomize.py").write_text(
        "import sys\n\n\nclass _Block:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name == 'xdist' or name.startswith('xdist.'):\n"
        "            raise ImportError(name)\n"
        "        return None\n\n\n"
        "sys.meta_path.insert(0, _Block())\n",
        encoding="utf-8",
    )

    proc = _gate(project, PYTHONPATH=str(blocker))

    log = _log(project)
    assert proc.returncode == 0, proc.stdout + log
    assert _status(project) == "pass", log
    assert "running the full suite serially" in log, log
    assert "--dist" not in log, log


def test_the_fast_lane_stays_serial(tmp_path: Path) -> None:
    """It is already narrowed to the declared paths; worker start-up would cost more
    than it saves, and the fast lane's whole point is being fast."""
    project = _project(tmp_path)

    proc = _gate(project, "--fast")

    log = _log(project)
    assert proc.returncode == 0, proc.stdout + log
    assert "--dist" not in log and "-n " not in log, log
    assert "FAST lane" in log or "FAST" in log, log


def test_files_that_share_a_group_land_on_one_worker(tmp_path: Path) -> None:
    """The rule has to reach the scheduler, not just the marker.

    xdist reads `xdist_group` in its OWN collection hook, so a hook that adds the marker
    afterwards leaves every test ungrouped and the suite silently unprotected — which is
    exactly what happened first: the two files that gate examples/textkit still landed on
    different workers, and still read each other's runs. `tryfirst` is why this passes.
    """
    suite = tmp_path / "suite"
    (suite / "tests").mkdir(parents=True)
    shutil.copy(BORROMEANRINGS_HOME / "tests" / "conftest.py", suite / "tests" / "conftest.py")
    shutil.copy(BORROMEANRINGS_HOME / "tests" / "_scheduling.py", suite / "_scheduling.py")
    report = suite / "workers"
    report.mkdir()
    body = (
        "import os\nfrom pathlib import Path\n\n"
        'XDIST_GROUP = "together"\n\n'
        "def _record(name):\n"
        '    worker = os.environ.get("PYTEST_XDIST_WORKER", "serial")\n'
        f'    Path(r"{report}").joinpath(name).write_text(worker)\n\n'
    )
    for f in ("a", "b"):
        (suite / "tests" / f"test_{f}.py").write_text(
            body + "".join(f'def test_{f}{i}():\n    _record("{f}{i}")\n\n' for i in range(3)),
            encoding="utf-8",
        )
    # Ungrouped company, so the scheduler has somewhere else to put things.
    (suite / "tests" / "test_other.py").write_text(
        "".join(f"def test_other{i}():\n    assert True\n\n" for i in range(6)), encoding="utf-8"
    )

    proc = subprocess.run(
        [
            "python3",
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-n",
            "2",
            "--dist",
            "loadgroup",
            "tests",
        ],
        cwd=suite,
        env={**os.environ, "PYTHONPATH": str(suite)},
        capture_output=True,
        text=True,
        timeout=GATE_TIMEOUT_S,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    workers = {p.name: p.read_text(encoding="utf-8") for p in report.iterdir()}
    assert len(workers) == 6, workers
    assert set(workers.values()) != {"serial"}, "the sandbox suite did not run in parallel"
    assert len(set(workers.values())) == 1, f"one group, two workers: {workers}"
