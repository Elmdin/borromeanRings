"""borromeanRings governs a *second, different-archetype* project end-to-end.

Runs the real gate against the `examples/textkit` library (its own
``borromeanrings.toml``, a plain library — not the meta-harness) and asserts it
passes. This makes the portability claim ("enforces best practices for any
project") a permanent regression check. See examples/textkit/README.md."""

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VERIFY = REPO / "verify.sh"
EXAMPLE = REPO / "examples" / "textkit"


def test_borromeanrings_governs_the_example_library() -> None:
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
    assert "RESULT: PASS" in result.stdout
