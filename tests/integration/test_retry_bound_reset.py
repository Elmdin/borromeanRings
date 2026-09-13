"""The Stop hook's retry bound must survive the resets an in-tree agent can make directly.

Regression for #218. ``stop_gate.sh`` kept its retry counter at
``.meta-harness/stop_attempts/<session_id>`` inside the governed project and
read a missing or unreadable file as ``0``, so the agent it governs could buy
unlimited attempts with one ``rm``. The count now lives under
``$XDG_STATE_HOME/borromeanrings/<project-digest>/`` (ADR-0079), outside the
tree the agent is confined to.

Each reset route below is applied to the in-tree harness state and asserts two
things in order: that the attack actually changed something, and only then
that the bound still held. The ``control`` variants apply the same routes to
the out-of-tree state directory. They show the bound *breaking*, which is the
documented limit (anything running as the same user can still write there) and
is also what proves the routes are real attacks rather than no-ops.

What this file does NOT prove: that an in-tree agent cannot reset the count.
The gate runs the project's own code (its tests, its conftest.py) as the user,
and that code can delete the state directory like any same-user process can
(#221 review, D3). Only an isolated test run closes that; see ADR-0079.

Every test points ``XDG_STATE_HOME``, ``HOME`` and ``CLAUDE_CONFIG_DIR`` at
``tmp_path``. None of them may touch the real home directory.

Excluded from the mutmut run (setup.cfg): it drives the shell hook through a
repo-relative path. ``meta_harness.retry_state`` is covered by unit tests alone.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
STOP_GATE = BORROMEANRINGS_HOME / ".claude" / "hooks" / "stop_gate.sh"
SESSION = "sess-218"
CAP = 3

FAILING_CONFIG = (
    '[project]\nlanguage = "none"\npackage = "x"\n\n'
    '[checks]\nrequired = ["05_hygiene"]\n\n'
    '[hygiene]\nrequires = ["does-not-exist.md"]\n'  # the gate fails, fast
)
PASSING_CONFIG = FAILING_CONFIG.replace('["does-not-exist.md"]', "[]")


# --- harness ------------------------------------------------------------------


def _project(root: Path, name: str = "project") -> Path:
    project = root / name
    project.mkdir()
    (project / "borromeanrings.toml").write_text(FAILING_CONFIG)
    return project


def _env(tmp_path: Path, **overrides: str) -> dict[str, str]:
    """An environment whose state, home and Claude config all live under tmp_path."""
    env = dict(os.environ)
    env["XDG_STATE_HOME"] = str(tmp_path / "state")
    env["HOME"] = str(tmp_path / "home")
    env["CLAUDE_CONFIG_DIR"] = str(tmp_path / "claude-config")
    env.update(overrides)
    for key in ("XDG_STATE_HOME", "HOME", "CLAUDE_CONFIG_DIR"):
        assert env[key].startswith(str(tmp_path)), f"{key} escaped tmp_path: {env[key]}"
    return env


def _stop(
    project: Path, env: dict[str, str], session: str = SESSION
) -> subprocess.CompletedProcess[str]:
    run_env = dict(env)
    run_env["CLAUDE_PROJECT_DIR"] = str(project)
    return subprocess.run(
        ["bash", str(STOP_GATE)],
        input=json.dumps({"session_id": session, "stop_hook_active": False}),
        capture_output=True,
        text=True,
        timeout=120,
        env=run_env,
        cwd=project,  # the substrate runs hooks from the project the agent is in
    )


def _assert_blocked_at(result: subprocess.CompletedProcess[str], attempt: int) -> None:
    assert result.returncode == 2, (
        f"expected a retry block, got {result.returncode}: {result.stderr}"
    )
    assert f"attempt {attempt}/{CAP}" in result.stderr, result.stderr.splitlines()[:1]


def _assert_escalated(result: subprocess.CompletedProcess[str]) -> None:
    first = result.stderr.splitlines()[:1]
    assert result.returncode == 0, f"bound did not hold (rc={result.returncode}): {first}"
    assert "ESCALATION" in result.stderr, f"bound did not hold: {first}"
    assert f"failed {CAP} times" in result.stderr, first


def _state_counters(tmp_path: Path) -> list[Path]:
    return sorted((tmp_path / "state" / "borromeanrings").glob("*/stop_attempts/*"))


def _two_failures(project: Path, env: dict[str, str]) -> None:
    _assert_blocked_at(_stop(project, env), 1)
    _assert_blocked_at(_stop(project, env), 2)


# --- reset routes -------------------------------------------------------------
# Each takes the harness state directory an adversary can reach and the counter
# path inside it, performs the attack, and asserts the attack changed something.


def _files_under(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file() or p.is_symlink()] if root.is_dir() else []


def delete_counter_file(harness: Path, counter: Path) -> None:
    # The agent cannot know which file holds the count, so it removes every one.
    doomed = _files_under(harness)
    assert doomed, f"nothing to delete under {harness}: the attack would be a no-op"
    for path in doomed:
        path.unlink()
    assert not counter.exists() and not _files_under(harness)


def delete_counter_dir(harness: Path, counter: Path) -> None:
    assert harness.is_dir(), f"{harness} absent: the attack would be a no-op"
    shutil.rmtree(harness)
    assert not harness.exists() and not counter.exists()


def write_zero(harness: Path, counter: Path) -> None:
    before = counter.read_text() if counter.exists() else None
    counter.parent.mkdir(parents=True, exist_ok=True)
    counter.write_text("0")
    assert before != "0" and counter.read_text() == "0"


def write_zero_keep_mtime(harness: Path, counter: Path) -> None:
    original = counter.stat() if counter.exists() else None
    counter.parent.mkdir(parents=True, exist_ok=True)
    counter.write_text("0")
    if original is not None:
        os.utime(counter, ns=(original.st_atime_ns, original.st_mtime_ns))
        want = original.st_mtime_ns
    else:  # nothing to restore: make the forged file look long-settled instead
        want = counter.stat().st_mtime_ns - 3_600 * 10**9
        os.utime(counter, ns=(want, want))
    assert counter.read_text() == "0" and counter.stat().st_mtime_ns == want


ROUTES: dict[str, Callable[[Path, Path], None]] = {
    "delete-counter-file": delete_counter_file,
    "delete-counter-dir": delete_counter_dir,
    "write-zero": write_zero,
    "write-zero-restore-mtime": write_zero_keep_mtime,
}


@pytest.mark.parametrize("route", sorted(ROUTES))
def test_in_tree_reset_does_not_restore_attempts(tmp_path: Path, route: str) -> None:
    project = _project(tmp_path)
    env = _env(tmp_path)
    _two_failures(project, env)

    harness = project / ".meta-harness"
    ROUTES[route](harness, harness / "stop_attempts" / SESSION)

    _assert_escalated(_stop(project, env))


@pytest.mark.parametrize("route", sorted(ROUTES))
def test_control_same_user_reset_of_the_state_dir_still_works(tmp_path: Path, route: str) -> None:
    """The documented limit: the state directory is same-user writable.

    Applying the same route where the count actually lives resets the bound.
    This is not a property to be proud of; it pins the claim at its true size
    and proves each route above is a live attack, not a no-op.
    """
    project = _project(tmp_path)
    env = _env(tmp_path)
    _two_failures(project, env)

    counters = _state_counters(tmp_path)
    assert len(counters) == 1, counters
    counter = counters[0]
    ROUTES[route](counter.parent.parent, counter)

    _assert_blocked_at(_stop(project, env), 1)


def test_shadowing_the_helper_module_from_the_tree_does_not_reset(tmp_path: Path) -> None:
    """An in-tree ``meta_harness`` package must not replace the real counter logic.

    ``python3 -`` puts the working directory first on ``sys.path`` and the hook
    runs from the project, so a planted package would win the import.
    """
    project = _project(tmp_path)
    env = _env(tmp_path)
    _two_failures(project, env)

    shadow = project / "meta_harness"
    shadow.mkdir()
    (shadow / "__init__.py").write_text("")
    (shadow / "retry_state.py").write_text(
        "def main(argv, env, **kwargs):\n    print('retry 1')\n    return 0\n"
    )
    # Changed something: a naive import from the project really does pick it up.
    probe = subprocess.run(
        [
            "python3",
            "-",
        ],
        input="import meta_harness.retry_state as m; print(m.__file__)",
        capture_output=True,
        text=True,
        cwd=project,
        env={**env, "PYTHONPATH": str(BORROMEANRINGS_HOME / "src")},
        timeout=30,
    )
    assert probe.stdout.strip() == str(shadow / "retry_state.py"), probe.stderr

    _assert_escalated(_stop(project, env))


def test_a_planted_stdlib_module_cannot_reset(tmp_path: Path) -> None:
    """#221 D2: a ``json.py`` in the project must not replace the hook's parser.

    Every Python the hook starts would otherwise import it: the working
    directory is the project, and ``python3 -c`` puts it first on ``sys.path``.
    This one hands out a fresh session id per Stop, so each Stop is attempt 1.
    """
    project = _project(tmp_path)
    env = _env(tmp_path)
    (project / "json.py").write_text(
        "import uuid\n"
        "def load(fp):\n    return {'session_id': uuid.uuid4().hex, 'stop_hook_active': False}\n"
        "def loads(s, **kw):\n    return load(None)\n"
        "def dumps(o, **kw):\n    return '{}'\n"
    )
    probe = subprocess.run(
        ["python3", "-c", "import json; print(json.__file__)"],
        capture_output=True,
        text=True,
        cwd=project,
        env=env,
        timeout=30,
    )
    assert probe.stdout.strip() == str(project / "json.py"), probe.stderr  # the attack is live

    _two_failures(project, env)
    _assert_escalated(_stop(project, env))


def _digest_dir(tmp_path: Path, project: Path) -> Path:
    digest = hashlib.sha256(os.path.realpath(project).encode()).hexdigest()[:32]
    return tmp_path / "state" / "borromeanrings" / digest


@pytest.mark.parametrize("level", ["meta-harness", "stop_attempts"])
def test_a_symlinked_legacy_dir_cannot_delete_the_real_count(tmp_path: Path, level: str) -> None:
    """#221 D1: the migration retired the legacy file *through* a planted symlink.

    Planted before the first Stop (dangling until the hook creates the state),
    ``.meta-harness/stop_attempts -> <state>/stop_attempts`` made every Stop
    delete the count it had just written. The link must be refused, not followed.
    """
    project = _project(tmp_path)
    env = _env(tmp_path)
    real = _digest_dir(tmp_path, project)
    link, target = {
        "meta-harness": (project / ".meta-harness", real),
        "stop_attempts": (project / ".meta-harness" / "stop_attempts", real / "stop_attempts"),
    }[level]
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target, target_is_directory=True)
    assert link.is_symlink() and os.readlink(link) == str(target)  # planted, points at the count

    for _ in range(3):  # refused every time, never counted from zero
        result = _stop(project, env)
        first = result.stderr.splitlines()[:1]
        assert result.returncode == 0 and "could not record" in result.stderr, first
        assert "symlink" in result.stderr, first
    assert link.is_symlink()


def test_a_state_root_inside_the_project_fails_closed(tmp_path: Path) -> None:
    project = _project(tmp_path)
    env = _env(tmp_path, XDG_STATE_HOME=str(tmp_path / "project" / ".state"))
    result = _stop(project, env)
    _assert_failed_closed(result, project)
    assert "inside the project" in result.stderr
    assert not (project / ".state").exists()


HOOKS = STOP_GATE.parent
_PYTHON = re.compile(r"\bpython3?\b")


def test_every_hook_python_runs_through_the_neutral_cwd_helper() -> None:
    """Fix the class (#221 D2): no hook starts Python from the project directory.

    ``borromeanrings_py`` in ``_lib.sh`` is the only place allowed to name the
    interpreter. It changes to ``/`` first, which keeps the project off
    ``sys.path`` on every supported Python and leaves ``PYTHONPATH`` alone.

    ``python3 -P`` (3.11+) and ``-I`` are banned outright: ``requires-python``
    is 3.10, ``-P`` is an unknown option there, and CI (3.12 only) would never
    see the break. ``-I`` also discards ``PYTHONPATH``, which is how the hooks
    find ``meta_harness``.
    """
    offenders = []
    for script in sorted(HOOKS.glob("*.sh")):
        for number, line in enumerate(script.read_text().splitlines(), 1):
            code = line.split("#", 1)[0] if not line.lstrip().startswith("#") else ""
            if re.search(r"python3?\s+-[IP]\b", line):
                offenders.append(f"{script.name}:{number}: banned flag: {line.strip()}")
            elif _PYTHON.search(code) and not (
                script.name == "_lib.sh" and re.search(r"\(cd / &&.*\bpython3\b", code)
            ):
                offenders.append(f"{script.name}:{number}: {line.strip()}")
    assert not offenders, "\n".join(offenders)


# --- where the count lives ------------------------------------------------------


def test_the_count_lives_outside_the_tree(tmp_path: Path) -> None:
    project = _project(tmp_path)
    env = _env(tmp_path)
    state = tmp_path / "state"
    assert not state.exists()  # the hook must create it, not the fixture

    _two_failures(project, env)

    assert not (project / ".meta-harness" / "stop_attempts").exists()
    counters = _state_counters(tmp_path)
    assert len(counters) == 1, counters
    assert counters[0].read_text() == "2"
    assert (counters[0].parent.parent.stat().st_mode & 0o077) == 0  # private to the user


def test_two_projects_count_independently(tmp_path: Path) -> None:
    env = _env(tmp_path)
    first, second = _project(tmp_path, "first"), _project(tmp_path, "second")

    _two_failures(first, env)
    _assert_blocked_at(_stop(second, env), 1)  # same session id, different project
    _assert_escalated(_stop(first, env))
    assert len(list((tmp_path / "state" / "borromeanrings").iterdir())) == 2


def test_a_symlinked_path_shares_the_count(tmp_path: Path) -> None:
    env = _env(tmp_path)
    real = _project(tmp_path, "real")
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)

    _assert_blocked_at(_stop(link, env), 1)
    _assert_blocked_at(_stop(real, env), 2)
    _assert_escalated(_stop(link, env))


def test_a_pass_clears_the_count(tmp_path: Path) -> None:
    project = _project(tmp_path)
    env = _env(tmp_path)
    _two_failures(project, env)
    assert _state_counters(tmp_path)

    (project / "borromeanrings.toml").write_text(PASSING_CONFIG)
    assert _stop(project, env).returncode == 0
    assert not _state_counters(tmp_path)

    (project / "borromeanrings.toml").write_text(FAILING_CONFIG)
    _assert_blocked_at(_stop(project, env), 1)


# --- fail closed ------------------------------------------------------------------


def _assert_failed_closed(result: subprocess.CompletedProcess[str], project: Path) -> None:
    first = result.stderr.splitlines()[:1]
    assert result.returncode == 0, f"treated an unrecordable count as zero: {first}"
    assert "ESCALATION" in result.stderr and "could not record" in result.stderr, first
    assert "RESULT: FAIL" in result.stderr  # the human still sees why the gate failed
    assert not (project / ".meta-harness" / "stop_attempts").exists()  # no in-tree fallback


def test_a_state_root_that_is_a_file_fails_closed(tmp_path: Path) -> None:
    project = _project(tmp_path)
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("")
    env = _env(tmp_path, XDG_STATE_HOME=str(blocker))

    _assert_failed_closed(_stop(project, env), project)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_an_unwritable_state_root_fails_closed(tmp_path: Path) -> None:
    project = _project(tmp_path)
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        env = _env(tmp_path, XDG_STATE_HOME=str(locked))
        _assert_failed_closed(_stop(project, env), project)
        _assert_failed_closed(_stop(project, env), project)  # every time, not just once
    finally:
        locked.chmod(0o700)


def test_no_usable_home_fails_closed(tmp_path: Path) -> None:
    project = _project(tmp_path)
    env = _env(tmp_path)
    del env["XDG_STATE_HOME"]
    env["HOME"] = ""
    _assert_failed_closed(_stop(project, env), project)


# --- migration --------------------------------------------------------------------


def test_a_mid_retry_in_tree_count_is_carried_over(tmp_path: Path) -> None:
    """A project upgraded mid-retry keeps its count; the in-tree file is retired."""
    project = _project(tmp_path)
    env = _env(tmp_path)
    legacy = project / ".meta-harness" / "stop_attempts" / SESSION
    legacy.parent.mkdir(parents=True)
    legacy.write_text("2")  # what the pre-#218 hook left after two failures

    _assert_escalated(_stop(project, env))
    assert not legacy.exists()


def test_the_migration_is_retired_after_it_imports(tmp_path: Path) -> None:
    project = _project(tmp_path)
    env = _env(tmp_path)
    legacy = project / ".meta-harness" / "stop_attempts" / SESSION
    legacy.parent.mkdir(parents=True)
    legacy.write_text("1")

    _assert_blocked_at(_stop(project, env), 2)
    assert not legacy.exists()
    assert [c.read_text() for c in _state_counters(tmp_path)] == ["2"]
