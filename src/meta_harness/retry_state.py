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

- It defeats the **same-tree** adversary: a wrapped agent confined to the
  project directory by its tooling cannot reach the count, whatever it deletes
  or rewrites there.
- It does **not** defeat a **same-user** adversary. Anything running as the
  same user can still write the state directory. The hook holds no secret and
  no storage the user cannot reach, so nothing it does can close that.

Fail-closed: when the count cannot be read or written, the verdict is
``unrecorded`` and the hook escalates to the human at once. Treating an
unrecordable count as zero is exactly the reset this module exists to prevent.

Migration: a counter the pre-ADR-0079 hook left in the tree is read, merged
with ``max`` and then removed. The in-tree location can therefore only ever
*raise* a count, never lower it.

Pure path derivation and decisions up top; the filesystem I/O below is thin and
the one impure input (path resolution) is injected. ``main`` is the hook's
entry point.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

APP_DIR = "borromeanrings"
COUNTER_DIR = "stop_attempts"
LEGACY_PARTS = (".meta-harness", "stop_attempts")
DIGEST_CHARS = 32
"""128 bits of sha256: collision-free for any real set of projects, short
enough to keep the state path readable."""

_VERBATIM_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
_DECIMAL = re.compile(r"[0-9]+")

Resolver = Callable[[str], str]


class StateUnavailable(Exception):
    """The retry count cannot be located, read or written. Callers fail closed."""


# --- pure: where the count lives ----------------------------------------------


def state_root(env: Mapping[str, str]) -> Path:
    """The XDG state base directory: ``$XDG_STATE_HOME`` or ``$HOME/.local/state``.

    A relative ``XDG_STATE_HOME`` is ignored, as the XDG Base Directory spec
    requires. Raises :class:`StateUnavailable` when neither yields an absolute
    path — never guesses a location (a guess could land inside the tree).
    """
    xdg = env.get("XDG_STATE_HOME", "")
    if os.path.isabs(xdg):
        return Path(xdg)
    home = env.get("HOME", "")
    if os.path.isabs(home):
        return Path(home) / ".local" / "state"
    raise StateUnavailable("no absolute XDG_STATE_HOME or HOME to keep the count under")


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "surrogateescape")).hexdigest()[:DIGEST_CHARS]


def project_digest(resolved_project: str) -> str:
    """Name a project by its resolved absolute path (symlinked routes share a count)."""
    return _digest(resolved_project)


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


def legacy_counter_path(project: Path, session_id: str) -> Path | None:
    """Where the pre-ADR-0079 hook kept this session's count, inside the tree.

    ``None`` for an id that was never safe to use as a path component.
    """
    if not _VERBATIM_ID.fullmatch(session_id):
        return None
    return project.joinpath(*LEGACY_PARTS, session_id)


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


def _read_legacy(path: Path | None) -> int:
    """An in-tree count, or ``0``. It can only raise the real count, so be lenient."""
    if path is None:
        return 0
    try:
        return parse_count(path.read_text()) or 0
    except OSError:
        return 0


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


def _retire_legacy(path: Path | None) -> None:
    """Remove the in-tree counter, and its directory once empty. Best-effort."""
    if path is None:
        return
    with contextlib.suppress(OSError):
        path.unlink()
    with contextlib.suppress(OSError):
        path.parent.rmdir()


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
    legacy = legacy_counter_path(Path(project), session_id)
    try:
        path = counter_path(env, resolve(project), session_id)
        attempts = max(_read_counter(path), _read_legacy(legacy)) + 1
        verdict = decide(attempts, cap)
        if verdict == "retry":
            _write_counter(path, attempts)
    except StateUnavailable as exc:
        return f"unrecorded {exc}"
    if verdict == "escalate":
        with contextlib.suppress(OSError):
            path.unlink()
    _retire_legacy(legacy)
    return f"{verdict} {attempts}"


def clear(
    project: str,
    session_id: str,
    env: Mapping[str, str],
    resolve: Resolver = os.path.realpath,
) -> None:
    """Forget this session's count after a passing gate. Best-effort, never creates state."""
    _retire_legacy(legacy_counter_path(Path(project), session_id))
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
