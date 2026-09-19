"""The PreCompact / SessionStart hooks, driven over their stdin protocol (#137).

Each hook is a thin adapter over ``meta_harness.compaction_brief``. These tests run the
real scripts with the JSON Claude Code sends, against a fixture project, and assert the
externally visible contract: what is written, what is printed, and that neither ever
blocks (exit 0) — even on garbage input or an ungoverned directory.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
PRE = BORROMEANRINGS_HOME / ".claude" / "hooks" / "pre_compact.sh"
START = BORROMEANRINGS_HOME / ".claude" / "hooks" / "session_start.sh"


def _project(root: Path) -> Path:
    root.mkdir()
    (root / "borromeanrings.toml").write_text(
        '[checks]\nrequired = ["13_adr"]\n[git]\nname = "wimaan3"\nemail = "d@x"\n',
        encoding="utf-8",
    )
    (root / ".meta-harness").mkdir()
    (root / ".meta-harness" / "last_verdict.json").write_text(
        json.dumps({"ok": False, "run_id": "r7", "checks": [["13_adr", "fail"]]}),
        encoding="utf-8",
    )
    return root


def _run(script: Path, project: Path, payload: object) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(project)
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        ["bash", str(script)], input=stdin, env=env, capture_output=True, text=True, timeout=60
    )


def test_pre_compact_snapshots_the_brief_and_never_blocks(tmp_path: Path) -> None:
    project = _project(tmp_path / "p")
    proc = _run(PRE, project, {"hook_event_name": "PreCompact", "trigger": "auto"})
    assert proc.returncode == 0
    snap = (project / ".meta-harness" / "compaction_brief.txt").read_text(encoding="utf-8")
    assert snap.startswith("# snapshot ") and "(trigger: auto)" in snap.splitlines()[0]
    assert "Last gate: FAIL (run r7" in snap
    assert "13_adr: FAIL — fix before the next Stop gate" in snap
    assert "wimaan3 <d@x>" in snap


def test_session_start_reinjects_on_compact_and_resume_only(tmp_path: Path) -> None:
    project = _project(tmp_path / "p")
    for trigger in ("compact", "resume"):
        proc = _run(START, project, {"hook_event_name": "SessionStart", "trigger": trigger})
        assert proc.returncode == 0
        assert "borromeanRings context restored after compaction" in proc.stdout
        assert "13_adr: FAIL" in proc.stdout
    for trigger in ("startup", "clear", "fork"):
        proc = _run(START, project, {"hook_event_name": "SessionStart", "trigger": trigger})
        assert proc.returncode == 0
        assert proc.stdout == ""


def test_session_start_reads_fresh_state_not_the_snapshot(tmp_path: Path) -> None:
    """A gate that ran between compaction and restart must be what gets re-injected."""
    project = _project(tmp_path / "p")
    _run(PRE, project, {"trigger": "manual"})
    (project / ".meta-harness" / "last_verdict.json").write_text(
        json.dumps({"ok": True, "run_id": "r8", "checks": [["13_adr", "pass"]]}),
        encoding="utf-8",
    )
    proc = _run(START, project, {"trigger": "compact"})
    assert "Last gate: PASS (run r8" in proc.stdout
    assert "Open obligations: none recorded" in proc.stdout


def test_hooks_are_inert_outside_a_governed_project(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    for script in (PRE, START):
        proc = _run(script, plain, {"trigger": "compact"})
        assert (proc.returncode, proc.stdout) == (0, "")
    assert not (plain / ".meta-harness").exists()


def test_hooks_survive_garbage_stdin(tmp_path: Path) -> None:
    project = _project(tmp_path / "p")
    for script in (PRE, START):
        proc = _run(script, project, "{not json")
        assert proc.returncode == 0, proc.stderr
    snap = (project / ".meta-harness" / "compaction_brief.txt").read_text(encoding="utf-8")
    assert "(trigger: unknown)" in snap


def test_session_start_dedupes_a_concurrent_duplicate(tmp_path: Path) -> None:
    """Project-level + user-level entries fire the hook twice at once; the brief must
    land once. A duplicate is one that arrives while the first claim is still held."""
    from meta_harness.hook_dedupe import claim, release

    project = _project(tmp_path / "p")
    markers = project / ".meta-harness" / "hook_markers"
    payload = {"hook_event_name": "SessionStart", "trigger": "compact", "session_id": "s1"}
    assert claim(markers, "session_start", "s1", window_seconds=60) is True  # first copy
    duplicate = _run(START, project, payload)
    assert (duplicate.returncode, duplicate.stdout) == (0, "")  # second copy yields
    release(markers, "session_start", "s1")
    later = _run(START, project, payload)  # a later, legitimate event is served
    assert "context restored" in later.stdout
