"""#222: the Stop hook must not stand down because the project said so.

The hook has three ways to exit 0 without running the gate, and all three used to
be reachable by writing a file inside the governed tree:

1. the no-op skip, which compared an unkeyed hash against an in-tree record;
2. the duplicate-run claim, which believed a marker's mtime;
3. a planted ``meta_harness``/``json`` module, which replaced the hook's own code.

Each test below first proves the forgery is *live* — that the planted artefact is
exactly what the old code would have believed — and only then asserts the gate ran
anyway. A test that skipped the first half would pass against a hook that had
simply stopped working.

The bound this proves is the realistic one: an agent confined to the project
directory. It is NOT a bound against intent — the gate runs the project's own test
code as the user, so that code can reach ``$HOME`` like any same-user process. A
real bound needs isolated execution (#144/#145).
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from meta_harness.change_detect import compute_state_hash
from meta_harness.hook_dedupe import claim
from meta_harness.spine import load_config

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
STOP_GATE = BORROMEANRINGS_HOME / ".claude" / "hooks" / "stop_gate.sh"
SESSION = "sess-222"

# A config whose gate fails fast: 05_hygiene wants a file that is not there.
FAILING_CONFIG = (
    '[project]\nlanguage = "none"\npackage = "x"\n\n'
    '[checks]\nrequired = ["05_hygiene"]\n\n'
    '[hygiene]\nrequires = ["does-not-exist.md"]\n'
)


def _project(root: Path) -> Path:
    project = root / "project"
    project.mkdir()
    (project / "borromeanrings.toml").write_text(FAILING_CONFIG, encoding="utf-8")
    return project


def _env(tmp_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["XDG_STATE_HOME"] = str(tmp_path / "state")
    env["HOME"] = str(tmp_path / "home")
    env["CLAUDE_CONFIG_DIR"] = str(tmp_path / "claude-config")
    return env


def _stop(project: Path, env: dict[str, str], session: str = SESSION):
    run_env = dict(env)
    run_env["CLAUDE_PROJECT_DIR"] = str(project)
    return subprocess.run(
        ["bash", str(STOP_GATE)],
        input=json.dumps({"session_id": session, "stop_hook_active": False}),
        capture_output=True,
        text=True,
        timeout=180,
        env=run_env,
        cwd=project,
    )


def _assert_gate_ran(result: subprocess.CompletedProcess[str], project: Path) -> None:
    """The gate ran and said no: a retry block, plus receipts on disk to prove it."""
    assert result.returncode == 2, (
        f"the hook stood down instead of gating (rc={result.returncode}): "
        f"{result.stderr.splitlines()[:2]}"
    )
    assert "gate FAILED" in result.stderr, result.stderr.splitlines()[:2]
    receipts = project / ".meta-harness" / "receipts"
    assert receipts.is_dir() and any(receipts.iterdir()), "no receipts — no gate run"


def test_a_forged_last_green_record_does_not_stop_the_gate(tmp_path: Path) -> None:
    """Route 1: the exact hash the skip compares against, planted in the tree."""
    project = _project(tmp_path)
    config = load_config(project / "borromeanrings.toml")
    planted = project / ".meta-harness" / "last_green_state"
    planted.parent.mkdir(parents=True)
    planted.write_text(compute_state_hash(project, config), encoding="utf-8")

    # The forgery is live: this is byte-for-byte the value the comparison wanted.
    assert planted.read_text(encoding="utf-8") == compute_state_hash(project, config)

    _assert_gate_ran(_stop(project, _env(tmp_path)), project)


def test_a_future_dated_claim_marker_does_not_stop_the_gate(tmp_path: Path) -> None:
    """Route 2: one `touch -d tomorrow` used to shadow every Stop, forever."""
    project = _project(tmp_path)
    env = _env(tmp_path)

    # Build the marker through the hook's own claim(), so its name is exactly the
    # one the hook will look for. (The hook releases its own marker on exit, so
    # there is nothing left over from a previous Stop to forge.)
    markers_dir = project / ".meta-harness" / "hook_markers"
    assert claim(markers_dir, "stop", SESSION) is True
    marker = next(markers_dir.iterdir())

    tomorrow = time.time() + 86_400
    os.utime(marker, (tomorrow, tomorrow))
    assert time.time() - marker.stat().st_mtime < 0  # would read as "fresh" forever

    _assert_gate_ran(_stop(project, env, session=SESSION), project)


def test_a_planted_module_does_not_stop_the_gate(tmp_path: Path) -> None:
    """Route 3: the hook's Python must not import the project's code (#221 D2).

    A ``meta_harness`` package in the project would otherwise replace the hook's
    own modules — including the one that decides whether to skip.
    """
    project = _project(tmp_path)
    shadow = project / "meta_harness"
    shadow.mkdir()
    (shadow / "__init__.py").write_text("", encoding="utf-8")
    (shadow / "change_detect.py").write_text(
        "def should_skip_gate(*_a, **_k):\n    return True\n", encoding="utf-8"
    )
    (project / "json.py").write_text(
        "def load(fp):\n    return {'session_id': 'x', 'stop_hook_active': False}\n"
        "def loads(s, **kw):\n    return load(None)\n"
        "def dumps(o, **kw):\n    return '{}'\n",
        encoding="utf-8",
    )

    # The attack is live: a naive interpreter started here really does pick it up.
    probe = subprocess.run(
        ["python3", "-c", "import meta_harness.change_detect as m; print(m.__file__)"],
        capture_output=True,
        text=True,
        cwd=project,
        env={**_env(tmp_path), "PYTHONPATH": str(BORROMEANRINGS_HOME / "src")},
        timeout=60,
    )
    assert probe.stdout.strip() == str(shadow / "change_detect.py"), probe.stderr

    _assert_gate_ran(_stop(project, _env(tmp_path)), project)
