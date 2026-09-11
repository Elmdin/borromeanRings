"""Unit tests for meta_harness.retry_state: where the Stop hook keeps its count.

Every test that touches the filesystem builds its state root under ``tmp_path``
and passes it through an explicit ``env`` mapping, so nothing here can reach
the real home directory.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from meta_harness import retry_state
from meta_harness.retry_state import (
    StateUnavailable,
    clear,
    counter_path,
    decide,
    legacy_counter_path,
    main,
    parse_count,
    project_digest,
    record_failure,
    session_filename,
    state_root,
)

# --- state_root --------------------------------------------------------------


def test_state_root_prefers_an_absolute_xdg_state_home() -> None:
    env = {"XDG_STATE_HOME": "/x/state", "HOME": "/home/u"}
    assert state_root(env) == Path("/x/state")


def test_state_root_ignores_a_relative_xdg_state_home() -> None:
    # XDG Base Directory spec: relative paths are invalid and must be ignored.
    env = {"XDG_STATE_HOME": "rel/state", "HOME": "/home/u"}
    assert state_root(env) == Path("/home/u/.local/state")


def test_state_root_falls_back_to_home_when_xdg_is_empty() -> None:
    assert state_root({"XDG_STATE_HOME": "", "HOME": "/home/u"}) == Path("/home/u/.local/state")


def test_state_root_falls_back_to_home_when_xdg_is_unset() -> None:
    assert state_root({"HOME": "/home/u"}) == Path("/home/u/.local/state")


@pytest.mark.parametrize("env", [{}, {"HOME": ""}, {"HOME": "relative/home"}])
def test_state_root_without_a_usable_home_is_unavailable(env: dict[str, str]) -> None:
    with pytest.raises(StateUnavailable, match="^no absolute XDG_STATE_HOME or HOME to keep"):
        state_root(env)


# --- project_digest / session_filename -----------------------------------------


def test_project_digest_is_a_truncated_sha256_of_the_path() -> None:
    expected = hashlib.sha256(b"/work/project").hexdigest()[:32]
    assert project_digest("/work/project") == expected
    assert len(expected) == 32


def test_project_digest_separates_projects() -> None:
    assert project_digest("/work/a") != project_digest("/work/b")


def test_project_digest_accepts_undecodable_path_bytes() -> None:
    raw = os.fsdecode(b"/work/\xff")
    assert project_digest(raw) == hashlib.sha256(b"/work/\xff").hexdigest()[:32]


@pytest.mark.parametrize("sid", ["abc", "A-b_9", "d0f1e2c3-4b5a-6978-8a9b-0c1d2e3f4a5b", "x" * 128])
def test_safe_session_ids_are_used_verbatim(sid: str) -> None:
    assert session_filename(sid) == sid


@pytest.mark.parametrize("sid", ["", "..", "a.b", "../escape", "a/b", "sp ace", "x" * 129])
def test_unsafe_session_ids_are_hashed(sid: str) -> None:
    expected = "h." + hashlib.sha256(sid.encode("utf-8", "surrogateescape")).hexdigest()[:32]
    assert session_filename(sid) == expected


def test_a_hashed_name_cannot_collide_with_a_verbatim_one() -> None:
    # "." is outside the verbatim alphabet, so no raw id can spell a hashed name.
    assert "." in session_filename("../x")
    assert session_filename("h") == "h"


def test_counter_path_layout() -> None:
    env = {"XDG_STATE_HOME": "/s"}
    got = counter_path(env, "/work/p", "sid")
    assert got == Path("/s/borromeanrings") / project_digest("/work/p") / "stop_attempts" / "sid"


def test_legacy_counter_path_is_the_pre_adr_0079_in_tree_location(tmp_path: Path) -> None:
    got = legacy_counter_path(tmp_path, "sid")
    assert got == tmp_path / ".meta-harness" / "stop_attempts" / "sid"


def test_legacy_counter_path_refuses_unsafe_ids(tmp_path: Path) -> None:
    assert legacy_counter_path(tmp_path, "../../etc/passwd") is None


# --- parse_count / decide ------------------------------------------------------


@pytest.mark.parametrize(("text", "value"), [("0", 0), ("2", 2), (" 3\n", 3), ("17", 17)])
def test_parse_count_accepts_non_negative_decimals(text: str, value: int) -> None:
    assert parse_count(text) == value


@pytest.mark.parametrize("text", ["", "   ", "-1", "abc", "1.5", "2 3", "٣", "+2"])
def test_parse_count_rejects_everything_else(text: str) -> None:
    assert parse_count(text) is None


@pytest.mark.parametrize(
    ("attempts", "verdict"), [(1, "retry"), (2, "retry"), (3, "escalate"), (4, "escalate")]
)
def test_decide_escalates_at_the_cap(attempts: int, verdict: str) -> None:
    assert decide(attempts, 3) == verdict


# --- record_failure ------------------------------------------------------------


def _env(tmp_path: Path) -> dict[str, str]:
    return {"XDG_STATE_HOME": str(tmp_path / "state"), "HOME": str(tmp_path / "home")}


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    return project


def _counter(tmp_path: Path, project: Path, sid: str = "s") -> Path:
    return counter_path(_env(tmp_path), os.path.realpath(project), sid)


def test_first_failure_creates_private_state_and_counts_one(tmp_path: Path) -> None:
    project = _project(tmp_path)
    assert not (tmp_path / "state").exists()

    assert record_failure(str(project), "s", 3, _env(tmp_path)) == "retry 1"

    counter = _counter(tmp_path, project)
    assert counter.read_text() == "1"
    for directory in (counter.parent, counter.parent.parent, counter.parent.parent.parent):
        assert directory.stat().st_mode & 0o777 == 0o700, directory
    assert not list(counter.parent.glob("*.tmp"))


def test_failures_accumulate_then_escalate_and_reset(tmp_path: Path) -> None:
    project = _project(tmp_path)
    env = _env(tmp_path)
    assert record_failure(str(project), "s", 3, env) == "retry 1"
    assert record_failure(str(project), "s", 3, env) == "retry 2"
    assert record_failure(str(project), "s", 3, env) == "escalate 3"
    assert not _counter(tmp_path, project).exists()
    assert record_failure(str(project), "s", 3, env) == "retry 1"


def test_the_resolved_path_keys_the_count(tmp_path: Path) -> None:
    env = _env(tmp_path)
    canonical = lambda _p: "/canonical/project"  # noqa: E731 — injected resolver
    assert record_failure("/via/link", "s", 3, env, resolve=canonical) == "retry 1"
    assert record_failure("/via/other", "s", 3, env, resolve=canonical) == "retry 2"


def test_sessions_count_independently(tmp_path: Path) -> None:
    project = _project(tmp_path)
    env = _env(tmp_path)
    assert record_failure(str(project), "a", 3, env) == "retry 1"
    assert record_failure(str(project), "b", 3, env) == "retry 1"


def test_an_unsafe_session_id_stays_inside_the_state_dir(tmp_path: Path) -> None:
    project = _project(tmp_path)
    assert record_failure(str(project), "../../x", 3, _env(tmp_path)) == "retry 1"
    assert _counter(tmp_path, project, "../../x").name.startswith("h.")
    assert not (tmp_path / "x").exists()


def test_a_corrupt_counter_fails_closed_and_is_left_alone(tmp_path: Path) -> None:
    project = _project(tmp_path)
    env = _env(tmp_path)
    record_failure(str(project), "s", 3, env)
    counter = _counter(tmp_path, project)
    counter.write_text("garbage")

    line = record_failure(str(project), "s", 3, env)
    assert line.startswith("unrecorded ") and "corrupt" in line
    assert counter.read_text() == "garbage"


def test_an_unreadable_counter_fails_closed(tmp_path: Path) -> None:
    project = _project(tmp_path)
    counter = _counter(tmp_path, project)
    counter.mkdir(parents=True)  # a directory where the counter file should be
    line = record_failure(str(project), "s", 3, _env(tmp_path))
    assert line == f"unrecorded cannot read {counter}: Is a directory"


def test_a_state_root_that_is_a_file_fails_closed(tmp_path: Path) -> None:
    project = _project(tmp_path)
    blocker = tmp_path / "blocker"
    blocker.write_text("")
    line = record_failure(str(project), "s", 3, {"XDG_STATE_HOME": str(blocker)})
    assert line.startswith("unrecorded ")


def test_a_missing_state_root_is_created_with_its_parents(tmp_path: Path) -> None:
    project = _project(tmp_path)
    env = {"XDG_STATE_HOME": str(tmp_path / "deep" / "nested" / "state")}
    assert record_failure(str(project), "s", 3, env) == "retry 1"


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_an_unwritable_state_root_fails_closed(tmp_path: Path) -> None:
    project = _project(tmp_path)
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        line = record_failure(str(project), "s", 3, {"XDG_STATE_HOME": str(locked)})
    finally:
        locked.chmod(0o700)
    assert line.startswith("unrecorded cannot write ") and "Permission denied" in line


def test_no_home_fails_closed(tmp_path: Path) -> None:
    project = _project(tmp_path)
    assert record_failure(str(project), "s", 3, {}).startswith("unrecorded ")


def test_a_failed_write_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _project(tmp_path)

    def deny(*args: object) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(retry_state.os, "replace", deny)
    line = record_failure(str(project), "s", 3, _env(tmp_path))
    assert line.startswith("unrecorded ") and "denied" in line
    counter = _counter(tmp_path, project)
    assert list(counter.parent.iterdir()) == []  # the half-written file is cleaned up


def test_a_failed_write_does_not_retire_the_legacy_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project(tmp_path)
    legacy = _legacy(project, "1")

    def deny(*args: object) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(retry_state.os, "replace", deny)
    assert record_failure(str(project), "s", 3, _env(tmp_path)).startswith("unrecorded ")
    assert legacy.read_text() == "1"


# --- migration from the in-tree counter ------------------------------------------


def _legacy(project: Path, text: str, sid: str = "s") -> Path:
    legacy = project / ".meta-harness" / "stop_attempts" / sid
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(text)
    return legacy


def test_a_legacy_count_is_carried_over_and_retired(tmp_path: Path) -> None:
    project = _project(tmp_path)
    legacy = _legacy(project, "1")
    assert record_failure(str(project), "s", 3, _env(tmp_path)) == "retry 2"
    assert not legacy.exists()
    assert not legacy.parent.exists()  # the emptied legacy directory goes too
    assert _counter(tmp_path, project).read_text() == "2"


def test_a_legacy_count_at_the_cap_escalates(tmp_path: Path) -> None:
    project = _project(tmp_path)
    legacy = _legacy(project, "2")
    assert record_failure(str(project), "s", 3, _env(tmp_path)) == "escalate 3"
    assert not legacy.exists()


def test_a_legacy_count_can_never_lower_the_real_one(tmp_path: Path) -> None:
    project = _project(tmp_path)
    env = _env(tmp_path)
    record_failure(str(project), "s", 3, env)
    record_failure(str(project), "s", 3, env)
    _legacy(project, "0")
    assert record_failure(str(project), "s", 3, env) == "escalate 3"


@pytest.mark.parametrize("text", ["garbage", "", "-5"])
def test_a_garbage_legacy_count_counts_as_nothing(tmp_path: Path, text: str) -> None:
    project = _project(tmp_path)
    _legacy(project, text)
    assert record_failure(str(project), "s", 3, _env(tmp_path)) == "retry 1"


def test_an_unreadable_legacy_count_counts_as_nothing(tmp_path: Path) -> None:
    project = _project(tmp_path)
    (project / ".meta-harness" / "stop_attempts" / "s").mkdir(parents=True)
    assert record_failure(str(project), "s", 3, _env(tmp_path)) == "retry 1"


def test_other_sessions_legacy_files_are_left_in_place(tmp_path: Path) -> None:
    project = _project(tmp_path)
    other = _legacy(project, "2", sid="other")
    _legacy(project, "1")
    assert record_failure(str(project), "s", 3, _env(tmp_path)) == "retry 2"
    assert other.read_text() == "2"


# --- clear -----------------------------------------------------------------------


def test_clear_removes_both_the_state_and_the_legacy_count(tmp_path: Path) -> None:
    project = _project(tmp_path)
    env = _env(tmp_path)
    record_failure(str(project), "s", 3, env)
    legacy = _legacy(project, "1")

    clear(str(project), "s", env)

    assert not _counter(tmp_path, project).exists()
    assert not legacy.exists()
    assert record_failure(str(project), "s", 3, env) == "retry 1"


def test_clear_with_nothing_recorded_is_a_no_op(tmp_path: Path) -> None:
    project = _project(tmp_path)
    clear(str(project), "s", _env(tmp_path))
    assert not (tmp_path / "state").exists()  # clearing never creates state


def test_clear_without_a_usable_home_still_retires_the_legacy_count(tmp_path: Path) -> None:
    project = _project(tmp_path)
    legacy = _legacy(project, "1")
    clear(str(project), "s", {})
    assert not legacy.exists()


# --- main --------------------------------------------------------------------------


def test_main_fail_prints_the_verdict(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project = _project(tmp_path)
    assert main(["fail", str(project), "s", "3"], _env(tmp_path)) == 0
    assert capsys.readouterr().out == "retry 1\n"


def test_main_passes_the_cap_through(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project = _project(tmp_path)
    main(["fail", str(project), "s", "1"], _env(tmp_path))
    assert capsys.readouterr().out == "escalate 1\n"


def test_main_uses_the_injected_resolver(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env = _env(tmp_path)
    main(["fail", "/a", "s", "3"], env, resolve=lambda _p: "/same")
    main(["fail", "/b", "s", "3"], env, resolve=lambda _p: "/same")
    assert capsys.readouterr().out == "retry 1\nretry 2\n"


def test_main_clear_uses_the_injected_resolver(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env = _env(tmp_path)
    main(["fail", "/a", "s", "3"], env, resolve=lambda _p: "/same")
    main(["clear", "/b", "s"], env, resolve=lambda _p: "/same")
    main(["fail", "/a", "s", "3"], env, resolve=lambda _p: "/same")
    assert capsys.readouterr().out == "retry 1\ncleared\nretry 1\n"


def test_main_clear(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project = _project(tmp_path)
    env = _env(tmp_path)
    main(["fail", str(project), "s", "3"], env)
    assert main(["clear", str(project), "s"], env) == 0
    assert capsys.readouterr().out == "retry 1\ncleared\n"
    assert not _counter(tmp_path, project).exists()


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["fail", "/p", "s"],
        ["fail", "/p", "s", "three"],
        ["fail", "/p", "s", "3", "extra"],
        ["clear", "/p", "s", "extra"],
        ["reset", "/p", "s"],
    ],
)
def test_main_rejects_malformed_arguments(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], argv: list[str]
) -> None:
    assert main(argv, _env(tmp_path)) == 0
    assert capsys.readouterr().out == "unrecorded bad-arguments\n"
    assert not (tmp_path / "state").exists()
