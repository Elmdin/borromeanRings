"""``18_api_contracts`` end-to-end: fail on a violation, pass on compliant code, noop when
the rules matched nothing, rule off when nothing is declared, fail closed on bad rules."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
TIMEOUT_S = 180


def _gate(project: Path) -> tuple[int, dict[str, str], str]:
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(project)
    proc = subprocess.run(
        ["bash", str(VERIFY)], env=env, capture_output=True, text=True, timeout=TIMEOUT_S
    )
    runs = sorted(p for p in (project / ".meta-harness" / "receipts").glob("*") if p.is_dir())
    statuses: dict[str, str] = {}
    log = ""
    if runs:
        for receipt in runs[-1].glob("*.json"):
            statuses[receipt.stem] = json.loads(receipt.read_text()).get("status", "?")
        log_path = runs[-1] / "18_api_contracts.log"
        log = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    return proc.returncode, statuses, log


def _project(root: Path, source: str, contracts: str) -> Path:
    root.mkdir()
    (root / "borromeanrings.toml").write_text(
        '[project]\nlanguage = "python"\nsrc_dir = "src"\n'
        '[checks]\nrequired = ["18_api_contracts"]\n[hygiene]\nrequires = []\n' + contracts,
        encoding="utf-8",
    )
    (root / "src").mkdir()
    (root / "src" / "fw.py").write_text(source, encoding="utf-8")
    return root


RULES = '[[api_contracts.rules]]\nkind = "banned"\nsymbol = "malloc"\nmessage = "no heap"\n'


def test_violation_fails_the_gate_and_names_the_site(tmp_path: Path) -> None:
    project = _project(tmp_path / "p", "def boot():\n    buf = malloc(64)\n", RULES)
    code, statuses, log = _gate(project)
    assert code != 0 and statuses["18_api_contracts"] == "fail"
    assert "src/fw.py:2 [banned] malloc — no heap" in log


def test_compliant_code_passes(tmp_path: Path) -> None:
    project = _project(tmp_path / "p", "def boot():\n    x = malloc\n    stack_alloc(64)\n", RULES)
    # a bare reference is not a call; the call site that matched is stack_alloc? no — none.
    code, statuses, _ = _gate(project)
    assert statuses["18_api_contracts"] == "noop"
    project2 = _project(
        tmp_path / "q",
        "def boot():\n    rc = init()\n",
        '[[api_contracts.rules]]\nkind = "must_check"\nsymbol = "init"\n',
    )
    code, statuses, log = _gate(project2)
    assert code == 0 and statuses["18_api_contracts"] == "pass"
    assert "1 matching call site" in log


def test_rules_that_match_nothing_are_noop_not_pass(tmp_path: Path) -> None:
    project = _project(tmp_path / "p", "print('hello')\n", RULES)
    code, statuses, log = _gate(project)
    assert code == 0 and statuses["18_api_contracts"] == "noop"
    assert "inspected nothing" in log


def test_nothing_declared_is_rule_off(tmp_path: Path) -> None:
    project = _project(tmp_path / "p", "malloc(1)\n", "")
    code, statuses, log = _gate(project)
    assert code == 0 and statuses["18_api_contracts"] == "pass"
    assert "rule off" in log


def test_malformed_rule_fails_closed(tmp_path: Path) -> None:
    bad = '[[api_contracts.rules]]\nkind = "vibes"\nsymbol = "x"\n'
    project = _project(tmp_path / "p", "x()\n", bad)
    code, statuses, log = _gate(project)
    assert code != 0 and statuses["18_api_contracts"] == "fail"
    assert "unknown rule kind" in log


def test_shipped_pack_is_usable_by_reference(tmp_path: Path) -> None:
    project = _project(
        tmp_path / "p",
        "import asyncio\n\nasync def main():\n    asyncio.create_task(job())\n",
        '[api_contracts]\npacks = ["python-asyncio"]\n',
    )
    code, statuses, log = _gate(project)
    assert code != 0 and statuses["18_api_contracts"] == "fail"
    assert "docs.python.org" in log
