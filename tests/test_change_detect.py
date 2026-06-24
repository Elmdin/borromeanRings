"""Tests for the no-op Stop guard (gate-skip change detection).

The Stop hook must skip the gate ONLY when the governed input state is identical
to the state that last passed — i.e. proof for this exact state already exists.
Any change, missing record, or unreadable state ⇒ do NOT skip (fail-closed).
"""

from pathlib import Path

import pytest

from meta_harness import change_detect
from meta_harness.change_detect import (
    compute_state_hash,
    read_last_green,
    record_green,
    should_skip_gate,
)
from meta_harness.spine import Config, load_config


def _make_project(tmp_path: Path) -> Config:
    (tmp_path / "borromeanrings.toml").write_text(
        '[checks]\nrequired = ["00_build"]\n[project]\nsrc_dir = "src"\ntests_dir = "tests"\n',
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text(
        "def test_x():\n    assert True\n", encoding="utf-8"
    )
    return load_config(tmp_path / "borromeanrings.toml")


def test_hash_is_deterministic(tmp_path: Path) -> None:
    config = _make_project(tmp_path)
    assert compute_state_hash(tmp_path, config) == compute_state_hash(tmp_path, config)


def test_hash_changes_when_gated_source_changes(tmp_path: Path) -> None:
    config = _make_project(tmp_path)
    before = compute_state_hash(tmp_path, config)
    (tmp_path / "src" / "app.py").write_text("x = 2\n", encoding="utf-8")
    assert compute_state_hash(tmp_path, config) != before


def test_no_record_means_never_skip(tmp_path: Path) -> None:
    config = _make_project(tmp_path)
    assert read_last_green(tmp_path) is None
    assert should_skip_gate(tmp_path, config) is False


def test_skip_when_state_matches_last_green(tmp_path: Path) -> None:
    config = _make_project(tmp_path)
    record_green(tmp_path, config)
    assert should_skip_gate(tmp_path, config) is True


def test_no_skip_after_gated_change(tmp_path: Path) -> None:
    config = _make_project(tmp_path)
    record_green(tmp_path, config)
    (tmp_path / "src" / "app.py").write_text("x = 99\n", encoding="utf-8")
    assert should_skip_gate(tmp_path, config) is False


def test_non_gated_file_does_not_block_skip(tmp_path: Path) -> None:
    # The user's exact case: a stray .txt (e.g. extracted prompts) is not governed
    # code, so it must not force a full gate run.
    config = _make_project(tmp_path)
    record_green(tmp_path, config)
    (tmp_path / "notes.txt").write_text("a question, no code change\n", encoding="utf-8")
    assert should_skip_gate(tmp_path, config) is True


def test_unreadable_state_is_fail_closed(tmp_path: Path) -> None:
    config = _make_project(tmp_path)
    assert read_last_green(tmp_path) is None
    assert should_skip_gate(tmp_path, config) is False


def test_nested_source_is_hashed_artifacts_excluded(tmp_path: Path) -> None:
    config = _make_project(tmp_path)
    # A nested package dir (exercises directory traversal) affects the hash...
    (tmp_path / "src" / "pkg").mkdir()
    (tmp_path / "src" / "pkg" / "mod.py").write_text("y = 1\n", encoding="utf-8")
    with_nested = compute_state_hash(tmp_path, config)
    record_green(tmp_path, config)
    # ...but build artifacts (__pycache__, .pyc) never do.
    (tmp_path / "src" / "__pycache__").mkdir()
    (tmp_path / "src" / "__pycache__" / "app.cpython-312.pyc").write_bytes(b"\x00\x01")
    (tmp_path / "src" / "app.pyc").write_bytes(b"\x00\x02")
    assert compute_state_hash(tmp_path, config) == with_nested
    assert should_skip_gate(tmp_path, config) is True


def test_compute_error_is_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _make_project(tmp_path)
    record_green(tmp_path, config)

    def _boom(*_a: object, **_k: object) -> str:
        raise OSError("gated file vanished mid-hash")

    monkeypatch.setattr(change_detect, "compute_state_hash", _boom)
    assert should_skip_gate(tmp_path, config) is False
