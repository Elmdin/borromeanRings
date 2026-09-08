"""End-to-end: ``19_context_budget`` ratchets what borromeanRings puts in context.

Runs the real ``verify.sh`` against fixture projects and asserts the three outcomes
that must stay distinct: a total at/below the baseline **passes** (and the log lists
the rows); a total above it **fails** naming both numbers; a project with nothing
measurable is **noop**, never a hollow pass. An unreadable baseline fails closed.
See docs/specs/SPEC-context-budget.md and ADR-0055.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
GATE_TIMEOUT_S = 120
BASELINE = ".borromeanrings-context-baseline"

CONFIG = (
    '[project]\nlanguage = "python"\nsrc_dir = "src"\n\n'
    '[checks]\nrequired = ["19_context_budget"]\n\n[hygiene]\nrequires = []\n'
)
SKILL = "---\nname: demo\ndescription: forty bytes of always-loaded text.\n---\n"


def _run_gate(project: Path) -> tuple[int, str, str, str]:
    """Run the gate against ``project``; return (exit, stdout, check status, check log)."""
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(project)
    proc = subprocess.run(
        ["bash", str(VERIFY)], env=env, capture_output=True, text=True, timeout=GATE_TIMEOUT_S
    )
    receipts = project / ".meta-harness" / "receipts"
    run_dir = sorted(p for p in receipts.glob("*") if p.is_dir())[-1]
    status = json.loads((run_dir / "19_context_budget.json").read_text())["status"]
    log = (run_dir / "19_context_budget.log").read_text(encoding="utf-8")
    return proc.returncode, proc.stdout, status, log


def _project(root: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    return root


def test_total_at_baseline_passes_and_logs_the_rows(tmp_path: Path) -> None:
    project = _project(
        tmp_path / "ok",
        {
            "borromeanrings.toml": CONFIG,
            "skills/demo/SKILL.md": SKILL,
            BASELINE: f"{len(SKILL.encode())}\n",
        },
    )
    code, stdout, status, log = _run_gate(project)
    assert code == 0, stdout
    assert status == "pass"
    assert "skill" in log and "skills/demo/SKILL.md" in log
    assert f"TOTAL        {len(SKILL.encode()):>6} B" in log
    assert "REGRESSION" not in log


def test_total_above_baseline_fails_naming_both_numbers(tmp_path: Path) -> None:
    project = _project(
        tmp_path / "regressed",
        {"borromeanrings.toml": CONFIG, "skills/demo/SKILL.md": SKILL, BASELINE: "10\n"},
    )
    code, stdout, status, log = _run_gate(project)
    assert code != 0, f"a total above the baseline must FAIL:\n{stdout}"
    assert status == "fail"
    assert f"CONTEXT-BUDGET REGRESSION: {len(SKILL.encode())} is above baseline 10" in log
    assert "accept the new baseline deliberately" in log


def test_nothing_measurable_is_noop_not_pass(tmp_path: Path) -> None:
    project = _project(tmp_path / "bare", {"borromeanrings.toml": CONFIG, BASELINE: "0\n"})
    code, stdout, status, _log = _run_gate(project)
    assert code == 0, stdout
    assert status == "noop"
    assert "inspected NOTHING" in stdout


def test_missing_baseline_is_vacuous_until_seeded(tmp_path: Path) -> None:
    project = _project(
        tmp_path / "unseeded", {"borromeanrings.toml": CONFIG, "skills/demo/SKILL.md": SKILL}
    )
    code, stdout, status, log = _run_gate(project)
    assert code == 0, stdout
    assert status == "pass"
    assert "no baseline recorded" in log


def test_unreadable_baseline_fails_closed(tmp_path: Path) -> None:
    project = _project(
        tmp_path / "garbage",
        {"borromeanrings.toml": CONFIG, "skills/demo/SKILL.md": SKILL, BASELINE: "lots\n"},
    )
    code, stdout, status, log = _run_gate(project)
    assert code != 0, f"an unparseable baseline must fail closed:\n{stdout}"
    assert status == "fail"
    assert "unreadable baseline" in log
