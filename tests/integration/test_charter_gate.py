"""End-to-end: the charter gate (22_charter) and the prompt-hook reminder (#173, ADR-0063).

Runs the real ``verify.sh`` against fixture projects for each state named in
SPEC-charter.md — rule off, valid, missing file, hedged predicate, unknown stakes — and
drives the real ``prompt_rewrite.sh`` over its stdin protocol for the one-line reminder.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
HOOK = BORROMEANRINGS_HOME / ".claude" / "hooks" / "prompt_rewrite.sh"
GATE_TIMEOUT_S = 120

OFF = '[checks]\nrequired = ["22_charter"]\n[hygiene]\nrequires = []\n'
ON = OFF + "[charter]\nenabled = true\n"
VALID = (
    'goal = "Keep the gate honest."\nstakes = "low"\n'
    'done_when = ["verify.sh exits 0"]\nstop_when = ["a ratchet regresses"]\n'
    'may_not = ["push"]\nowner = "maintainer"\n'
)


def _project(root: Path, config: str, charter: str | None) -> Path:
    root.mkdir()
    (root / "borromeanrings.toml").write_text(config, encoding="utf-8")
    if charter is not None:
        (root / "CHARTER.toml").write_text(charter, encoding="utf-8")
    return root


def _gate(project: Path) -> tuple[int, str, str]:
    """Run the gate; return (exit, stdout, the 22_charter log)."""
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(project)
    proc = subprocess.run(
        ["bash", str(VERIFY)], env=env, capture_output=True, text=True, timeout=GATE_TIMEOUT_S
    )
    runs = sorted(p for p in (project / ".meta-harness" / "receipts").glob("*") if p.is_dir())
    receipt = json.loads((runs[-1] / "22_charter.json").read_text(encoding="utf-8"))
    log = Path(receipt["log"]).read_text(encoding="utf-8")
    return proc.returncode, proc.stdout, f"{receipt['status']}\n{log}"


def test_rule_off_when_charter_not_declared(tmp_path: Path) -> None:
    code, out, log = _gate(_project(tmp_path / "p", OFF, None))
    assert code == 0 and "RESULT: PASS" in out
    assert log.startswith("pass\n") and "rule off" in log
    assert "NOOP" not in out  # never noop: off is a pass, a declared charter is judged


def test_valid_charter_passes_and_is_rendered(tmp_path: Path) -> None:
    code, out, log = _gate(_project(tmp_path / "p", ON, VALID))
    assert code == 0 and "RESULT: PASS" in out
    assert "charter OK — stakes: low; owner: maintainer" in log


def test_missing_charter_file_fails_naming_the_path(tmp_path: Path) -> None:
    project = _project(tmp_path / "p", ON, None)
    code, out, log = _gate(project)
    assert code == 1 and "RESULT: FAIL" in out
    assert log.startswith("fail\n")
    assert f"file — charter not found at {project / 'CHARTER.toml'}" in log


def test_hedged_predicate_fails_naming_the_item(tmp_path: Path) -> None:
    hedged = VALID.replace('"verify.sh exits 0"', '"it works"')
    code, out, log = _gate(_project(tmp_path / "p", ON, hedged))
    assert code == 1 and "RESULT: FAIL" in out
    assert 'done_when[0] — hedge, not a predicate: "it works"' in log


def test_unknown_stakes_fails_closed(tmp_path: Path) -> None:
    dial = VALID.replace('"low"', '"medium"')
    code, out, log = _gate(_project(tmp_path / "p", ON, dial))
    assert code == 1 and "RESULT: FAIL" in out
    assert 'stakes — must be "low" or "high", got "medium"' in log


# --- UserPromptSubmit reminder ------------------------------------------------


def _hook(project: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(project)
    env["BORROMEANRINGS_HOOK_DEDUPE_WINDOW"] = "0"
    payload = json.dumps({"session_id": "s-charter", "prompt": "build the thing"})
    return subprocess.run(
        ["bash", str(HOOK)], input=payload, env=env, capture_output=True, text=True, timeout=60
    )


def test_reminder_when_enabled_and_file_missing(tmp_path: Path) -> None:
    proc = _hook(_project(tmp_path / "p", ON, None))
    assert proc.returncode == 0
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("borromeanRings: [charter]")]
    assert lines == [
        "borromeanRings: [charter] is enabled but CHARTER.toml is missing — "
        "write it before governed work"
    ]
    assert len(lines[0].encode("utf-8")) < 120


def test_no_reminder_when_file_exists_or_rule_off(tmp_path: Path) -> None:
    # exists (even an invalid one: validity is the gate's job, not the prompt hook's)
    present = _hook(_project(tmp_path / "present", ON, "goal = 3\n"))
    assert present.returncode == 0 and "[charter]" not in present.stdout
    # not declared
    off = _hook(_project(tmp_path / "off", OFF, None))
    assert off.returncode == 0 and "[charter]" not in off.stdout
