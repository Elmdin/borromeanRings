"""Coupling ratchet — the worst efferent coupling (fan-out) in the internal
module graph may not regress.

A module that imports many internal siblings knows too much: it is hard to change
in isolation and signals weak cohesion (matrix row **D — coupling/cohesion
metrics**). We ratchet the **maximum fan-out** across the package — non-regression,
no arbitrary ceiling — so a new god-module fails the gate until its dependencies
are pared back (or the baseline is deliberately raised).

Native: reuses :func:`meta_harness.architecture.build_import_graph` (no external
tool). ``fan_in`` is exposed too (afferent coupling) for reporting. See
docs/specs/SPEC-coupling.md and ADR-0038.
"""

from __future__ import annotations

from pathlib import Path

from meta_harness.architecture import Graph, build_import_graph


def fan_out(graph: Graph) -> dict[str, int]:
    """Efferent coupling: internal modules each module imports."""
    return {module: len(deps) for module, deps in graph.items()}


def fan_in(graph: Graph) -> dict[str, int]:
    """Afferent coupling: how many internal modules import each module."""
    counts = {module: 0 for module in graph}
    for deps in graph.values():
        for target in deps:
            if target in counts:
                counts[target] += 1
    return counts


def worst_fan_out(src_root: Path | str, package: str) -> tuple[int, str]:
    """The highest fan-out across ``package`` and the module that has it."""
    graph = build_import_graph(src_root, package)
    counts = fan_out(graph)
    if not counts:
        return 0, ""
    # Deterministic tie-break by name so the reported worst module is stable.
    module = max(counts, key=lambda name: (counts[name], name))
    return counts[module], module
