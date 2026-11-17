"""Docstring-coverage measurement for a non-regression ratchet.

Counts *documentable* definitions — the module itself, and every public class,
function, and method (names not starting with ``_``) — and how many carry a
docstring. The check ratchets the fraction against a recorded baseline: it may
not fall, but there is no arbitrary target to game (a genuine signal, not a
number). Native stdlib ``ast``; no external tool.

Analysis is pure (``analyze_source`` takes text, returns counts);
``measure_package`` is the thin filesystem walk. ``__init__.py`` package markers
are excluded so an empty one does not distort the fraction. See
docs/specs/SPEC-docstrings.md and ADR-0029.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

_Def = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


@dataclass(frozen=True)
class DocstringStats:
    """Documented vs total documentable definitions."""

    documented: int
    total: int

    @property
    def coverage(self) -> float:
        """Documented fraction in [0, 1]; 1.0 when there is nothing to document."""
        return 1.0 if self.total == 0 else self.documented / self.total

    def __add__(self, other: DocstringStats) -> DocstringStats:
        return DocstringStats(self.documented + other.documented, self.total + other.total)


def _count_scope(body: list[ast.stmt]) -> DocstringStats:
    """Count public definitions directly in ``body``, descending into classes but
    NOT into function bodies (nested/inner functions are not part of the public
    API surface and are excluded, matching common docstring-coverage tools)."""
    stats = DocstringStats(0, 0)
    for node in body:
        if isinstance(node, _Def) and not node.name.startswith("_"):
            documented = 1 if ast.get_docstring(node) is not None else 0
            stats = stats + DocstringStats(documented, 1)
            if isinstance(node, ast.ClassDef):
                stats = stats + _count_scope(node.body)
    return stats


def analyze_source(source: str) -> DocstringStats:
    """Count documentable definitions and how many have docstrings in ``source``."""
    tree = ast.parse(source)
    module = DocstringStats(1 if ast.get_docstring(tree) is not None else 0, 1)
    return module + _count_scope(tree.body)


def measure_package(src_root: Path | str, package: str) -> DocstringStats:
    """Aggregate docstring coverage over ``package`` (excluding ``__init__.py``)."""
    pkg_dir = Path(src_root) / package
    stats = DocstringStats(0, 0)
    for path in sorted(pkg_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        stats = stats + analyze_source(path.read_text(encoding="utf-8"))
    return stats
