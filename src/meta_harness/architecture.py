"""Architectural fitness: enforce declared import-direction contracts over a
package's internal module graph.

Pure-Python (stdlib ``ast``) so the gate gains no external tool. It makes the
architecture documented in ARCHITECTURE.md executable: the style is an **acyclic**
registry of independent checks with a config **foundation** (`spine`, the Single
Choice) and a research **testbed** (`deep_research`) that must stay
non-load-bearing. Those become declared contracts:

  - ``leaves``        — a module that must import no internal sibling (a
    foundation like `spine`, so it never accretes domain dependencies);
  - ``private``       — a module no other internal module may import (a testbed
    kept out of the load-bearing graph);
  - ``forbidden``     — explicit "A must not import B" edges;
  - ``forbid_cycles`` — the internal graph must be acyclic.

The analysis functions are pure (a graph in, violations out) and unit-testable
without the filesystem; :func:`build_import_graph` is the thin I/O that derives a
graph from source. See docs/specs/SPEC-architecture.md and ADR-0027.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

Graph = dict[str, set[str]]  # module name -> internal sibling modules it imports


def _referenced_heads(node: ast.AST, package: str) -> list[str]:
    """Top-level module names a single import node references within ``package``
    (before filtering to actual siblings). Structured so every branch is
    reachable: a level-0 ``from … import`` always carries a module, so we never
    test that redundantly."""
    if isinstance(node, ast.Import):
        return [
            alias.name.split(".")[1]
            for alias in node.names
            if alias.name.split(".")[0] == package and "." in alias.name
        ]
    if isinstance(node, ast.ImportFrom):
        if node.module is None:
            return [alias.name.split(".")[0] for alias in node.names]  # from . import x
        parts = node.module.split(".")
        if node.level:
            return [parts[0]]  # from .sub import x
        if parts[0] == package and len(parts) >= 2:
            return [parts[1]]  # from package.sub import x
    return []


def _imported_siblings(source: str, package: str, modules: set[str]) -> set[str]:
    """Sibling modules of ``package`` imported by ``source`` (absolute or relative)."""
    deps: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        deps.update(head for head in _referenced_heads(node, package) if head in modules)
    return deps


def build_import_graph(src_root: Path | str, package: str) -> Graph:
    """Map each top-level module of ``package`` to the siblings it imports."""
    pkg_dir = Path(src_root) / package
    modules = {p.stem for p in pkg_dir.glob("*.py") if p.stem != "__init__"}
    graph: Graph = {}
    for path in sorted(pkg_dir.glob("*.py")):
        if path.stem == "__init__":
            continue
        graph[path.stem] = _imported_siblings(
            path.read_text(encoding="utf-8"), package, modules
        ) - {path.stem}
    return graph


@dataclass(frozen=True)
class ArchViolation:
    """A single breached architectural contract (its kind and a human-readable detail)."""

    kind: str  # "leaf" | "private" | "forbidden" | "cycle"
    detail: str


@dataclass(frozen=True)
class ArchReport:
    """Aggregate result of evaluating the contracts: ``ok`` plus any violations."""

    ok: bool
    violations: tuple[ArchViolation, ...]


def leaf_violations(graph: Graph, leaves: tuple[str, ...]) -> list[ArchViolation]:
    """Foundation modules in ``leaves`` that import an internal sibling."""
    out: list[ArchViolation] = []
    for module in leaves:
        imported = sorted(graph.get(module, set()))
        if imported:
            out.append(
                ArchViolation(
                    "leaf",
                    f"{module} must import no internal module (foundation) "
                    f"but imports: {', '.join(imported)}",
                )
            )
    return out


def private_violations(graph: Graph, private: tuple[str, ...]) -> list[ArchViolation]:
    """Modules importing a ``private`` module (which nothing may depend on)."""
    priv = set(private)
    out: list[ArchViolation] = []
    for module, deps in sorted(graph.items()):
        if module in priv:
            continue
        for target in sorted(deps & priv):
            out.append(
                ArchViolation(
                    "private",
                    f"{module} imports private module {target} (a testbed no module may depend on)",
                )
            )
    return out


def forbidden_violations(
    graph: Graph, forbidden: tuple[tuple[str, str], ...]
) -> list[ArchViolation]:
    """Declared ``A ↛ B`` edges that the graph violates."""
    out: list[ArchViolation] = []
    for importer, target in forbidden:
        if target in graph.get(importer, set()):
            out.append(ArchViolation("forbidden", f"{importer} must not import {target}"))
    return out


def find_cycles(graph: Graph) -> list[list[str]]:
    """Return distinct import cycles (each as a node list) via DFS back-edges.
    Distinct-by-node-set (``setdefault``), so a cycle reached twice is reported
    once without a hard-to-exercise dedup branch."""
    color: dict[str, int] = {}  # 1 = on stack (gray), 2 = done (black)
    stack: list[str] = []
    found: dict[frozenset[str], list[str]] = {}

    def visit(node: str) -> None:
        color[node] = 1
        stack.append(node)
        for nxt in sorted(graph.get(node, set())):
            if nxt not in graph:
                continue  # external module — not part of the internal graph
            if color.get(nxt) == 1:
                cycle = stack[stack.index(nxt) :]
                found.setdefault(frozenset(cycle), cycle)
            elif nxt not in color:
                visit(nxt)
        color[node] = 2
        stack.pop()

    for node in sorted(graph):
        if node not in color:
            visit(node)
    return list(found.values())


def cycle_violations(graph: Graph) -> list[ArchViolation]:
    """Import cycles in ``graph`` rendered as violations."""
    return [ArchViolation("cycle", " -> ".join([*cycle, cycle[0]])) for cycle in find_cycles(graph)]


def evaluate(
    graph: Graph,
    *,
    leaves: tuple[str, ...] = (),
    private: tuple[str, ...] = (),
    forbidden: tuple[tuple[str, str], ...] = (),
    forbid_cycles: bool = False,
) -> ArchReport:
    """Evaluate all declared contracts against ``graph``; fail-closed on any violation."""
    violations: list[ArchViolation] = []
    violations += leaf_violations(graph, leaves)
    violations += private_violations(graph, private)
    violations += forbidden_violations(graph, forbidden)
    if forbid_cycles:
        violations += cycle_violations(graph)
    return ArchReport(ok=not violations, violations=tuple(violations))
