"""End-to-end: ``24_quotes`` verifies marked quotations against saved sources.

Runs the real ``verify.sh`` against fixture projects and asserts the outcomes that must
stay distinct: rule off ⇒ pass saying so; no marked quotation ⇒ **noop**, never a hollow
pass; every quotation verbatim ⇒ pass with counts; a drifted or missing one ⇒ fail naming
file:line; an unreadable source ⇒ fail closed. See docs/specs/SPEC-quotes.md, ADR-0065.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
GATE_TIMEOUT_S = 120

CONFIG = (
    '[project]\nlanguage = "markdown"\nsrc_dir = "src"\n\n'
    '[checks]\nrequired = ["24_quotes"]\n\n[hygiene]\nrequires = []\n\n'
    "[quotes]\nenabled = {enabled}\n"
)
SOURCE = "url: https://example.test\n\nRecall is the unsolved problem,\nsaid the paper.\n"
VERBATIM = (
    "# Notes\n\n> “Recall is the unsolved problem.”\n\n— source: docs/research/r/sources/1.md#L3\n"
)
DRIFTED = "# Notes\n\n> Recall is a solved problem.\n\n— source: docs/research/r/sources/1.md#L3\n"
MISSING = (
    "# Notes\n\n> Recall is the unsolved problem.\n"
    "<!-- quote: docs/research/r/sources/9.md#L3 -->\n"
)


def _run_gate(project: Path) -> tuple[int, str, str, str]:
    """Run the gate against ``project``; return (exit, stdout, check status, check log)."""
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(project)
    proc = subprocess.run(
        ["bash", str(VERIFY)], env=env, capture_output=True, text=True, timeout=GATE_TIMEOUT_S
    )
    receipts = project / ".meta-harness" / "receipts"
    run_dir = sorted(p for p in receipts.glob("*") if p.is_dir())[-1]
    status = json.loads((run_dir / "24_quotes.json").read_text())["status"]
    log = (run_dir / "24_quotes.log").read_text(encoding="utf-8")
    return proc.returncode, proc.stdout, status, log


def _project(root: Path, files: dict[str, str], enabled: bool = True) -> Path:
    files = {"borromeanrings.toml": CONFIG.format(enabled=str(enabled).lower()), **files}
    for rel, content in files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    return root


def test_rule_off_passes_and_says_so(tmp_path: Path) -> None:
    project = _project(tmp_path / "off", {"docs/notes.md": DRIFTED}, enabled=False)
    code, stdout, status, log = _run_gate(project)
    assert code == 0, stdout
    assert status == "pass"
    assert "rule off" in log


def test_no_marked_quotation_is_noop_not_pass(tmp_path: Path) -> None:
    project = _project(tmp_path / "bare", {"docs/notes.md": "# Notes\n\n> a plain scope note\n"})
    code, stdout, status, log = _run_gate(project)
    assert code == 0, stdout
    assert status == "noop"
    assert "no marked quotations in 1 Markdown file(s)" in log
    assert "inspected NOTHING" in stdout


def test_no_markdown_at_all_is_noop(tmp_path: Path) -> None:
    project = _project(tmp_path / "empty", {})
    code, stdout, status, log = _run_gate(project)
    assert code == 0, stdout
    assert status == "noop"
    assert "no Markdown under [quotes].paths ['docs']" in log


def test_verbatim_quotation_passes_with_counts(tmp_path: Path) -> None:
    project = _project(
        tmp_path / "ok", {"docs/notes.md": VERBATIM, "docs/research/r/sources/1.md": SOURCE}
    )
    code, stdout, status, log = _run_gate(project)
    assert code == 0, stdout
    assert status == "pass"
    assert "docs/notes.md:3: VERBATIM docs/research/r/sources/1.md#L3-L3" in log
    assert "quotes: 1 verbatim, 0 drifted, 0 missing, 0 out of range, 0 orphan" in log


def test_drifted_quotation_fails_with_file_line_and_diff(tmp_path: Path) -> None:
    project = _project(
        tmp_path / "drift", {"docs/notes.md": DRIFTED, "docs/research/r/sources/1.md": SOURCE}
    )
    code, stdout, status, log = _run_gate(project)
    assert code != 0, f"a drifted quotation must FAIL:\n{stdout}"
    assert status == "fail"
    assert "docs/notes.md:3: DRIFTED docs/research/r/sources/1.md#L3-L3" in log
    assert "    -Recall is a solved problem." in log
    assert "    +Recall is the unsolved problem," in log
    assert "QUOTE FIDELITY" in log


def test_missing_source_fails(tmp_path: Path) -> None:
    project = _project(
        tmp_path / "missing", {"docs/notes.md": MISSING, "docs/research/r/sources/1.md": SOURCE}
    )
    code, stdout, status, log = _run_gate(project)
    assert code != 0, stdout
    assert status == "fail"
    assert "docs/notes.md:3: MISSING docs/research/r/sources/9.md#L3-L3 (no such file)" in log


def test_unreadable_source_fails_closed(tmp_path: Path) -> None:
    project = _project(tmp_path / "unreadable", {"docs/notes.md": VERBATIM})
    (project / "docs/research/r/sources").mkdir(parents=True)
    (project / "docs/research/r/sources/1.md").write_bytes(b"\xff\xfe not utf-8 \x00")
    code, stdout, status, log = _run_gate(project)
    assert code != 0, stdout
    assert status == "fail"
    assert "UNREADABLE" in log or "codec" in log


SECRET = "SECRET-CONTENT-MUST-NOT-APPEAR-IN-LOG"


def test_symlinked_source_outside_the_project_is_missing_and_never_read(tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere" / "1.md"
    outside.parent.mkdir(parents=True)
    outside.write_text(f"url: x\n\n{SECRET}\nsaid the paper.\n", encoding="utf-8")
    project = _project(tmp_path / "symlink_file", {"docs/notes.md": VERBATIM})
    (project / "docs/research/r/sources").mkdir(parents=True)
    (project / "docs/research/r/sources/1.md").symlink_to(outside)
    code, stdout, status, log = _run_gate(project)
    assert code != 0, stdout
    assert status == "fail"
    assert (
        "docs/notes.md:3: MISSING docs/research/r/sources/1.md#L3-L3 (outside the project)" in log
    )
    assert SECRET not in log


def test_symlinked_directory_outside_the_project_is_skipped_not_read(tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "evil.md").write_text(f"> {SECRET}\n— source: docs/research/r/sources/1.md#L3\n")
    project = _project(
        tmp_path / "symlink_dir",
        {"docs/notes.md": VERBATIM, "docs/research/r/sources/1.md": SOURCE},
    )
    (project / "docs" / "linked").symlink_to(outside, target_is_directory=True)
    code, stdout, status, log = _run_gate(project)
    assert code == 0, stdout
    assert status == "pass"
    assert "skipped docs/linked: symlinked directory, outside the project (not followed)" in log
    assert SECRET not in log
    assert "quotes: 1 verbatim, 0 drifted, 0 missing, 0 out of range, 0 orphan" in log


def test_symlinked_file_inside_the_project_is_read_normally(tmp_path: Path) -> None:
    project = _project(
        tmp_path / "symlink_inside",
        {"docs/notes.md": VERBATIM, "docs/research/r/saved.md": SOURCE},
    )
    (project / "docs/research/r/sources").mkdir()
    (project / "docs/research/r/sources/1.md").symlink_to(project / "docs/research/r/saved.md")
    code, stdout, status, log = _run_gate(project)
    assert code == 0, stdout
    assert status == "pass"
    assert "docs/notes.md:3: VERBATIM docs/research/r/sources/1.md#L3-L3" in log
