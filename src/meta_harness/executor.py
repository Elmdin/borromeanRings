"""Executor conformance: when do two receipt bundles mean the same thing?

`SPEC-executor.md` (lands with #203) makes "run this check against this snapshot
and give me a receipt" a contract with more than one implementation: `local` (the
gate's own in-tree run) is the reference, and `worktree` (`run-in-worktree.sh`,
ADR-0076) is the second. A second implementation is only worth anything if it can
be *checked* against the first, and byte-identical bundles are unattainable — the
`log` path, the `content_sha256` that covers it, the `run_id` in every path and the
timings inside test output all differ per run, legitimately.

So conformance is an **equivalence relation**, and this module is where it lives:

- :func:`receipt_differences` — receipts are equal field by field, except the
  volatile ones (:data:`VOLATILE_FIELDS`) and any executor-namespaced extra.
  Check-specific extras (``score``, ``coverage_percent``, ``worst_function``, …)
  are compared **exactly**: they are what the receipt actually claims.
- :func:`canonicalise_log` — logs are equal after the run's own paths and its
  durations are masked, and after nothing else. A diff that survives
  canonicalisation is a real divergence: the fix is to add the new source of noise
  here, deliberately and on the record, never to loosen the field comparison.
- :func:`import_shadow_violation` — the one toolchain hazard a worktree run has
  that a local run does not: an editable install whose import points back at the
  primary checkout, so the checks would test the primary's code and report it
  against the worktree's snapshot. A valid receipt for the wrong tree is exactly
  the false green this project exists to prevent, so the executor asks this
  question before it runs anything.

Pure functions over strings and mappings — no I/O, no git, no subprocess — so the
conformance rule itself is unit-testable to exact values and the shell entry point
stays a thin orchestrator.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

#: Receipt fields that differ between two honest runs of the same snapshot and are
#: therefore excluded from the comparison: ``log`` is a path in the executor's own
#: namespace, and ``content_sha256`` covers that path (it stays *verified* against
#: its own log on each side — excluded here, never unchecked).
VOLATILE_FIELDS: tuple[str, ...] = ("log", "content_sha256")

#: Extras an executor is allowed to add about itself; they describe the executor,
#: not the check's finding, so they are not part of the equivalence.
EXECUTOR_FIELD_PREFIX = "executor"

#: A wall-clock duration as tools print it (``0.83s``, ``12.50s``). Deliberately
#: does NOT match an integer-second value: ``TIMED OUT after 300s`` is the declared
#: bound, part of the finding, and must survive canonicalisation.
_DURATION_RE = re.compile(r"\b\d+\.\d+s\b")

#: What a masked duration is replaced by.
DURATION_MASK = "<T>"

#: What ``find_spec`` reports as the origin of a **namespace** package: it has no
#: single file to resolve, so there is nothing to compare against the worktree.
NAMESPACE_ORIGIN = "namespace"


def canonicalise_log(text: str, replacements: Sequence[tuple[str, str]] = ()) -> str:
    """Mask a log's run-specific noise: each ``(needle, mask)`` pair, then durations.

    Needles are applied **longest first**, so a caller may pass the project root and
    the run directory (which lives inside it) in any order and still get the run
    directory replaced as a whole. Empty needles are ignored — an empty string would
    otherwise match everywhere.
    """
    out = text
    for needle, mask in sorted(replacements, key=lambda pair: len(pair[0]), reverse=True):
        if not needle:
            continue
        out = out.replace(needle, mask)
    return _DURATION_RE.sub(DURATION_MASK, out)


def _comparable(receipt: Mapping[str, object], ignored: frozenset[str]) -> dict[str, object]:
    return {
        key: value
        for key, value in receipt.items()
        if key not in ignored and not key.startswith(EXECUTOR_FIELD_PREFIX)
    }


def receipt_differences(
    reference: Mapping[str, object],
    candidate: Mapping[str, object],
    *,
    ignored: Iterable[str] = VOLATILE_FIELDS,
) -> tuple[str, ...]:
    """Every way ``candidate`` differs from ``reference``, as readable lines (sorted).

    Empty ⇒ the two receipts are equivalent: same fields, same values, extras
    included. A field present on only one side is reported as such rather than
    silently skipped — an executor that drops or invents a field has diverged just
    as much as one that changes a value.
    """
    ignore = frozenset(ignored)
    left = _comparable(reference, ignore)
    right = _comparable(candidate, ignore)
    lines: list[str] = []
    for key in sorted(set(left) | set(right)):
        if key not in right:
            lines.append(f"{key}: only in reference ({left[key]!r})")
        elif key not in left:
            lines.append(f"{key}: only in candidate ({right[key]!r})")
        elif left[key] != right[key]:
            lines.append(f"{key}: {left[key]!r} != {right[key]!r}")
    return tuple(lines)


def import_shadow_violation(module_origin: str, worktree_root: str) -> str | None:
    """Message if ``module_origin`` resolves outside ``worktree_root``, else ``None``.

    ``module_origin`` is where Python actually resolves the governed project's
    package from (``importlib.util.find_spec(...).origin``), empty when the package
    is not importable at all — nothing to shadow, so no violation. Anything inside
    the worktree is correct by construction. Anything outside it means an editable
    install (or a stray ``PYTHONPATH``) wins over the snapshot, and the run would
    report on code it did not check out.

    **Known limit:** a *namespace* package has no single origin — ``find_spec``
    reports :data:`NAMESPACE_ORIGIN` (or ``None``, which reaches here as ``""``)
    while its portions may live in several directories, one of which could be
    outside the worktree. This guard cannot see that and says "no violation"; the
    portion list would have to be checked instead. Recorded rather than pretended
    away — a governed project whose package is a namespace package is not covered.
    """
    if not module_origin or module_origin == NAMESPACE_ORIGIN:
        return None
    if Path(module_origin).resolve().is_relative_to(Path(worktree_root).resolve()):
        return None
    return (
        f"import shadow: the package resolves to {module_origin}, outside the worktree "
        f"{worktree_root} — an editable install points at the primary checkout, so the "
        "run would test the primary's code and report it against this snapshot"
    )
