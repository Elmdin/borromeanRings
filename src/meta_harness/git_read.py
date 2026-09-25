"""Ask git something, and never mistake "it failed" for "there is nothing" (#186).

The shell half of this has `borromeanrings_git_capture` (ADR-0088). This is the same
rule for the checks that read git from inside their embedded Python, where the shape was:

    out = subprocess.run(["git", "-C", root, *args], capture_output=True).stdout

`subprocess.run` without ``check=`` returns an object whose ``.stdout`` is empty when the
command failed — indistinguishable from a command that succeeded and found nothing. So a
repository whose objects cannot be read produced "empty history — nothing to scan", and a
file whose previous version could not be read looked like a file that never existed.

Every function here raises :class:`GitUnavailable` instead, carrying git's own words, and
bounds the call by the check's wall-clock limit (#256) so a hanging git fails closed
rather than holding the gate.
"""

from __future__ import annotations

import math
import os
import subprocess  # nosec B404 — fixed argv, no shell; reads the governed repository

#: The check's wall-clock limit, in seconds; `0` (or unset-and-negative) disables it.
TIMEOUT_ENV = "BORROMEANRINGS_CHECK_TIMEOUT"
DEFAULT_TIMEOUT_S = 300


class GitUnavailable(RuntimeError):
    """git could not answer, so nothing about the repository is known.

    Never to be caught and turned into an empty result: that is the bug this exists to
    prevent. Catch it to *report* it, and fail the check.
    """


def _timeout() -> float | None:
    """The bound in seconds, or ``None`` when it is deliberately disabled.

    ``nan`` and ``inf`` parse as floats without raising, and ``nan <= 0`` is False, so a
    naive guard let both through and ``subprocess.run(timeout=nan)`` waits forever: the
    bound silently defeated by a value that is not a number (review of #260). Anything
    that is not a finite number falls back to the default — never to "unbounded".
    """
    raw = os.environ.get(TIMEOUT_ENV, "")
    try:
        seconds = float(raw) if raw.strip() else float(DEFAULT_TIMEOUT_S)
    except ValueError:
        seconds = float(DEFAULT_TIMEOUT_S)
    if not math.isfinite(seconds):
        seconds = float(DEFAULT_TIMEOUT_S)
    return None if seconds <= 0 else seconds


def _run(root: str, argv: tuple[str, ...], stdin: str | None) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(  # nosec B603 B607 — fixed argv, no shell
            ["git", "-C", root, *argv],
            input=stdin.encode() if stdin is not None else None,
            capture_output=True,
            timeout=_timeout(),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitUnavailable(f"git {' '.join(argv)} timed out after {exc.timeout}s") from exc
    except OSError as exc:  # git missing, or the directory cannot be entered
        raise GitUnavailable(f"git {' '.join(argv)} could not be run: {exc}") from exc


def git_bytes(root: str, *argv: str, stdin: str | None = None) -> bytes:
    """git's stdout, or :class:`GitUnavailable` with its stderr — never a silent empty."""
    done = _run(root, argv, stdin)
    if done.returncode != 0:
        detail = done.stderr.decode("utf-8", "replace").strip().replace("\n", " ")
        raise GitUnavailable(f"git {' '.join(argv)} exited {done.returncode}: {detail}")
    return bytes(done.stdout)


def git_text(root: str, *argv: str, stdin: str | None = None) -> str:
    """:func:`git_bytes`, decoded. Undecodable bytes are replaced, never dropped."""
    return git_bytes(root, *argv, stdin=stdin).decode("utf-8", "replace")


def git_show(root: str, rev: str, path: str) -> str | None:
    """The contents of ``path`` at ``rev``, or ``None`` when it did not exist there.

    "Did not exist" is asked separately, with ``ls-tree``, which answers an absent path
    with success and empty output: reading the file and calling every failure "it is a
    new file" is how a whole-repository failure reported "no breaking changes" having
    compared nothing.
    """
    listed = git_text(root, "ls-tree", "--name-only", rev, "--", path).strip()
    if not listed:
        return None
    return git_text(root, "show", f"{rev}:{path}")
