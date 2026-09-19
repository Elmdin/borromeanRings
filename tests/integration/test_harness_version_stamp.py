"""The gate stamps the governing borromeanRings version and its evidence into the verdict.

Locks the argv-threading contract at the bash/Python boundary (ADR-0048, ADR-0056): a
future refactor that mis-wires ``HARNESS_VERSION`` — or the receipt → evidence → verdict
plumbing — through ``verify.sh`` into the Python verdict step would still pass unit +
mutation tests (they can't see the shell seam), but would break here. Runs the real gate
ONCE against ``examples/textkit`` (module-scoped) and asserts what was printed and
persisted."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from meta_harness.receipts import CONTENT_HASH_FIELD
from meta_harness.verdict import RISK_BANDS, read_last_verdict, risk_band

REPO = Path(__file__).resolve().parents[2]
VERIFY = REPO / "verify.sh"
EXAMPLE = REPO / "examples" / "textkit"


@pytest.fixture(scope="module")
def gate_run() -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(EXAMPLE)
    result = subprocess.run(
        ["bash", str(VERIFY)],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, f"gate did not pass for textkit:\n{result.stdout}"
    return result


def _newest_run_dir() -> Path:
    receipts = EXAMPLE / ".meta-harness" / "receipts"
    runs = sorted(p for p in receipts.iterdir() if p.is_dir())
    assert runs, "no receipt run dir was created"
    return runs[-1]


def test_gate_prints_and_persists_the_harness_version(
    gate_run: subprocess.CompletedProcess[str],
) -> None:
    # (1) printed in the gate output
    assert "harness-version:" in gate_run.stdout

    # (2) persisted as a self-describing marker in the newest receipt bundle
    marker = _newest_run_dir() / "harness_version.txt"
    assert marker.is_file(), "harness_version.txt was not written into the receipt bundle"
    assert marker.read_text(encoding="utf-8").strip(), "harness_version.txt is empty"


def test_gate_persists_evidence_intent_and_risk_band(
    gate_run: subprocess.CompletedProcess[str],
) -> None:
    """Every required receipt is carried on the verdict as evidence, hash-for-hash."""
    verdict = read_last_verdict(EXAMPLE)
    assert verdict is not None
    run_dir = _newest_run_dir()
    assert verdict.run_id == run_dir.name

    # Risk band: printed, persisted, categorical, and re-derivable from the record.
    assert verdict.risk in RISK_BANDS
    assert verdict.risk == risk_band(verdict.checks)
    assert (
        f"  risk-band: {verdict.risk.upper()} · evidence: {len(verdict.evidence)} receipt(s)"
        in (gate_run.stdout)
    )

    # Evidence: one entry per required check, matching the receipt on disk.
    assert [e.check for e in verdict.evidence] == [cid for cid, _ in verdict.checks]
    for item in verdict.evidence:
        receipt = json.loads((run_dir / f"{item.check}.json").read_text(encoding="utf-8"))
        assert item.content_sha256 == receipt[CONTENT_HASH_FIELD]
        assert item.command == receipt["command"]
        assert item.exit_code == receipt["exit_code"]
        assert item.log == receipt["log"]
        assert item.log_bytes == os.path.getsize(item.log)
        assert item.lane == "fast"  # textkit was gated on the fast lane

    # Intent: read from git with a fixed argv — the example lives inside this repo.
    head = subprocess.check_output(["git", "-C", str(EXAMPLE), "rev-parse", "HEAD"], text=True)
    assert verdict.intent.head_sha == head.strip()
    assert verdict.intent.branch
    assert len(verdict.intent.input_digest) == 64  # sha256 hex of the gated inputs
