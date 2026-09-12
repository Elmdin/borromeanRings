"""The gate stamps the governing borromeanRings version into its output + evidence.

Locks the argv-threading contract at the bash/Python boundary (ADR-0048): a future
refactor that mis-wires ``HARNESS_VERSION`` through ``verify.sh`` into the Python
verdict step would still pass unit + mutation tests (they can't see the shell seam),
but would break here. Runs the real gate against ``examples/textkit`` and asserts the
version is both printed and persisted into the receipt bundle."""

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VERIFY = REPO / "verify.sh"
EXAMPLE = REPO / "examples" / "textkit"


def test_gate_prints_and_persists_the_harness_version() -> None:
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
    # (1) printed in the gate output
    assert "harness-version:" in result.stdout

    # (2) persisted as a self-describing marker in the newest receipt bundle
    receipts = EXAMPLE / ".meta-harness" / "receipts"
    runs = sorted(p for p in receipts.iterdir() if p.is_dir())
    assert runs, "no receipt run dir was created"
    marker = runs[-1] / "harness_version.txt"
    assert marker.is_file(), "harness_version.txt was not written into the receipt bundle"
    assert marker.read_text(encoding="utf-8").strip(), "harness_version.txt is empty"
