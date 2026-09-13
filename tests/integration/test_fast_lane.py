"""The fast (interactive) lane, through the real gate. ADR-0081, issue #226.

The unit tests own the decision (:mod:`meta_harness.lane`); only a real ``verify.sh`` run
can show the decision is actually *wired* — that ``--fast`` reaches ``40_test`` through the
environment, that it narrows the suite, and, most importantly, that the narrowed PASS says
so in both the receipt and the gate output. A fast lane that could report a silent green
would be worse than a slow gate, so that is what these assertions are for.

Cost: three gate runs over a two-test fixture project, ~1 s each.

(``--heavy`` precedence is a pure decision, unit-tested in tests/unit/test_lane.py —
asserting it here would mean paying for a full CI-tier run per test session.)
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VERIFY = REPO / "verify.sh"

_CONFIG = '[project]\nlanguage = "python"\nsrc_dir = "src"\n[checks]\nrequired = ["40_test"]\n'
_FAST_CONFIG = _CONFIG + '\n[test]\nfast_paths = ["tests/unit"]\n'


def _fixture(root: Path, config: str) -> Path:
    """A governed project whose unit test passes and whose integration test FAILS."""
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "mod.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (root / "tests" / "unit").mkdir(parents=True, exist_ok=True)
    (root / "tests" / "unit" / "test_ok.py").write_text(
        "def test_ok() -> None:\n    assert True\n", encoding="utf-8"
    )
    (root / "tests" / "integration").mkdir(parents=True, exist_ok=True)
    (root / "tests" / "integration" / "test_slow.py").write_text(
        "def test_slow() -> None:\n    assert False, 'only the full lane sees me'\n",
        encoding="utf-8",
    )
    (root / "borromeanrings.toml").write_text(config, encoding="utf-8")
    return root


def _gate(project: Path, *args: str) -> tuple[int, str]:
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(project)
    env.pop("BORROMEANRINGS_LANE", None)
    result = subprocess.run(
        ["bash", str(VERIFY), *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return result.returncode, result.stdout + result.stderr


def _receipt(project: Path, check: str) -> dict[str, object]:
    runs = sorted(p for p in (project / ".meta-harness" / "receipts").iterdir() if p.is_dir())
    return json.loads((runs[-1] / f"{check}.json").read_text(encoding="utf-8"))


def test_declared_fast_paths_narrow_only_the_fast_lane(tmp_path: Path) -> None:
    project = _fixture(tmp_path / "declared", _FAST_CONFIG)

    code, out = _gate(project, "--fast")
    assert code == 0, f"the fast lane should have run tests/unit only:\n{out}"

    # ... and the full lane still runs the failing test the fast lane skipped.
    full_code, full_out = _gate(project)
    assert full_code != 0, f"the full lane must still run the whole suite:\n{full_out}"
    full_receipt = _receipt(project, "40_test")
    assert full_receipt["status"] == "fail"
    assert "lane" not in full_receipt, "the full lane must not label itself a fast one"


def test_a_fast_lane_pass_is_never_readable_as_a_full_pass(tmp_path: Path) -> None:
    project = _fixture(tmp_path / "marked", _FAST_CONFIG)
    code, out = _gate(project, "--fast")
    assert code == 0, out

    # (1) the verdict line itself
    assert "RESULT: PASS (FAST LANE)" in out
    assert "FAST LANE: a partial run" in out
    # (2) the check's row in the table
    assert "FAST LANE — only tests/unit" in out
    # (3) the receipt — the durable evidence, not just the console
    receipt = _receipt(project, "40_test")
    assert receipt["status"] == "pass"
    assert receipt["lane"] == "fast"
    assert receipt["fast_paths"] == ["tests/unit"]
    assert "coverage_percent" not in receipt, "the fast lane must not claim a coverage number"
    # (4) the persisted verdict a status view reads
    verdict = json.loads(
        (project / ".meta-harness" / "last_verdict.json").read_text(encoding="utf-8")
    )
    assert verdict["ok"] is True and verdict["lane"] == "fast"
    # (5) the log documents what was skipped and where it is caught instead
    log = Path(str(receipt["log"])).read_text(encoding="utf-8")
    assert "NOT run" in log and "CI" in log


def test_a_project_with_no_fast_paths_is_unaffected_by_the_fast_flag(tmp_path: Path) -> None:
    project = _fixture(tmp_path / "undeclared", _CONFIG)
    code, out = _gate(project, "--fast")
    assert code != 0, f"with nothing declared, --fast must run the whole suite:\n{out}"
    assert "FAST LANE" not in out, "a run that narrowed nothing must not claim a partial lane"
    receipt = _receipt(project, "40_test")
    assert "lane" not in receipt
    assert "coverage_percent" in receipt, "the coverage ratchet must still apply"
