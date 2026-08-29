"""End-to-end: the shell lint actually rejects bad shell, and is honest when there is none.

A check that only ever passes proves nothing (ADR-0049). These run the real ``verify.sh``
against fixture projects and assert both directions: a planted shell defect is rejected,
and a project with no shell at all reports ``noop`` rather than a hollow ``pass``.
"""

import json
import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
GATE_TIMEOUT_S = 120

CONFIG = (
    '[project]\nlanguage = "python"\nsrc_dir = "src"\n\n'
    '[checks]\nrequired = ["16_shellcheck"]\n\n[hygiene]\nrequires = []\n'
)


def _run_gate(project: Path) -> tuple[int, str, dict[str, str]]:
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(project)
    proc = subprocess.run(
        ["bash", str(VERIFY)], env=env, capture_output=True, text=True, timeout=GATE_TIMEOUT_S
    )
    statuses: dict[str, str] = {}
    runs = sorted(p for p in (project / ".meta-harness" / "receipts").glob("*") if p.is_dir())
    if runs:
        for receipt in runs[-1].glob("*.json"):
            try:
                statuses[receipt.stem] = json.loads(receipt.read_text()).get("status", "?")
            except (OSError, json.JSONDecodeError):
                statuses[receipt.stem] = "?"
    return proc.returncode, proc.stdout, statuses


def _git_project(root: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    for argv in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
    ):
        subprocess.run(argv, cwd=root, capture_output=True, check=False)
    return root


def test_planted_shell_defect_is_rejected(tmp_path: Path) -> None:
    """An unquoted expansion that word-splits on spaces — a real bug, not a style nit."""
    bad = '#!/usr/bin/env bash\nf() {\n  rm $1\n}\nf "$@"\n'
    project = _git_project(tmp_path / "badshell", {"borromeanrings.toml": CONFIG, "bad.sh": bad})
    code, stdout, statuses = _run_gate(project)
    assert code != 0, f"the gate must reject unlinted shell:\n{stdout}"
    assert statuses.get("16_shellcheck") == "fail"


def test_clean_shell_passes(tmp_path: Path) -> None:
    """Negative control: without it, a check that failed everything would look correct."""
    good = (
        '#!/usr/bin/env bash\nset -euo pipefail\nmain() {\n  printf \'%s\\n\' "$1"\n}\nmain "$@"\n'
    )
    project = _git_project(tmp_path / "goodshell", {"borromeanrings.toml": CONFIG, "ok.sh": good})
    code, stdout, statuses = _run_gate(project)
    assert code == 0, stdout
    assert statuses.get("16_shellcheck") == "pass"


def test_project_without_shell_is_noop_not_a_hollow_pass(tmp_path: Path) -> None:
    """No shell is legitimate for a pure-Python project — but say so, don't imply work."""
    project = _git_project(
        tmp_path / "noshell",
        {"borromeanrings.toml": CONFIG, "src/mod.py": "def f() -> None:\n    pass\n"},
    )
    code, stdout, statuses = _run_gate(project)
    assert code == 0, stdout
    assert statuses.get("16_shellcheck") == "noop"
    assert "inspected NOTHING" in stdout
