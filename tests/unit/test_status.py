"""Unit tests for the portfolio status / roster view (meta_harness.status)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from meta_harness.status import (
    ProjectStatus,
    build_status,
    discover_projects,
    gather,
    main,
    render,
    summarize,
)
from meta_harness.verdict import Verdict, write_last_verdict

# A minimal governed config: [project] + a non-empty [checks].required (load_config
# fails closed on an empty required set). Missing the recommended set ⇒ drift.
_MINIMAL_TOML = """\
[project]
language = "python"
src_dir = "src"
tests_dir = "tests"

[checks]
required = ["00_build", "40_test"]
"""


def _write_project(root: Path, toml: str = _MINIMAL_TOML) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "borromeanrings.toml").write_text(toml, encoding="utf-8")
    return root


def _git_init(root: Path) -> None:
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "t@t.t"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "t"], check=True)


# --- build_status (pure) ---------------------------------------------------


def test_build_status_never_gated_when_no_verdict() -> None:
    s = build_status(
        "/p",
        is_git=True,
        config_dirty=False,
        required=("00_build",),
        has_changelog=True,
        last_verdict=None,
    )
    assert s.verdict == "never"


def test_build_status_maps_verdict_ok_and_fail() -> None:
    ok = build_status(
        "/p",
        is_git=True,
        config_dirty=False,
        required=("00_build",),
        has_changelog=True,
        last_verdict=Verdict(ok=True),
    )
    bad = build_status(
        "/p",
        is_git=True,
        config_dirty=False,
        required=("00_build",),
        has_changelog=True,
        last_verdict=Verdict(ok=False),
    )
    assert ok.verdict == "pass"
    assert bad.verdict == "fail"


def test_build_status_notes_non_git() -> None:
    s = build_status(
        "/p",
        is_git=False,
        config_dirty=False,
        required=("00_build",),
        has_changelog=True,
        last_verdict=None,
    )
    assert "not a git repo" in s.note


def test_build_status_notes_uncommitted_config() -> None:
    s = build_status(
        "/p",
        is_git=True,
        config_dirty=True,
        required=("00_build",),
        has_changelog=True,
        last_verdict=None,
    )
    assert "config uncommitted" in s.note


def test_build_status_reports_adoption_drift() -> None:
    # required lacks the recommended set ⇒ drift with a positive count.
    s = build_status(
        "/p",
        is_git=True,
        config_dirty=False,
        required=("00_build", "40_test"),
        has_changelog=True,
        last_verdict=Verdict(ok=True),
    )
    # all 5 recommended checks are missing here ⇒ the note reports the exact count.
    assert len(s.missing_recommended) == 5
    assert "drift: +5" in s.note


def test_build_status_names_failing_checks() -> None:
    # A red row names which checks failed, so it is diagnosable without a manual cd.
    v = Verdict(ok=False, checks=(("12_secrets", "fail"), ("40_test", "pass")))
    s = build_status(
        "/p",
        is_git=True,
        config_dirty=False,
        required=("00_build",),
        has_changelog=True,
        last_verdict=v,
    )
    assert "failed: 12_secrets" in s.note
    assert "40_test" not in s.note


def test_build_status_fully_adopted_has_no_note() -> None:
    required = (
        "00_build",
        "12_secrets",
        "11_changelog",
        "32_complexity",
        "33_coupling",
        "45_docstrings",
    )
    s = build_status(
        "/p",
        is_git=True,
        config_dirty=False,
        required=required,
        has_changelog=True,
        last_verdict=Verdict(ok=True),
    )
    assert s.missing_recommended == ()
    assert s.note == ""


# --- discover_projects (fs) ------------------------------------------------


def test_discover_finds_governed_and_skips_vendor(tmp_path: Path) -> None:
    _write_project(tmp_path / "a")
    _write_project(tmp_path / "b" / "nested")
    _write_project(tmp_path / "node_modules" / "pkg")  # must be skipped
    found = discover_projects([tmp_path])
    names = {p.name for p in found}
    assert "a" in names
    assert "nested" in names
    assert "pkg" not in names


def test_discover_ignores_missing_root(tmp_path: Path) -> None:
    assert discover_projects([tmp_path / "does-not-exist"]) == []


def test_discover_continues_past_a_missing_root(tmp_path: Path) -> None:
    # a missing root is skipped (continue), it must not abort the whole scan (break).
    _write_project(tmp_path / "real")
    found = discover_projects([tmp_path / "missing", tmp_path])
    assert any(p.name == "real" for p in found)


def test_discover_respects_max_depth(tmp_path: Path) -> None:
    # a project nested below max_depth is pruned (the walk stops descending).
    _write_project(tmp_path / "deep" / "deeper")
    found = discover_projects([tmp_path], max_depth=1)
    assert all(p.name != "deeper" for p in found)


def test_discover_dedups_symlinked_aliases(tmp_path: Path) -> None:
    # a governed project reached via two roots (real path + a symlink) yields one row.
    real = _write_project(tmp_path / "real")
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    assert len(discover_projects([real, link])) == 1


# --- gather (impure: config + git + verdict) -------------------------------


def test_gather_non_git_project(tmp_path: Path) -> None:
    proj = _write_project(tmp_path / "proj")
    s = gather(proj)
    assert s.is_git is False
    assert s.verdict == "never"
    assert "not a git repo" in s.note


def test_gather_git_project_clean_then_dirty(tmp_path: Path) -> None:
    proj = _write_project(tmp_path / "proj")
    _git_init(proj)
    subprocess.run(["git", "-C", str(proj), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(proj), "commit", "-q", "-m", "init"], check=True)
    clean = gather(proj)
    assert clean.is_git is True
    assert clean.config_dirty is False
    # now dirty the config
    (proj / "borromeanrings.toml").write_text(_MINIMAL_TOML + "\n# edit\n", encoding="utf-8")
    dirty = gather(proj)
    assert dirty.config_dirty is True


def test_git_helpers_fail_soft_when_git_absent(tmp_path: Path, monkeypatch) -> None:
    # If git is missing from PATH, subprocess raises OSError — the helpers and gather
    # must degrade, not crash (the "never crashes / always exits 0" contract).
    from meta_harness import status as status_mod

    def _boom(*_a: object, **_k: object) -> None:
        raise FileNotFoundError("git")

    monkeypatch.setattr(status_mod.subprocess, "run", _boom)
    assert status_mod._is_git_repo(tmp_path) is False
    assert status_mod._config_dirty(tmp_path) is False
    proj = _write_project(tmp_path / "p")
    s = gather(proj)
    assert s.verdict == "never"
    assert s.is_git is False


def test_gather_reads_persisted_verdict(tmp_path: Path) -> None:
    proj = _write_project(tmp_path / "proj")
    write_last_verdict(proj, Verdict(ok=True, checks=(("00_build", "pass"),)))
    assert gather(proj).verdict == "pass"


def test_gather_bad_config_degrades_to_note(tmp_path: Path) -> None:
    proj = tmp_path / "broken"
    proj.mkdir()
    (proj / "borromeanrings.toml").write_text("not = valid = toml", encoding="utf-8")
    s = gather(proj)
    assert s.verdict == "never"
    assert "config" in s.note.lower()


# --- render / summarize / main ---------------------------------------------


def test_render_empty_is_exact() -> None:
    assert render([]) == "no governed projects found."


def test_render_row_shows_every_field() -> None:
    out = render([ProjectStatus("/x/proj", True, False, 2, "pass", (), "a note")])
    lines = out.splitlines()
    # header names all columns; the row carries git/req/verdict/note verbatim.
    assert lines[0].split() == ["PROJECT", "GIT", "REQ", "VERDICT", "NOTES"]
    row = lines[2]
    assert "/x/proj" in row
    assert "yes" in row
    assert "2" in row
    assert "pass" in row
    assert "a note" in row
    # a non-git row renders "NO", not "yes".
    no = render([ProjectStatus("/y", False, False, 1, "fail", (), "")]).splitlines()[2]
    assert "NO" in no


def test_render_shortens_home_paths() -> None:
    home = str(Path.home())
    out = render([ProjectStatus(f"{home}/sub/proj", True, False, 1, "pass", (), "")])
    assert "~/sub/proj" in out


def test_summarize_counts_every_field() -> None:
    rows = [
        ProjectStatus("/a", True, False, 5, "pass", (), ""),
        ProjectStatus("/b", True, False, 5, "fail", (), ""),
        ProjectStatus("/c", False, False, 5, "never", ("12_secrets",), "not a git repo"),
        ProjectStatus("/d", True, False, 5, "pass", ("33_coupling",), "drift: +1"),
    ]
    line = summarize(rows)
    # every count is asserted so a mutation of any one of them is caught.
    assert "4 governed" in line
    assert "2 green" in line
    assert "1 failing" in line
    assert "1 never-gated" in line
    assert "2 drifted" in line
    assert "1 non-git" in line


def test_main_list_mode_prints_paths(tmp_path: Path, capsys) -> None:
    _write_project(tmp_path / "proj")
    rc = main(["--list", str(tmp_path)])
    assert rc == 0
    assert "proj" in capsys.readouterr().out


def test_main_render_mode(tmp_path: Path, capsys) -> None:
    _write_project(tmp_path / "proj")
    rc = main([str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "proj" in out
    assert "governed" in out


# --- legacy config name (issue #62) -----------------------------------------


def _write_legacy_project(root: Path, toml: str = _MINIMAL_TOML) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "borromeo.toml").write_text(toml, encoding="utf-8")
    return root


def test_discover_finds_legacy_named_project(tmp_path: Path) -> None:
    _write_legacy_project(tmp_path / "old")
    _write_project(tmp_path / "new")
    assert discover_projects([tmp_path]) == [
        (tmp_path / "new").resolve(),
        (tmp_path / "old").resolve(),
    ]


def test_gather_legacy_project_loads_config_and_tracks_dirty(tmp_path: Path) -> None:
    proj = _write_legacy_project(tmp_path / "old")
    _git_init(proj)
    subprocess.run(["git", "-C", str(proj), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(proj), "commit", "-q", "-m", "init"], check=True)
    with pytest.warns(DeprecationWarning):
        clean = gather(proj)
    assert clean.required_count == 2
    assert clean.config_dirty is False
    (proj / "borromeo.toml").write_text(_MINIMAL_TOML + "\n# edit\n", encoding="utf-8")
    with pytest.warns(DeprecationWarning):
        dirty = gather(proj)
    assert dirty.config_dirty is True
