"""A ratchet whose measurement failed has no measurement to compare (#186, ADR-0088).

`32_complexity`, `33_coupling` and `45_docstrings` each measure the project, read a
baseline, and fail when the measurement is worse. The measurement was taken like this:

    read -r current worst < <(… borromeanrings_py - … <<'PY' … PY)

Process substitution *discards* the exit status — worse than `|| true`, because `$?`
afterwards belongs to `read`, so even a careful author checking it is told the wrong
thing. A crashed measurement leaves `current` empty, `[ "" -gt 100000 ]` errors, the
comparison does not fire, and the check reports `pass`: a ratchet that ratchets nothing.

The baseline had the same shape from the other side: `cat file 2>/dev/null || echo 0`
turns an *unreadable* baseline into the most permissive one.

Both are forced here for real — the source the measurement must read cannot be opened,
and the baseline that exists cannot be read — against a project that otherwise passes.
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

CHECKS = ["32_complexity", "33_coupling", "45_docstrings"]
BASELINES = {
    "32_complexity": ".borromeanrings-complexity-baseline",
    "33_coupling": ".borromeanrings-coupling-baseline",
    "45_docstrings": ".borromeanrings-docstring-baseline",
}

CONFIG = """\
[project]
language = "python"
package = "thing"
src_dir = "src"

[checks]
required = ["{check}"]
"""

INIT = '''"""The package, re-exporting its one helper."""

from thing.util import add

__all__ = ["add"]
'''

#: A second module, because `45_docstrings` skips `__init__.py` and `33_coupling`
#: measures imports BETWEEN modules — with one file there is nothing to measure, and
#: the test below would be making a source unreadable that nobody reads.
UTIL = '''"""One documented function."""


def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
'''


def _project(tmp_path: Path, check: str) -> Path:
    project = tmp_path / "proj"
    (project / "src" / "thing").mkdir(parents=True)
    (project / "borromeanrings.toml").write_text(CONFIG.format(check=check), encoding="utf-8")
    (project / "src" / "thing" / "__init__.py").write_text(INIT, encoding="utf-8")
    (project / "src" / "thing" / "util.py").write_text(UTIL, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "add", "-A"], cwd=project, check=True)
    return project


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


@pytest.mark.parametrize("check", CHECKS)
def test_the_ratchet_passes_when_the_measurement_works(tmp_path: Path, check: str) -> None:
    """The control: this project is simple and documented, so a working measurement
    passes. Without it, the test below proves nothing about *why* the check failed."""
    project = _project(tmp_path, check)

    proc = _gate(project)
    status, log = _receipt(project, check)

    assert status == "pass", log
    assert proc.returncode == 0, proc.stdout


@pytest.mark.parametrize("check", CHECKS)
@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a mode-000 file anyway")
def test_a_failed_measurement_fails_closed(tmp_path: Path, check: str) -> None:
    """The measurement is made to fail for real — the source it must read cannot be
    opened — against a project that otherwise passes."""
    project = _project(tmp_path, check)
    source = project / "src" / "thing" / "util.py"
    source.chmod(0)

    try:
        proc = _gate(project)
        status, log = _receipt(project, check)
    finally:
        source.chmod(0o644)

    assert status == "fail", f"{check} ratcheted against a measurement it never got:\n{log}"
    assert proc.returncode != 0


@pytest.mark.parametrize("check", CHECKS)
@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a mode-000 file anyway")
def test_an_unreadable_baseline_fails_closed(tmp_path: Path, check: str) -> None:
    """`cat file 2>/dev/null || echo <permissive default>` turns a baseline that exists
    but cannot be read into the most permissive one — the ratchet silently switches
    off. Absent is a default; unreadable is a failure."""
    project = _project(tmp_path, check)
    baseline = project / BASELINES[check]
    baseline.write_text("0\n", encoding="utf-8")
    baseline.chmod(0)

    try:
        proc = _gate(project)
        status, log = _receipt(project, check)
    finally:
        baseline.chmod(0o644)

    assert status == "fail", f"{check} read an unreadable baseline as permissive:\n{log}"
    assert proc.returncode != 0
