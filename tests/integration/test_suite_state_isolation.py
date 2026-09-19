"""The test suite must never write the real user's out-of-tree state.

Since ADR-0079/0082 the gate and the Stop hook keep state outside the governed tree,
under ``$XDG_STATE_HOME/borromeanrings`` (default ``~/.local/state``): the retry count
and the last-green record. Every test that runs the gate therefore wrote there — the
developer's real state directory held hundreds of entries left by test fixtures, mixed in
with the records of the projects they actually govern. ``tests/conftest.py`` points
``XDG_STATE_HOME`` at a per-session temporary directory before any test runs; this
proves it, and that a real gate run lands there and nowhere else.
"""

import os
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VERIFY = REPO / "verify.sh"
REAL_STATE = Path.home() / ".local" / "state" / "borromeanrings"


def _entries(root: Path) -> set[str]:
    return {p.name for p in root.iterdir()} if root.is_dir() else set()


def test_the_suite_state_home_is_a_private_temporary_directory() -> None:
    state = Path(os.environ["XDG_STATE_HOME"])
    assert state.is_absolute()
    assert state.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()), state
    assert state.resolve() != (Path.home() / ".local" / "state").resolve()


def test_a_gate_run_writes_its_state_under_the_suite_state_home(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "borromeanrings.toml").write_text(
        '[project]\nlanguage = "none"\n\n[checks]\nrequired = ["05_hygiene"]\n\n'
        "[hygiene]\nrequires = []\n",
        encoding="utf-8",
    )
    for argv in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
    ):
        subprocess.run(argv, cwd=project, capture_output=True, check=True)
    suite_state = Path(os.environ["XDG_STATE_HOME"]) / "borromeanrings"
    real_before, suite_before = _entries(REAL_STATE), _entries(suite_state)

    proc = subprocess.run(
        ["bash", str(VERIFY)],
        cwd=project,
        env={**os.environ, "BORROMEANRINGS_PROJECT": str(project)},
        capture_output=True,
        text=True,
        timeout=300,
    )

    assert "RESULT: PASS" in proc.stdout, proc.stdout + proc.stderr
    assert _entries(REAL_STATE) == real_before, "the gate wrote the real user's state"
    assert _entries(suite_state) - suite_before, "the passing gate recorded no state at all"
