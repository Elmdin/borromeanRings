"""The merge policy: borromeanRings's self-extension safety invariant, as tested code.

borromeanRings may *extend* itself (human-approved merges of new capability) but never
*rewrite* itself (autonomous modification of its own core/gates). The single rule
that enforces that boundary lives here, separated from the git plumbing in
``merge.sh`` so it can be unit-tested in isolation.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MergeDecision:
    """The outcome of a merge-permission check."""

    allowed: bool
    reason: str


def decide_merge(*, gate_passed: bool, explicitly_requested: bool) -> MergeDecision:
    """Decide whether borromeanRings may perform a merge.

    A merge is allowed only when a human explicitly requested it *and* the gate
    passed. borromeanRings never originates a merge on its own, and never merges on a
    red gate (fail-closed).

    Args:
        gate_passed: whether ``verify.sh`` exited 0 on the branch being merged.
        explicitly_requested: whether a human invoked the merge for this change.

    Returns:
        A :class:`MergeDecision` with ``allowed`` and a human-readable ``reason``.
    """
    if not explicitly_requested:
        return MergeDecision(
            allowed=False,
            reason="merge must be explicitly requested by a human; "
            "borromeanRings never self-initiates a merge",
        )
    if not gate_passed:
        return MergeDecision(
            allowed=False,
            reason="the gate did not pass; refusing to merge (fail-closed)",
        )
    return MergeDecision(allowed=True, reason="explicitly requested and gate passed")
