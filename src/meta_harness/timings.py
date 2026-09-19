"""How long each check took, read off the receipts (#253, ADR-0085).

A check records its own wall time in its receipt (``duration_ms``, inside the content
hash). These functions turn those numbers into the one line the gate prints. They report
and never judge: there is no budget here, no threshold and no verdict — a slow check is a
fact about this run, and what to do about it is a person's decision, not the gate's.

A missing ``duration_ms`` means *not measured* (an older harness, a receipt copied in by
the worktree executor) and is left out, never read as zero.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

MINUTE_MS = 60_000

#: How many checks the gate names on its `slowest:` line.
DEFAULT_LIMIT = 3


def format_duration_ms(ms: int) -> str:
    """``92_400`` → ``"1m 32s"``; under a minute, tenths of a second."""
    if ms < 0:
        raise ValueError(f"negative duration: {ms}ms — the clock went backwards")
    if ms < MINUTE_MS:
        return f"{ms / 1000:.1f}s"
    minutes, rest = divmod(ms, MINUTE_MS)
    return f"{minutes}m {rest // 1000:02d}s"


def slowest(
    entries: Iterable[tuple[str, int | None]], limit: int = DEFAULT_LIMIT
) -> tuple[tuple[str, int], ...]:
    """The ``limit`` longest-running checks, longest first, unmeasured ones dropped.

    Ties keep the order they were given in, so the line is stable across runs of the
    same configuration.
    """
    measured: Sequence[tuple[str, int]] = [
        (cid, ms) for cid, ms in entries if isinstance(ms, int) and not isinstance(ms, bool)
    ]
    return tuple(sorted(measured, key=lambda pair: -pair[1])[:limit])


def timings_line(
    entries: Iterable[tuple[str, int | None]], limit: int = DEFAULT_LIMIT
) -> str | None:
    """The gate's one-line measurement, or ``None`` when nothing was measured."""
    ranked = slowest(entries, limit)
    if not ranked:
        return None
    parts = " · ".join(f"{cid} {format_duration_ms(ms)}" for cid, ms in ranked)
    return f"slowest: {parts}"
