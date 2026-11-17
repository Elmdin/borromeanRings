"""File-organization gates: keep a governed repo tidy.

Agents tend to dump specs at the repo root, scatter docs, and lay large test
suites out flat. A project DECLARES its layout conventions in ``borromeanrings.toml``
(``[layout]``) and borromeanRings enforces them fail-closed. Each rule is independently
opt-in (absent/zero ⇒ off). This module is the pure decision logic; the
``07_layout`` check gathers the filesystem facts and calls it.

See docs/specs/SPEC-layout.md and ADR-0018.
"""

from __future__ import annotations

from collections.abc import Sequence


def misplaced_specs(spec_paths: Sequence[str], specs_dir: str) -> list[str]:
    """Repo-relative ``SPEC*.md`` paths that are NOT under ``specs_dir``.

    Empty ``specs_dir`` ⇒ the spec-placement rule is off (returns nothing).
    """
    if not specs_dir:
        return []
    prefix = specs_dir.rstrip("/") + "/"
    return sorted(p for p in spec_paths if not p.startswith(prefix))


def disallowed_root_docs(root_docs: Sequence[str], allowlist: Sequence[str]) -> list[str]:
    """Repo-root ``.md`` filenames that are not in ``allowlist``.

    Empty ``allowlist`` ⇒ the root-doc rule is off (returns nothing).
    """
    if not allowlist:
        return []
    allowed = set(allowlist)
    return sorted(name for name in root_docs if name not in allowed)


def excess_flat_tests(flat_count: int, threshold: int) -> bool:
    """True iff ungrouped test files exceed ``threshold`` (``threshold`` ≤ 0 ⇒ off)."""
    return threshold > 0 and flat_count > threshold
