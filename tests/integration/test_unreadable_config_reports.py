"""A config the gate cannot read gets a verdict, not a stack trace (audit 2026-09-20).

`borromeanrings.toml` is what configures the gate, so a config that will not parse is the
one failure the gate cannot delegate to a check. The design is deliberate that it does
not refuse the run — every check fails closed on its own and writes a receipt saying why,
which is better evidence than one message and no receipts (ADR-0042, and
`test_supply_chain_gate.py::test_unreadable_spine_fails_closed_not_noop` pins it).

What was not deliberate: the verdict step then died on the same config, so the run ended
in a Python traceback with **no verdict at all** — and every check's own config read threw
another one, eighteen in a single run. A gate that answers with stack traces has not
answered.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
GATE_TIMEOUT_S = 300

BROKEN = '[project\nlanguage = "go"\n\n[checks]\nrequired = ["05_hygiene"]\n'


def _project(tmp_path: Path, config: str) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "borromeanrings.toml").write_text(config, encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project, check=True)
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


def test_an_unparseable_config_still_ends_in_a_verdict(tmp_path: Path) -> None:
    project = _project(tmp_path, BROKEN)

    proc = _gate(project)
    out = proc.stdout + proc.stderr

    assert proc.returncode != 0
    assert "RESULT: FAIL" in proc.stdout, out
    assert "cannot read" in proc.stdout, out
    assert "borromeanrings.toml" in proc.stdout, out


def test_the_reason_is_a_sentence_not_a_stack_trace(tmp_path: Path) -> None:
    """Each check's config read reports one line now. One inline block inside a check
    still raises — the remaining `borromeanrings_project_cfg`-family sites are tracked on
    #186 — so this asserts the count is far below one-per-check rather than zero."""
    project = _project(tmp_path, BROKEN)

    proc = _gate(project)
    out = proc.stdout + proc.stderr

    ran = len(list((project / ".meta-harness" / "receipts").glob("*/*.json")))
    assert ran > 5, "the checks did run and wrote receipts"
    assert out.count("Traceback (most recent call last)") <= 2, out
    assert "cannot read language from" in out or "cannot read" in out, out


def test_a_language_that_cannot_be_read_says_which_lane_ran(tmp_path: Path) -> None:
    """The fallback is deliberate, but WHICH LANE runs is decided by it: silently
    choosing python means a Go project is checked by tools that find no source and report
    "nothing to inspect". The reader is told, so "nothing ran" has a reason."""
    project = _project(tmp_path, BROKEN)

    proc = _gate(project)

    assert "could not read [project].language" in proc.stderr, proc.stderr
    assert "'python' lane" in proc.stderr, proc.stderr


def test_an_unreadable_config_records_the_failure_it_reports(tmp_path: Path) -> None:
    """The run exited before writing its verdict, so `.meta-harness/last_verdict.json`
    still held the PREVIOUS run and `status.sh` reported a green that did not happen
    (review of #261). A record with no checks is the honest statement: nothing was
    graded, and the run failed."""
    import json

    project = _project(
        tmp_path,
        '[project]\nlanguage = "none"\n\n'
        '[checks]\nrequired = ["05_hygiene"]\n\n[hygiene]\nrequires = []\n',
    )
    assert _gate(project).returncode == 0, "the config parses, so this run is green"
    record = project / ".meta-harness" / "last_verdict.json"
    assert json.loads(record.read_text(encoding="utf-8"))["ok"] is True

    (project / "borromeanrings.toml").write_text(BROKEN, encoding="utf-8")
    proc = _gate(project)

    assert proc.returncode != 0
    assert json.loads(record.read_text(encoding="utf-8"))["ok"] is False, (
        "the stale green survived a run that could not read the config"
    )
