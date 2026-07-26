"""Tests for the project-hygiene gate (written first, per ADR-0012 TDD)."""

from pathlib import Path

from meta_harness.hygiene import missing_paths


def test_missing_paths_reports_absent_required_artifacts(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    missing = missing_paths(tmp_path, ["README.md", "docs", "LICENSE", ".github/workflows"])
    assert missing == ["LICENSE", ".github/workflows"]


def test_missing_paths_empty_when_all_present(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    assert missing_paths(tmp_path, ["README.md"]) == []
