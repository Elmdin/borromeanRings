"""End-to-end: check ``23_predicates`` through the real ``verify.sh``.

Fixture projects exercise every status the SPEC promises — off, noop, hedge, orphan,
unreadable, pass — and the receipt status is read back from the run directory, not
inferred from the exit code. See docs/specs/SPEC-predicates.md and ADR-0064.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
GATE_TIMEOUT_S = 120

CONFIG_ON = (
    '[project]\nlanguage = "python"\n\n[checks]\nrequired = ["23_predicates"]\n\n'
    "[hygiene]\nrequires = []\n\n[predicates]\nenabled = true\n"
)
CONFIG_OFF = CONFIG_ON.replace("enabled = true", "enabled = false")
CLEAN_SPEC = "# SPEC — X\n\n## Contract\n- The gate fails closed; enforced by `05_hygiene`.\n"


def _project(root: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    return root


def _run_gate(project: Path) -> tuple[int, str, str]:
    """Run the real gate; return (exit code, receipt status, check log)."""
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(project)
    proc = subprocess.run(
        ["bash", str(VERIFY)], env=env, capture_output=True, text=True, timeout=GATE_TIMEOUT_S
    )
    run_dir = sorted((project / ".meta-harness" / "receipts").glob("*"))[-1]
    receipt = json.loads((run_dir / "23_predicates.json").read_text(encoding="utf-8"))
    log = (run_dir / "23_predicates.log").read_text(encoding="utf-8")
    return proc.returncode, str(receipt.get("status")), log


def test_off_is_noop_never_pass(tmp_path: Path) -> None:
    hedged = "# SPEC — X\n\n## Contract\n- The healthcheck is meaningful.\n"
    project = _project(
        tmp_path, {"borromeanrings.toml": CONFIG_OFF, "docs/specs/SPEC-x.md": hedged}
    )
    code, status, log = _run_gate(project)
    assert code == 0 and status == "noop"
    assert "rule off" in log


def test_no_predicates_is_noop(tmp_path: Path) -> None:
    project = _project(
        tmp_path, {"borromeanrings.toml": CONFIG_ON, "docs/specs/notes.md": "## Contract\n- x\n"}
    )
    code, status, log = _run_gate(project)
    assert code == 0 and status == "noop"
    assert "no predicates found" in log


def test_hedged_predicate_fails_naming_file_line_and_hedge(tmp_path: Path) -> None:
    spec = "# SPEC — X\n\n## Contract\n- Keys rotate as needed; enforced by `05_hygiene`.\n"
    project = _project(tmp_path, {"borromeanrings.toml": CONFIG_ON, "docs/specs/SPEC-x.md": spec})
    code, status, log = _run_gate(project)
    assert code != 0 and status == "fail"
    assert (
        "docs/specs/SPEC-x.md:4 — Keys rotate as needed; enforced by `05_hygiene`. — as needed"
        in log
    )


def test_orphan_spec_fails_and_is_listed(tmp_path: Path) -> None:
    orphan = "# SPEC — Y\n\n## Contract\n- Something holds, referenced by nothing.\n"
    project = _project(
        tmp_path,
        {
            "borromeanrings.toml": CONFIG_ON,
            "docs/specs/SPEC-x.md": CLEAN_SPEC,
            "docs/specs/SPEC-y.md": orphan,
        },
    )
    code, status, log = _run_gate(project)
    assert code != 0 and status == "fail"
    assert "ORPHAN" in log and "docs/specs/SPEC-y.md" in log
    assert "docs/specs/SPEC-x.md" not in log


def test_reference_to_an_existing_test_file_rescues_a_spec(tmp_path: Path) -> None:
    spec = "# SPEC — Y\n\n## Contract\n- Verified by test_y.py.\n"
    project = _project(
        tmp_path,
        {
            "borromeanrings.toml": CONFIG_ON,
            "docs/specs/SPEC-y.md": spec,
            "tests/unit/test_y.py": "def test_y() -> None:\n    pass\n",
        },
    )
    code, status, _log = _run_gate(project)
    assert code == 0 and status == "pass"


def test_unreadable_file_fails_closed(tmp_path: Path) -> None:
    project = _project(
        tmp_path, {"borromeanrings.toml": CONFIG_ON, "docs/specs/SPEC-x.md": CLEAN_SPEC}
    )
    (project / "docs/specs/SPEC-bad.md").write_bytes(b"# SPEC\n\n## Contract\n- \xff\xfe broken\n")
    code, status, log = _run_gate(project)
    assert code != 0 and status == "fail"
    assert "could not be read" in log and "SPEC-bad.md" in log


def test_clean_predicates_pass_with_counts(tmp_path: Path) -> None:
    adr = "# ADR-0001\n\n## Consequences\n- (+) The gate must stay fail-closed.\n"
    project = _project(
        tmp_path,
        {
            "borromeanrings.toml": CONFIG_ON,
            "docs/specs/SPEC-x.md": CLEAN_SPEC,
            "docs/adr/0001-x.md": adr,
        },
    )
    code, status, log = _run_gate(project)
    assert code == 0 and status == "pass"
    assert "2 predicate(s) in 2 document(s); 0 hedged; 1 SPEC(s) referenced" in log


def test_spec_without_predicates_or_reference_fails_not_noop(tmp_path: Path) -> None:
    """The noop rule needs both: nothing to lint AND no orphan (fail-closed)."""
    project = _project(
        tmp_path,
        {"borromeanrings.toml": CONFIG_ON, "docs/specs/SPEC-z.md": "# S\n\n## Problem\nProse.\n"},
    )
    code, status, log = _run_gate(project)
    assert code != 0 and status == "fail"
    assert "ORPHAN" in log and "docs/specs/SPEC-z.md" in log


def test_unreadable_spine_fails_closed_not_noop(tmp_path: Path) -> None:
    """A malformed borromeanrings.toml must not be reported as 'rule off' (noop)."""
    broken = 'this is = not [valid toml\n[checks]\nrequired = ["23_predicates"\n'
    project = _project(
        tmp_path, {"borromeanrings.toml": broken, "docs/specs/SPEC-x.md": CLEAN_SPEC}
    )
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(project)
    subprocess.run(
        ["bash", str(VERIFY)], env=env, capture_output=True, text=True, timeout=GATE_TIMEOUT_S
    )
    run_dir = sorted((project / ".meta-harness" / "receipts").glob("*"))[-1]
    receipt = json.loads((run_dir / "23_predicates.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "fail"
    assert "failing closed" in (run_dir / "23_predicates.log").read_text(encoding="utf-8")
