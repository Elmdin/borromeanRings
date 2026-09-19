"""End-to-end: the provenance gate against a fixture project and a fixture "source".

The defect this locks down came from review: two of five re-authored ports of a
CC-licensed sibling carried copied passages, and the mechanical shingle sweep that caught
them lived only in a scratchpad. These tests run the real ``verify.sh`` with only
``25_provenance`` required and assert every outcome the spec names:

* off (no ``[provenance]``) / noop (no sources; nothing changed under ``paths``);
* pass (no overlap), fail with both locations, allowlisted overlap passes;
* an unreadable source fails closed;
* ``BORROMEANRINGS_PROVENANCE_SOURCES`` turns the rule on with ``sources = []``.

See docs/specs/SPEC-provenance.md and ADR-0070.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
GATE_TIMEOUT_S = 120
CHECK = "25_provenance"

SOURCE_ADR = (
    "# ADR-0004 — Stewardship is a cadence, not a fifth competency\n"
    "\n"
    "Bolting a fifth column onto a framework named for having four is a category error.\n"
    "Licensed under CC BY-NC-SA 4.0.\n"
)
CLEAN_DOC = "# Ours\n\nA fifth column does not belong on a four-part model.\n"
COPIED_DOC = (
    "# Ours\n"
    "\n"
    "We reject bolting a fifth column onto a framework named for having four.\n"
    "\n"
    "The sibling is licensed under CC BY-NC-SA 4.0.\n"
)


def _config(provenance: str | None) -> str:
    base = '[project]\nlanguage = "python"\n\n[checks]\nrequired = ["25_provenance"]\n\n'
    base += "[hygiene]\nrequires = []\n\n"
    return base if provenance is None else base + provenance


def _git(root: Path, *argv: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *argv],
        cwd=root,
        capture_output=True,
        check=True,
    )


def _write(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")


def _feature_repo(root: Path, config: str, changed: dict[str, str]) -> Path:
    """A repo with ``main`` holding the config and a ``feat/x`` branch adding ``changed``."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", "main")
    _write(root, {"borromeanrings.toml": config, "README.md": "base\n"})
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    _git(root, "checkout", "-qb", "feat/x")
    if changed:
        _write(root, changed)
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", "feat: docs")
    return root


def _source_dir(root: Path) -> Path:
    src = root / "sibling"
    _write(src, {"docs/adr/0004.md": SOURCE_ADR})
    return src


def _run_gate(project: Path, extra_env: dict[str, str] | None = None) -> tuple[int, str, str]:
    """Run the real gate; return (exit code, status of 25_provenance, its log text)."""
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(project)
    env.pop("BORROMEANRINGS_PROVENANCE_SOURCES", None)
    env.update(extra_env or {})
    proc = subprocess.run(
        ["bash", str(VERIFY)], env=env, capture_output=True, text=True, timeout=GATE_TIMEOUT_S
    )
    runs = sorted(p for p in (project / ".meta-harness" / "receipts").glob("*") if p.is_dir())
    receipt = json.loads((runs[-1] / f"{CHECK}.json").read_text(encoding="utf-8"))
    return proc.returncode, receipt["status"], (runs[-1] / f"{CHECK}.log").read_text("utf-8")


def test_no_provenance_section_is_rule_off_reported_as_noop(tmp_path: Path) -> None:
    project = _feature_repo(tmp_path / "p", _config(None), {"docs/x.md": COPIED_DOC})
    code, status, log = _run_gate(project)
    assert code == 0 and status == "noop", log
    assert "rule off" in log


def test_declared_but_no_sources_is_noop(tmp_path: Path) -> None:
    project = _feature_repo(
        tmp_path / "p", _config("[provenance]\nsources = []\n"), {"docs/x.md": COPIED_DOC}
    )
    code, status, log = _run_gate(project)
    assert code == 0 and status == "noop", log
    assert "no provenance sources" in log


def test_nothing_changed_under_paths_is_noop(tmp_path: Path) -> None:
    src = _source_dir(tmp_path)
    cfg = _config(f'[provenance]\nsources = ["{src}"]\npaths = ["docs"]\n')
    project = _feature_repo(tmp_path / "p", cfg, {"notes/x.md": COPIED_DOC})
    code, status, log = _run_gate(project)
    assert code == 0 and status == "noop", log
    assert "no changed files" in log


def test_clean_re_authoring_passes(tmp_path: Path) -> None:
    src = _source_dir(tmp_path)
    cfg = _config(f'[provenance]\nsources = ["{src}"]\n')
    project = _feature_repo(tmp_path / "p", cfg, {"docs/x.md": CLEAN_DOC})
    code, status, log = _run_gate(project)
    assert code == 0 and status == "pass", log
    assert "no unlisted" in log


def test_copied_passage_fails_with_both_locations(tmp_path: Path) -> None:
    src = _source_dir(tmp_path)
    cfg = _config(f'[provenance]\nsources = ["{src}"]\n')
    project = _feature_repo(tmp_path / "p", cfg, {"docs/x.md": COPIED_DOC})
    code, status, log = _run_gate(project)
    assert code != 0 and status == "fail", log
    assert f'docs/x.md:3 ↔ {src / "docs/adr/0004.md"}:3 — "a fifth column onto a framework"' in log
    # The generic license phrase is a finding too until a human allowlists it.
    assert '"licensed under cc by nc sa"' in log


def test_allowlisted_overlap_passes_and_is_named(tmp_path: Path) -> None:
    src = _source_dir(tmp_path)
    cfg = _config(
        f'[provenance]\nsources = ["{src}"]\n'
        "allow = [\n"
        '  "CC BY-NC-SA",  # license identifier, not authorial expression\n'
        '  "bolting a fifth column onto a framework named for having four",  # acknowledged\n'
        "]\n"
    )
    project = _feature_repo(tmp_path / "p", cfg, {"docs/x.md": COPIED_DOC})
    code, status, log = _run_gate(project)
    assert code == 0 and status == "pass", log
    assert "allowed" in log and "cc by nc sa" in log


def test_missing_source_fails_closed(tmp_path: Path) -> None:
    cfg = _config(f'[provenance]\nsources = ["{tmp_path / "absent"}"]\n')
    project = _feature_repo(tmp_path / "p", cfg, {"docs/x.md": CLEAN_DOC})
    code, status, log = _run_gate(project)
    assert code != 0 and status == "fail", log
    assert "failing closed" in log and "absent" in log


def test_source_with_only_binaries_fails_closed(tmp_path: Path) -> None:
    src = tmp_path / "bin"
    src.mkdir()
    (src / "blob.bin").write_bytes(b"\x00\x01\x02" * 100)
    cfg = _config(f'[provenance]\nsources = ["{src}"]\n')
    project = _feature_repo(tmp_path / "p", cfg, {"docs/x.md": CLEAN_DOC})
    code, status, log = _run_gate(project)
    assert code != 0 and status == "fail", log
    assert "zero readable text files" in log


def test_env_sources_turn_the_rule_on_without_a_committed_path(tmp_path: Path) -> None:
    src = _source_dir(tmp_path)
    cfg = _config("[provenance]\nsources = []\n")
    project = _feature_repo(tmp_path / "p", cfg, {"docs/x.md": COPIED_DOC})
    code, status, log = _run_gate(
        project, {"BORROMEANRINGS_PROVENANCE_SOURCES": f"{tmp_path / 'nope-empty'}:{src}:"}
    )
    # The first entry does not exist ⇒ fail closed on it (env paths are sources too).
    assert code != 0 and status == "fail", log
    assert "nope-empty" in log
    code, status, log = _run_gate(project, {"BORROMEANRINGS_PROVENANCE_SOURCES": str(src)})
    assert code != 0 and status == "fail", log
    assert "a fifth column onto a framework" in log


def test_broken_git_inside_a_repo_fails_closed(tmp_path: Path) -> None:
    src = _source_dir(tmp_path)
    cfg = _config(f'[provenance]\nsources = ["{src}"]\n')
    project = _feature_repo(tmp_path / "p", cfg, {"docs/x.md": CLEAN_DOC})
    # Corrupt the object store so `git diff` errors rather than reporting "no changes".
    for obj in (project / ".git" / "objects").rglob("*"):
        if obj.is_file():
            obj.chmod(0o644)  # loose objects are read-only
            obj.write_bytes(b"garbage")
    code, status, log = _run_gate(project)
    assert code != 0 and status == "fail", log
    assert "failing closed" in log
