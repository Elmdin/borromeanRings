"""A hanging check must fail-closed under a wall-clock timeout, not hang the gate.

Regression for the orphaned-pytest bug: a networked test in a governed project
blocked on a socket and hung borromeanRings's gate until the 600s Stop-hook timeout,
leaking one pytest process per run. The fix bounds every check's tool invocation
with coreutils `timeout` so a hang becomes a FAIL receipt (exit 124), promptly.

The check layer is bash (`checks/_lib.sh`), so this drives `run_check` via a small
bash harness in a subprocess and inspects the receipt it writes.
"""

import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[1]
LIB = BORROMEANRINGS_HOME / "checks" / "_lib.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("timeout") is None and shutil.which("gtimeout") is None,
    reason="no coreutils `timeout`/`gtimeout` to bound checks with",
)


def _run_check(tmp_path: Path, *, check_id: str, tool: str, cmd: str, env_timeout: str) -> Path:
    """Source _lib.sh and invoke run_check; return the receipt dir."""
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    harness = (
        f"export PROJECT_ROOT={tmp_path!s}\n"
        f"export RECEIPT_DIR={receipts!s}\n"
        f"export BORROMEANRINGS_HOME={BORROMEANRINGS_HOME!s}\n"
        f"export BORROMEANRINGS_CHECK_TIMEOUT={env_timeout}\n"
        f"source {LIB!s}\n"
        f'run_check "{check_id}" "{tool}" "{cmd}" || true\n'
    )
    # Outer timeout is a backstop only: if run_check were still unbounded, this raises
    # TimeoutExpired and the test fails loudly rather than hanging the suite.
    subprocess.run(["bash", "-c", harness], check=True, timeout=20)
    return receipts


def test_hanging_check_is_bounded_and_fails_closed(tmp_path: Path) -> None:
    start = time.monotonic()
    receipts = _run_check(
        tmp_path, check_id="99_hang", tool="sleep", cmd="sleep 30", env_timeout="1"
    )
    elapsed = time.monotonic() - start

    assert elapsed < 15, f"check was not bounded: took {elapsed:.1f}s for a 1s limit"

    receipt = json.loads((receipts / "99_hang.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "fail", "a timed-out check must fail closed, never pass"
    assert receipt["exit_code"] == 124, "wall-clock timeout should surface as exit 124"

    log = (receipts / "99_hang.log").read_text(encoding="utf-8")
    assert "TIMED OUT" in log, "the log must say it timed out, for diagnosability"


def test_fast_check_still_passes_under_the_timeout(tmp_path: Path) -> None:
    receipts = _run_check(tmp_path, check_id="99_ok", tool="true", cmd="true", env_timeout="30")
    receipt = json.loads((receipts / "99_ok.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "pass"
    assert receipt["exit_code"] == 0
