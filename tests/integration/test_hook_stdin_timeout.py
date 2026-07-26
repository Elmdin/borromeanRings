"""Hooks must never hang on an unclosed stdin pipe.

Regression for the orphaned-shell bug: substrate hook payloads arrive on stdin,
and the hooks read them with an unbounded ``cat``. When the substrate did not
close the pipe's write end promptly, ``cat`` blocked forever waiting for EOF —
leaving an idle shell parked in the process table for the rest of the session
(observed: one 51 hours old). The fix bounds the read with coreutils
``timeout``/``gtimeout`` (``BORROMEANRINGS_HOOK_STDIN_TIMEOUT``, default 5s) —
the same fallback contract as ``checks/_lib.sh``.

Each test starts a hook with stdin held OPEN (write end never closed) and
asserts the hook exits on its own instead of hanging.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
HOOKS = BORROMEANRINGS_HOME / ".claude" / "hooks"

pytestmark = pytest.mark.skipif(
    shutil.which("timeout") is None and shutil.which("gtimeout") is None,
    reason="no coreutils `timeout`/`gtimeout` to bound the stdin read with",
)


def _governed_project(tmp_path: Path) -> Path:
    """A minimal governed project whose gate is cheap (no language check dir)."""
    (tmp_path / "borromeanrings.toml").write_text(
        '[project]\nlanguage = "none"\npackage = "x"\n\n'
        '[checks]\nrequired = ["05_hygiene"]\n\n'
        "[hygiene]\nrequires = []\n"
    )
    return tmp_path


def _assert_hook_exits(project: Path, hook: str, wait: float) -> None:
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(project)
    env["BORROMEANRINGS_HOOK_STDIN_TIMEOUT"] = "1"
    proc = subprocess.Popen(
        ["bash", str(HOOKS / hook)],
        stdin=subprocess.PIPE,  # held open: never written to, never closed
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    try:
        proc.wait(timeout=wait)
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail(f"{hook} hung on an unclosed stdin pipe (orphaned-shell regression)")
    finally:
        if proc.stdin is not None:
            proc.stdin.close()


def test_pre_bash_guard_exits_with_stdin_held_open(tmp_path: Path) -> None:
    _assert_hook_exits(_governed_project(tmp_path), "pre_bash_guard.sh", wait=20)


def test_post_edit_format_exits_with_stdin_held_open(tmp_path: Path) -> None:
    _assert_hook_exits(_governed_project(tmp_path), "post_edit_format.sh", wait=20)


def test_prompt_rewrite_exits_with_stdin_held_open(tmp_path: Path) -> None:
    _assert_hook_exits(_governed_project(tmp_path), "prompt_rewrite.sh", wait=20)


def test_stop_gate_exits_with_stdin_held_open(tmp_path: Path) -> None:
    # Runs the (cheap) gate after the bounded read times out, so allow for it.
    _assert_hook_exits(_governed_project(tmp_path), "stop_gate.sh", wait=90)
