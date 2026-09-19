"""The Stop hook records the self-report verdict, driven over its stdin protocol (#176).

``stop_gate.sh`` hands the payload's ``transcript_path`` to ``meta_harness.self_report`` in
the same bounded step as the rewrite contract and appends the verdict to
``.meta-harness/self_report.jsonl``. These tests run the real script with the JSON Claude
Code sends and assert the record line — and that recording never blocks the Stop. The
fixture project is pre-marked green so the gate itself is skipped (no-op guard).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from meta_harness.change_detect import record_green
from meta_harness.spine import load_config
from meta_harness.verdict import REWRITE_CONTRACT_FILE, SELF_REPORT_FILE

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
STOP = BORROMEANRINGS_HOME / ".claude" / "hooks" / "stop_gate.sh"

BLOCK = (
    "VERIFICATION STATUS\n"
    "Verified: the test ran\n"
    "Unverified: none\n"
    "Weakest claim: the bound — untested under load\n"
    "Assumed: nothing\n"
)


def _project(root: Path, *, rewriting: bool = True, self_report: bool | None = None) -> Path:
    root.mkdir()
    extra = (
        "" if self_report is None else f"\n[self_report]\nenabled = {str(self_report).lower()}\n"
    )
    (root / "borromeanrings.toml").write_text(
        '[project]\nlanguage = "none"\npackage = "x"\n\n'
        '[checks]\nrequired = ["05_hygiene"]\n\n[hygiene]\nrequires = []\n\n'
        f"[prompt_rewriting]\nenabled = {'true' if rewriting else 'false'}\n{extra}",
        encoding="utf-8",
    )
    record_green(root, load_config(root / "borromeanrings.toml"))
    return root


def _transcript(path: Path, prompt: str, *replies: str) -> Path:
    path.parent.mkdir(exist_ok=True)
    entries: list[dict[str, object]] = [
        {"type": "user", "origin": {"kind": "human"}, "message": {"content": prompt}}
    ]
    entries += [
        {"type": "assistant", "message": {"content": [{"type": "text", "text": reply}]}}
        for reply in replies
    ]
    path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    return path


def _stop(project: Path, payload: object) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(project)
    env["CLAUDE_CONFIG_DIR"] = str(project.parent)
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        ["bash", str(STOP)], input=stdin, env=env, capture_output=True, text=True, timeout=120
    )


def _records(project: Path) -> list[dict[str, object]]:
    raw = (project / SELF_REPORT_FILE).read_text(encoding="utf-8")
    return [json.loads(line) for line in raw.splitlines()]


def test_stop_records_a_present_block_from_the_final_reply(tmp_path: Path) -> None:
    project = _project(tmp_path / "p")
    transcript = _transcript(
        tmp_path / "projects" / "s.jsonl",
        "add retries",
        "Reading this as: add bounded retries.",
        "Done.\n\n" + BLOCK,
    )
    proc = _stop(project, {"session_id": "s1", "transcript_path": str(transcript)})
    assert proc.returncode == 0, proc.stderr
    (row,) = _records(project)
    assert row == {
        "ts": row["ts"],
        "session_id": "s1",
        "prompt_hash": row["prompt_hash"],
        "status": "present",
        "present_fields": ["Verified", "Unverified", "Weakest claim", "Assumed"],
        "violation": "",
        "line": 3,
    }
    assert len(str(row["prompt_hash"])) == 16 and str(row["ts"]).endswith("Z")
    # both receipts came out of the one step, joined by the same prompt digest
    (rewrite,) = [
        json.loads(line)
        for line in (project / REWRITE_CONTRACT_FILE).read_text(encoding="utf-8").splitlines()
    ]
    assert rewrite["prompt_hash"] == row["prompt_hash"] and rewrite["status"] == "honoured"


def test_stop_records_a_graded_block_without_blocking(tmp_path: Path) -> None:
    project = _project(tmp_path / "p")
    graded = BLOCK.replace(
        "Weakest claim: the bound — untested under load", "Weakest claim: medium"
    )
    transcript = _transcript(tmp_path / "projects" / "s.jsonl", "add retries", graded)
    proc = _stop(project, {"session_id": "s1", "transcript_path": str(transcript)})
    assert proc.returncode == 0, proc.stderr
    (row,) = _records(project)
    assert (row["status"], row["violation"], row["line"]) == ("graded", "Weakest claim: medium", 2)


def test_stop_records_an_absent_block(tmp_path: Path) -> None:
    project = _project(tmp_path / "p")
    transcript = _transcript(tmp_path / "projects" / "s.jsonl", "add retries", "Sure, done.")
    proc = _stop(project, {"session_id": "s1", "transcript_path": str(transcript)})
    assert proc.returncode == 0, proc.stderr
    (row,) = _records(project)
    assert (row["status"], row["present_fields"], row["violation"]) == ("absent", [], "")


def test_self_report_follows_prompt_rewriting_unless_overridden(tmp_path: Path) -> None:
    transcript = _transcript(tmp_path / "projects" / "s.jsonl", "add retries", "Sure.")
    payload = {"session_id": "s1", "transcript_path": str(transcript)}

    off = _project(tmp_path / "off", rewriting=False)
    assert _stop(off, payload).returncode == 0
    assert not (off / SELF_REPORT_FILE).exists()

    diverged = _project(tmp_path / "on", rewriting=False, self_report=True)
    assert _stop(diverged, payload).returncode == 0
    assert not (diverged / REWRITE_CONTRACT_FILE).exists()
    assert _records(diverged)[0]["status"] == "absent"

    opted_out = _project(tmp_path / "out", rewriting=True, self_report=False)
    assert _stop(opted_out, payload).returncode == 0
    assert (opted_out / REWRITE_CONTRACT_FILE).exists()
    assert not (opted_out / SELF_REPORT_FILE).exists()
