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


@pytest.fixture
def state_env(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """An isolated state home (#222), genuinely OUTSIDE the project.

    The last-green record lives outside the governed tree now, so a test that did
    not pass an env would write into the developer's real ``~/.local/state``.

    It comes from ``tmp_path_factory`` rather than ``tmp_path`` on purpose: these
    tests use ``tmp_path`` itself as the project root, so a state home under it
    would be *inside* the tree — which ``_state_path`` now refuses, and rightly.
    That refusal is what caught this fixture.
    """
    return {"XDG_STATE_HOME": str(tmp_path_factory.mktemp("state-home"))}


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


def test_no_record_means_never_skip(tmp_path: Path, state_env: dict[str, str]) -> None:
    config = _make_project(tmp_path)
    assert read_last_green(tmp_path, state_env) is None
    assert should_skip_gate(tmp_path, config, state_env) is False


def test_skip_when_state_matches_last_green(tmp_path: Path, state_env: dict[str, str]) -> None:
    config = _make_project(tmp_path)
    record_green(tmp_path, config, state_env)
    assert should_skip_gate(tmp_path, config, state_env) is True


def test_no_skip_after_gated_change(tmp_path: Path, state_env: dict[str, str]) -> None:
    config = _make_project(tmp_path)
    record_green(tmp_path, config, state_env)
    (tmp_path / "src" / "app.py").write_text("x = 99\n", encoding="utf-8")
    assert should_skip_gate(tmp_path, config, state_env) is False


def test_non_gated_file_does_not_block_skip(tmp_path: Path, state_env: dict[str, str]) -> None:
    # The user's exact case: a stray .txt (e.g. extracted prompts) is not governed
    # code, so it must not force a full gate run.
    config = _make_project(tmp_path)
    record_green(tmp_path, config, state_env)
    (tmp_path / "notes.txt").write_text("a question, no code change\n", encoding="utf-8")
    assert should_skip_gate(tmp_path, config, state_env) is True


def test_unreadable_state_is_fail_closed(tmp_path: Path, state_env: dict[str, str]) -> None:
    config = _make_project(tmp_path)
    assert read_last_green(tmp_path, state_env) is None
    assert should_skip_gate(tmp_path, config, state_env) is False


def test_nested_source_is_hashed_artifacts_excluded(
    tmp_path: Path, state_env: dict[str, str]
) -> None:
    config = _make_project(tmp_path)
    # A nested package dir (exercises directory traversal) affects the hash...
    (tmp_path / "src" / "pkg").mkdir()
    (tmp_path / "src" / "pkg" / "mod.py").write_text("y = 1\n", encoding="utf-8")
    with_nested = compute_state_hash(tmp_path, config)
    record_green(tmp_path, config, state_env)
    # ...but build artifacts (__pycache__, .pyc) never do.
    (tmp_path / "src" / "__pycache__").mkdir()
    (tmp_path / "src" / "__pycache__" / "app.cpython-312.pyc").write_bytes(b"\x00\x01")
    (tmp_path / "src" / "app.pyc").write_bytes(b"\x00\x02")
    assert compute_state_hash(tmp_path, config) == with_nested
    assert should_skip_gate(tmp_path, config, state_env) is True


def test_compute_error_is_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state_env: dict[str, str]
) -> None:
    config = _make_project(tmp_path)
    record_green(tmp_path, config, state_env)

    def _boom(*_a: object, **_k: object) -> str:
        raise OSError("gated file vanished mid-hash")

    monkeypatch.setattr(change_detect, "compute_state_hash", _boom)
    assert should_skip_gate(tmp_path, config, state_env) is False


# --- #222: the record the skip rests on must live outside the governed tree -----


def test_the_record_is_not_written_inside_the_project(
    tmp_path: Path, state_env: dict[str, str]
) -> None:
    """Route 1's precondition: nothing under the project decides the skip.

    An in-tree record is writable by the agent it bounds, and the hash is
    computable from this repository — so the forgery needs no secret at all.
    """
    config = _make_project(tmp_path)
    record_green(tmp_path, config, state_env)

    assert should_skip_gate(tmp_path, config, state_env) is True
    assert not (tmp_path / ".meta-harness" / "last_green_state").exists()
    written = list(Path(state_env["XDG_STATE_HOME"]).rglob("last_green_state"))
    assert len(written) == 1, written


def test_a_forged_in_tree_record_is_ignored(tmp_path: Path, state_env: dict[str, str]) -> None:
    """Route 1 (#222): plant the correct hash in the old in-tree location.

    First prove the forgery is *correct* — it is the exact value the old code
    compared against — then prove the gate still runs.
    """
    config = _make_project(tmp_path)
    legacy = tmp_path / ".meta-harness" / "last_green_state"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(compute_state_hash(tmp_path, config), encoding="utf-8")

    assert legacy.read_text() == compute_state_hash(tmp_path, config)  # the forgery is live
    assert should_skip_gate(tmp_path, config, state_env) is False  # and buys nothing


def test_a_green_run_removes_a_stale_in_tree_record(
    tmp_path: Path, state_env: dict[str, str]
) -> None:
    """The old location is cleaned, so nobody 'fixes' the skip by reading it again."""
    config = _make_project(tmp_path)
    legacy = tmp_path / ".meta-harness" / "last_green_state"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("stale", encoding="utf-8")

    record_green(tmp_path, config, state_env)

    assert not legacy.exists()


def test_no_state_home_never_skips(tmp_path: Path) -> None:
    """Fail closed rather than fall back into the tree.

    A fallback would restore the forgeable location on exactly the machines least
    able to notice it had happened.
    """
    config = _make_project(tmp_path)
    nowhere: dict[str, str] = {}  # no XDG_STATE_HOME, no HOME

    record_green(tmp_path, config, nowhere)  # must not raise, and must not write in-tree

    assert not (tmp_path / ".meta-harness" / "last_green_state").exists()
    assert read_last_green(tmp_path, nowhere) is None
    assert should_skip_gate(tmp_path, config, nowhere) is False


def test_a_symlinked_project_path_shares_one_record(
    tmp_path: Path, state_env: dict[str, str]
) -> None:
    """The record is keyed by the RESOLVED path, as the retry counter is."""
    project = tmp_path / "real"
    project.mkdir()
    config = _make_project(project)
    link = tmp_path / "link"
    link.symlink_to(project, target_is_directory=True)

    record_green(project, config, state_env)

    assert should_skip_gate(link, config, state_env) is True


def test_a_state_root_inside_the_project_is_refused(tmp_path: Path) -> None:
    """A $HOME resolving into the tree must not silently re-open the hole (#232 review).

    Without this the record lands back where the agent can write it while every
    log line still claims it is outside. Same guard as ``retry_state``'s.
    """
    config = _make_project(tmp_path)
    inside = {"XDG_STATE_HOME": str(tmp_path / "state")}

    record_green(tmp_path, config, inside)

    assert not (tmp_path / "state").exists(), "wrote the record inside the project"
    assert should_skip_gate(tmp_path, config, inside) is False


def test_a_symlinked_meta_harness_cannot_steer_the_legacy_delete(
    tmp_path: Path, state_env: dict[str, str]
) -> None:
    """``.meta-harness`` is agent-writable, so the delete must not follow it (#232 review).

    ``unlink`` refuses to follow a symlink only as the FINAL component. With
    ``.meta-harness`` itself a link, the tidy-up of the pre-#222 record would
    delete a same-named file anywhere on the filesystem.
    """
    project = tmp_path / "proj"
    project.mkdir()
    config = _make_project(project)

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    bystander = elsewhere / "last_green_state"
    bystander.write_text("someone else's file", encoding="utf-8")
    (project / ".meta-harness").symlink_to(elsewhere, target_is_directory=True)

    record_green(project, config, state_env)

    assert bystander.exists(), "followed a planted symlink and deleted an outside file"
    assert bystander.read_text(encoding="utf-8") == "someone else's file"


def test_retiring_a_legacy_record_under_an_unopenable_project_is_not_an_error(
    tmp_path: Path,
) -> None:
    """Tidying an old file must never be able to fail a gate run.

    Exercised through the private helper on purpose: this is the branch where the
    project directory cannot be opened at all, which the public path cannot reach
    (hashing the gated inputs would have failed first). A defensive branch still
    has to be shown to be safe.
    """
    change_detect._retire_legacy(tmp_path / "does-not-exist")  # must not raise
