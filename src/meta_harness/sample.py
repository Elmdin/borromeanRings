"""A small, real module so the v0 gate exercises actual typed, tested code.

The function mirrors borromeanRings's own fail-closed rule, which makes it a fitting
first inhabitant of the repo it governs.
"""

from collections.abc import Iterable


def overall_status(statuses: Iterable[str]) -> str:
    """Aggregate per-check statuses into one verdict, failing closed.

    Returns ``"pass"`` only when *every* status is ``"pass"``. Any non-pass
    status — or an empty input (absence of proof) — yields ``"fail"``. This is
    the same rule borromeanRings's gate applies across its checks.

    Args:
        statuses: the individual check statuses to aggregate.

    Returns:
        ``"pass"`` if all statuses are ``"pass"`` and at least one exists,
        otherwise ``"fail"``.
    """
    materialized = list(statuses)
    if not materialized:
        return "fail"
    return "pass" if all(status == "pass" for status in materialized) else "fail"
