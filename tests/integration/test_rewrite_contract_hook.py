"""The Stop hook records the rewrite-contract verdict, driven over its stdin protocol (#81).

``stop_gate.sh`` is a thin adapter: it hands the payload's ``transcript_path`` to
``meta_harness.rewrite_contract`` and appends the verdict to
``.meta-harness/rewrite_contract.jsonl``. These tests run the real script with the JSON
Claude Code sends and assert the record line — and that recording never blocks the Stop.
The fixture project is pre-marked green so the gate itself is skipped (no-op guard) and
the test exercises only the recording seam.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from meta_harness.change_detect import record_green
from meta_harness.spine import load_config
from meta_harness.verdict import REWRITE_CONTRACT_FILE

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
STOP = BORROMEANRINGS_HOME / ".claude" / "hooks" / "stop_gate.sh"


def _project(root: Path, *, rewriting: bool = True) -> Path:
    root.mkdir()
    (root / "borromeanrings.toml").write_text(
        '[project]\nlanguage = "none"\npackage = "x"\n\n'
        '[checks]\nrequired = ["05_hygiene"]\n\n[hygiene]\nrequires = []\n\n'
        f"[prompt_rewriting]\nenabled = {'true' if rewriting else 'false'}\n",
        encoding="utf-8",
    )
    record_green(root, load_config(root / "borromeanrings.toml"))
    return root


def _transcript(path: Path, prompt: str, reply: str) -> Path:
    entries = [
        {"type": "user", "origin": {"kind": "human"}, "message": {"content": prompt}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": reply}]}},
    ]
    path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    return path


def _stop(project: Path, payload: object) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(project)
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        ["bash", str(STOP)], input=stdin, env=env, capture_output=True, text=True, timeout=120
    )


def _records(project: Path) -> list[dict[str, object]]:
    raw = (project / REWRITE_CONTRACT_FILE).read_text(encoding="utf-8")
    return [json.loads(line) for line in raw.splitlines()]


def test_stop_records_an_honoured_verdict_with_evidence(tmp_path: Path) -> None:
    project = _project(tmp_path / "p")
    transcript = _transcript(
        tmp_path / "s.jsonl", "add retries", "Reading this as: add bounded retries.\nDone."
    )
    proc = _stop(project, {"session_id": "s1", "transcript_path": str(transcript)})
    assert proc.returncode == 0, proc.stderr
    (row,) = _records(project)
    assert row["session_id"] == "s1"
    assert row["honoured"] is True
    assert row["status"] == "honoured"
    assert row["line"] == 2
    assert row["matched"] == "Reading this as: add bounded retries."
    assert len(row["prompt_hash"]) == 16 and row["ts"].endswith("Z")


def test_stop_records_a_broken_contract_without_blocking(tmp_path: Path) -> None:
    project = _project(tmp_path / "p")
    transcript = _transcript(tmp_path / "s.jsonl", "add retries", "Sure, adding them.")
    proc = _stop(project, {"session_id": "s1", "transcript_path": str(transcript)})
    assert proc.returncode == 0, proc.stderr
    (row,) = _records(project)
    assert (row["honoured"], row["status"], row["reason"]) == (
        False,
        "not_honoured",
        "reply opened with something else",
    )


def test_stop_records_unknown_on_a_missing_transcript_and_still_exits_zero(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path / "p")
    proc = _stop(project, {"session_id": "s1", "transcript_path": str(tmp_path / "gone.jsonl")})
    assert proc.returncode == 0, proc.stderr
    (row,) = _records(project)
    assert row["honoured"] is None and row["status"] == "unknown"
    assert str(row["reason"]).startswith("transcript unreadable: ")


def test_stop_records_nothing_when_rewriting_is_disabled(tmp_path: Path) -> None:
    project = _project(tmp_path / "p", rewriting=False)
    transcript = _transcript(tmp_path / "s.jsonl", "add retries", "Sure.")
    proc = _stop(project, {"session_id": "s1", "transcript_path": str(transcript)})
    assert proc.returncode == 0, proc.stderr
    assert not (project / REWRITE_CONTRACT_FILE).exists()


def test_stop_does_not_record_on_a_re_stop_or_garbage_payload(tmp_path: Path) -> None:
    project = _project(tmp_path / "p")
    transcript = _transcript(tmp_path / "s.jsonl", "q", "Reading this as: q")
    re_stop = {"session_id": "s1", "transcript_path": str(transcript), "stop_hook_active": True}
    assert _stop(project, re_stop).returncode == 0
    assert not (project / REWRITE_CONTRACT_FILE).exists()  # same prompt, already judged
    proc = _stop(project, "{not json")
    assert proc.returncode == 0, proc.stderr
    (row,) = _records(project)
    assert (row["status"], row["reason"]) == ("unknown", "hook payload unreadable")
