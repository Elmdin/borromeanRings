"""A gate run says where its own time went (#253, ADR-0085).

On 2026-09-19 `40_test` hit the 900s check bound on `dev` and the bound was raised to
1800s to unblock the merge queue. Nothing in the run recorded which check spent the time,
so the only way to find out was to re-run the suite locally under `--durations`. A bound
raised against no measurement is headroom, not a fix.

Each check now records its own wall time in its receipt, inside the content hash that
already protects the rest of the receipt, and the gate names the slowest few. It is a
report, not a rule: no budget, no threshold, and it never changes the verdict.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
GATE_TIMEOUT_S = 300

CONFIG = """\
[project]
language = "none"

[checks]
required = ["05_hygiene", "13_adr"]

[hygiene]
requires = ["LICENSE"]
"""


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "borromeanrings.toml").write_text(CONFIG, encoding="utf-8")
    (project / "LICENSE").write_text("MIT\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project, check=True)
    subprocess.run(["git", "add", "-A"], cwd=project, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=project,
        check=True,
    )
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


def _receipts(project: Path) -> dict[str, dict]:
    run_dir = sorted((project / ".meta-harness" / "receipts").glob("*/"))[-1]
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in run_dir.glob("*.json")}


def test_every_check_records_how_long_it_took(tmp_path: Path) -> None:
    project = _project(tmp_path)

    proc = _gate(project)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    receipts = _receipts(project)
    assert receipts, "the run wrote no receipts at all"
    for cid, receipt in receipts.items():
        ms = receipt.get("duration_ms")
        assert isinstance(ms, int), f"{cid} recorded no duration: {receipt.get('duration_ms')!r}"
        assert ms >= 0, f"{cid} recorded a negative duration"


def test_the_recorded_duration_is_covered_by_the_receipts_content_hash(tmp_path: Path) -> None:
    """Otherwise a slow check could be re-timed after the fact and the digest still
    match — a measurement nobody could rely on. The gate already fails closed on a
    receipt whose hash does not cover its own contents (ADR-0026)."""
    from meta_harness.receipts import read_log_text, verify_receipt

    project = _project(tmp_path)
    _gate(project)
    run_dir = sorted((project / ".meta-harness" / "receipts").glob("*/"))[-1]
    receipt = json.loads((run_dir / "05_hygiene.json").read_text(encoding="utf-8"))
    assert verify_receipt(receipt, read_log_text(receipt, str(run_dir))), "as written"

    retimed = {**receipt, "duration_ms": receipt["duration_ms"] + 1}

    assert not verify_receipt(retimed, read_log_text(retimed, str(run_dir)))


def test_the_gate_names_the_slowest_checks_of_the_run(tmp_path: Path) -> None:
    project = _project(tmp_path)

    proc = _gate(project)

    lines = [line.strip() for line in proc.stdout.splitlines() if "slowest:" in line]
    assert len(lines) == 1, proc.stdout
    named = lines[0]
    assert "05_hygiene" in named or "13_adr" in named, named
    assert "s" in named.split("slowest:")[1]


def test_the_measurement_never_changes_the_verdict(tmp_path: Path) -> None:
    """A slow check is a fact about the run, not a finding: there is no budget here."""
    project = _project(tmp_path)
    (project / "LICENSE").unlink()  # [hygiene].requires names it → 05_hygiene fails

    proc = _gate(project)

    assert proc.returncode != 0
    assert "RESULT: FAIL" in proc.stdout
    assert "slowest:" in proc.stdout, "the measurement is printed on a red run too"
