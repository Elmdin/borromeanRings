"""Cross-invocation dedupe for substrate hooks.

The same hook can be registered more than once for one workspace — a
project-level ``.claude/settings.json`` entry plus the user-level one written
by ``install-global.sh``. The substrate then runs the identical script twice
per event. For hooks whose effect is *not* idempotent that is a real defect:
the prompt-rewrite directive gets injected twice per prompt, and the Stop gate
runs twice, double-counting retry attempts toward its escalation cap.

:func:`claim` gives such hooks an atomic first-writer-wins claim on each event
occurrence, keyed by event name + a caller-chosen key, with a freshness window:
the duplicate invocation (arriving within the window) loses and yields.

Fail-open by design: on any filesystem error the caller proceeds. A lost
dedupe merely duplicates work; a false dedupe would silently drop governance.
"""

import contextlib
import hashlib
import os
import time
from pathlib import Path

DEFAULT_WINDOW_SECONDS = 5.0
"""Duplicate registrations fire within moments of each other; legitimate
repeat events (a later prompt, the next Stop) arrive far outside this window —
a Stop retry alone includes a full gate run plus an agent turn."""


def claim(
    marker_dir: Path, event: str, key: str, window_seconds: float = DEFAULT_WINDOW_SECONDS
) -> bool:
    """Atomically claim the right to handle one hook-event occurrence.

    Args:
        marker_dir: directory for marker files (created if missing), normally
            ``<project>/.meta-harness/hook_markers``.
        event: hook event name (e.g. ``stop``, ``user_prompt_submit``).
        key: identifies the occurrence (e.g. session id, or session id +
            prompt); hashed, so any length is fine.
        window_seconds: how long a claim shadows duplicates.

    Returns:
        True if this invocation should proceed (first claimant, or the prior
        claim is stale); False if a fresh claim exists — a duplicate
        registration already handled this occurrence.
    """
    marker = _marker_path(marker_dir, event, key)
    now = time.time()

    try:
        marker_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return True  # cannot keep markers here → proceed (fail-open)

    try:
        fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            age = now - marker.stat().st_mtime
        except OSError:
            return True  # marker vanished mid-race → proceed (fail-open)
        if age < window_seconds:
            return False  # fresh claim by the other registration → yield
        os.utime(marker, (now, now))  # stale → reclaim and refresh the window
        return True
    except OSError:
        return True  # marker not creatable → proceed (fail-open)

    os.close(fd)
    return True


def release(marker_dir: Path, event: str, key: str) -> None:
    """Remove a claim so the next occurrence of this event starts fresh.

    A claimant whose work is *slow and must re-run on every legitimate
    occurrence* (the Stop gate) releases its claim when it finishes: while the
    work is in flight the marker shadows the duplicate registration, and after
    release the next real occurrence claims immediately — the freshness window
    then only covers duplicate-arrival skew and crash recovery, so it can stay
    small without ever shadowing a legitimate re-run. Best-effort: releasing a
    marker that is already gone (or unremovable) is not an error.
    """
    # A lingering marker just expires via the window; never fail the hook.
    with contextlib.suppress(OSError):
        _marker_path(marker_dir, event, key).unlink(missing_ok=True)


def _marker_path(marker_dir: Path, event: str, key: str) -> Path:
    digest = hashlib.sha256(key.encode()).hexdigest()[:16]
    return marker_dir / f"{event}-{digest}"
