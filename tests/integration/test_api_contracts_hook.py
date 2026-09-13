"""The PostToolUse preventive layer for API contracts, driven over its stdin protocol."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

HOOK = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "post_edit_format.sh"


def _run(project: Path, edited: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(project)
    payload = {"tool_name": "Edit", "tool_input": {"file_path": str(edited)}}
    return subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps(payload),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_hook_reports_violations_in_the_edited_file_and_never_blocks(tmp_path: Path) -> None:
    (tmp_path / "borromeanrings.toml").write_text(
        '[checks]\nrequired = ["00_build"]\n'
        '[[api_contracts.rules]]\nkind = "banned"\nsymbol = "malloc"\nmessage = "no heap"\n',
        encoding="utf-8",
    )
    edited = tmp_path / "fw.py"
    edited.write_text("buf = malloc(4)\n", encoding="utf-8")
    proc = _run(tmp_path, edited)
    assert proc.returncode == 0
    assert "API-contract violations" in proc.stdout
    assert "line 1 [banned] malloc — no heap" in proc.stdout


def test_hook_is_silent_when_compliant_or_undeclared(tmp_path: Path) -> None:
    (tmp_path / "borromeanrings.toml").write_text(
        '[checks]\nrequired = ["00_build"]\n', encoding="utf-8"
    )
    edited = tmp_path / "fw.py"
    edited.write_text("buf = malloc(4)\n", encoding="utf-8")
    proc = _run(tmp_path, edited)
    assert (proc.returncode, proc.stdout) == (0, "")
