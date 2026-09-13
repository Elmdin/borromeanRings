"""Where the Stop hook keeps its retry count: outside the governed tree.

The Stop hook bounds the generate -> verify -> retry loop: after ``cap`` failed
gates it stops blocking and hands control to the human. That bound is only as
good as the count behind it. It used to live at
``<project>/.meta-harness/stop_attempts/<session>``, inside the tree the agent
works in, and a missing file read as ``0`` — so one ``rm`` bought unlimited
attempts (#218).

The count now lives under ``$XDG_STATE_HOME/borromeanrings/<digest>/`` (default
``~/.local/state``), where ``<digest>`` names the project by its resolved
absolute path (ADR-0079). What that buys, stated at its true size:

- Resistance to **accident** and to a **naive reset**: tidying ``.meta-harness/``,
  deleting the old counter or writing ``0`` into it no longer resets the count.
- **Failing closed**: when the count cannot be located, read or written, the
  verdict is ``unrecorded`` and the hook escalates to the human at once, where
  the old hook silently counted from zero.
- It is **not a bound against intent**. Anything running as the user can write
  the state directory, and that includes the agent's own code once the gate
  runs it: the gate executes the project's tests as the user, so a
  ``conftest.py`` can delete the count (#221 review, D3). Only a test run
  isolated from this state (another account, a privileged executor, a sandbox)
  closes that, and nothing in this module can.

Migration: a counter the pre-ADR-0079 hook left in the tree is read, merged
with ``max`` and then removed, reached without following any symlink. A
symlink anywhere on that path is refused as hostile (``unrecorded``): followed,
it let the migration delete the real count through the link (#221 review, D1).

Pure path derivation and decisions up top; the filesystem I/O below is thin and
the one impure input (path resolution) is injected. ``main`` is the hook's
entry point.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import re
import stat
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from meta_harness.state_home import StateUnavailable, project_digest, state_root

APP_DIR = "borromeanrings"
COUNTER_DIR = "stop_attempts"
LEGACY_PARTS = (".meta-harness", "stop_attempts")
DIGEST_CHARS = 32
"""128 bits of sha256: collision-free for any real set of projects, short
enough to keep the state path readable."""

_VERBATIM_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
_DECIMAL = re.compile(r"[0-9]+")

Resolver = Callable[[str], str]


# --- pure: where the count lives ----------------------------------------------
#
# The location is shared with the last-green record (#222), so it lives in
# meta_harness.state_home. Re-exported here: this module's callers and tests have
# always reached these names through retry_state, and the move is not theirs.


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "surrogateescape")).hexdigest()[:DIGEST_CHARS]


def session_filename(session_id: str) -> str:
    """A filename for a session id that cannot escape the counter directory.

    Ordinary ids (UUIDs) are kept verbatim so the state stays readable; anything
    else is hashed. Hashed names contain ``.``, which a verbatim id never does,
    so the two forms cannot collide.
    """
    if _VERBATIM_ID.fullmatch(session_id):
        return session_id
    return "h." + _digest(session_id)


def counter_path(env: Mapping[str, str], resolved_project: str, session_id: str) -> Path:
    """``<state root>/borromeanrings/<project digest>/stop_attempts/<session>``."""
    return (
        state_root(env)
        / APP_DIR
        / project_digest(resolved_project)
        / COUNTER_DIR
        / session_filename(session_id)
    )


def legacy_name(session_id: str) -> str | None:
    """The filename the pre-ADR-0079 hook used for this session, inside
    ``<project>/.meta-harness/stop_attempts/``. ``None`` for an id that was never
    safe to use as a path component."""
    return session_id if _VERBATIM_ID.fullmatch(session_id) else None


def is_inside(path: str, root: str) -> bool:
    """True when ``path`` is ``root`` or below it. Both must already be resolved."""
    return os.path.commonpath([path, root]) == root


def parse_count(text: str) -> int | None:
    """A non-negative ASCII decimal count, or ``None`` for anything else."""
    stripped = text.strip()
    return int(stripped) if _DECIMAL.fullmatch(stripped) else None


def decide(attempts: int, cap: int) -> str:
    """``retry`` below the cap, ``escalate`` at or above it."""
    return "retry" if attempts < cap else "escalate"


# --- thin I/O --------------------------------------------------------------------


def _read_counter(path: Path) -> int:
    """The recorded count; ``0`` only when no count was ever recorded.

    Unreadable or corrupt ⇒ :class:`StateUnavailable`: the agent cannot reach
    this file, so a bad value means something is wrong, not that it is zero.
    """
    try:
        text = path.read_text()
    except FileNotFoundError:
        return 0
    except OSError as exc:
        raise StateUnavailable(f"cannot read {path}: {exc.strerror or exc}") from exc
    value = parse_count(text)
    if value is None:
        raise StateUnavailable(f"corrupt count in {path}")
    return value


_DIR = os.O_RDONLY | os.O_DIRECTORY
_LEGACY_READ_BYTES = 64
"""A count is a handful of digits; never read more of an in-tree file than this."""


def _open_nofollow(name: str, flags: int, dir_fd: int) -> int | None:
    """Open ``name`` under ``dir_fd`` without following a symlink.

    ``None`` when it is absent or unusable. :class:`StateUnavailable` when it is
    a symlink: the in-tree legacy path is writable by the agent, and a link there
    could steer a read or a delete at the real count.
    """
    try:
        return os.open(name, flags | os.O_NOFOLLOW, dir_fd=dir_fd)
    except OSError as exc:
        try:
            mode = os.stat(name, dir_fd=dir_fd, follow_symlinks=False).st_mode
        except OSError:
            return None
        if stat.S_ISLNK(mode):
            raise StateUnavailable(
                f"refusing to follow a symlink at the legacy counter path ({name})"
            ) from exc
        return None


def _open_legacy_dirs(project: str, fds: list[int]) -> tuple[int, int] | None:
    """``(.meta-harness fd, stop_attempts fd)`` opened without following links.

    Every fd opened is appended to ``fds`` for the caller to close. ``None``
    when the legacy directory does not exist (nothing to migrate).
    """
    try:
        fds.append(os.open(project, _DIR))
    except OSError:
        return None
    for part in LEGACY_PARTS:
        fd = _open_nofollow(part, _DIR, fds[-1])
        if fd is None:
            return None
        fds.append(fd)
    return fds[-2], fds[-1]


def _read_legacy(dirs: tuple[int, int] | None, name: str | None) -> int:
    """An in-tree count, or ``0`` when there is none or it is unreadable."""
    if dirs is None or name is None:
        return 0
    fd = _open_nofollow(name, os.O_RDONLY, dirs[1])
    if fd is None:
        return 0
    try:
        data = os.read(fd, _LEGACY_READ_BYTES)
    except OSError:
        data = b""  # e.g. a directory where the file should be
    finally:
        os.close(fd)
    return parse_count(data.decode("utf-8", "replace")) or 0


def _retire_legacy(dirs: tuple[int, int] | None, name: str | None) -> None:
    """Remove the in-tree counter, and its directory once empty. Best-effort.

    Both removals go through the directory fds opened above, so a link planted
    after that walk cannot redirect them; ``unlink`` and ``rmdir`` never follow
    a final symlink.
    """
    if dirs is None or name is None:
        return
    with contextlib.suppress(OSError):
        os.unlink(name, dir_fd=dirs[1])
    with contextlib.suppress(OSError):
        os.rmdir(LEGACY_PARTS[1], dir_fd=dirs[0])


def _close_all(fds: list[int]) -> None:
    for fd in fds:
        with contextlib.suppress(OSError):
            os.close(fd)


def _ensure_private_dirs(counter_dir: Path) -> None:
    """Create the counter directory and its borromeanRings-owned parents as 0700."""
    owned = (counter_dir.parent.parent, counter_dir.parent, counter_dir)
    owned[0].parent.mkdir(parents=True, exist_ok=True)
    for directory in owned:
        directory.mkdir(mode=0o700, exist_ok=True)


def _write_counter(path: Path, value: int) -> None:
    tmp = path.with_name(path.name + ".tmp")
    try:
        _ensure_private_dirs(path.parent)
        tmp.write_text(str(value))
        os.replace(tmp, path)
    except OSError as exc:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise StateUnavailable(f"cannot write {path}: {exc.strerror or exc}") from exc


def record_failure(
    project: str,
    session_id: str,
    cap: int,
    env: Mapping[str, str],
    resolve: Resolver = os.path.realpath,
) -> str:
    """Count one failed gate and return the hook's verdict line.

    ``retry N`` or ``escalate N``; ``unrecorded <reason>`` when the count cannot
    be kept, which the hook treats as an escalation.
    """
    name = legacy_name(session_id)
    fds: list[int] = []
    try:
        resolved = resolve(project)
        root = resolve(str(state_root(env)))
        if is_inside(root, resolved):
            raise StateUnavailable(f"state root {root} is inside the project")
        path = counter_path(env, resolved, session_id)
        dirs = _open_legacy_dirs(project, fds) if name else None
        attempts = max(_read_counter(path), _read_legacy(dirs, name)) + 1
        verdict = decide(attempts, cap)
        if verdict == "retry":
            _write_counter(path, attempts)
        else:
            with contextlib.suppress(OSError):
                path.unlink()
        _retire_legacy(dirs, name)
    except StateUnavailable as exc:
        return f"unrecorded {exc}"
    finally:
        _close_all(fds)
    return f"{verdict} {attempts}"


def clear(
    project: str,
    session_id: str,
    env: Mapping[str, str],
    resolve: Resolver = os.path.realpath,
) -> None:
    """Forget this session's count after a passing gate. Best-effort, never creates state.

    A symlinked legacy path is left alone, not deleted through.
    """
    name = legacy_name(session_id)
    fds: list[int] = []
    with contextlib.suppress(StateUnavailable):
        _retire_legacy(_open_legacy_dirs(project, fds) if name else None, name)
    _close_all(fds)
    with contextlib.suppress(StateUnavailable, OSError):
        counter_path(env, resolve(project), session_id).unlink()


def main(argv: Sequence[str], env: Mapping[str, str], resolve: Resolver = os.path.realpath) -> int:
    """Hook entry point. ``fail <project> <session> <cap>`` | ``clear <project> <session>``.

    Prints one verdict line; the hook escalates on anything but ``retry N`` /
    ``escalate N``, so a crash here also fails closed. Always returns 0.
    """
    try:
        command, project, session_id, *rest = argv
        if command == "fail" and len(rest) == 1:
            line = record_failure(project, session_id, int(rest[0]), env, resolve)
        elif command == "clear" and not rest:
            clear(project, session_id, env, resolve)
            line = "cleared"
        else:
            raise ValueError(command)
    except ValueError:
        line = "unrecorded bad-arguments"
    print(line)
    return 0
