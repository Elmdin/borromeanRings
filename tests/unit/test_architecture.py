"""Architectural fitness contracts over the internal import graph.

Analysis is pure (synthetic graphs in, violations out); the builder is exercised
on a tiny package written to tmp. See meta_harness/architecture.py, ADR-0027.
"""

from pathlib import Path

from meta_harness.architecture import (
    ArchReport,
    build_import_graph,
    cycle_violations,
    evaluate,
    find_cycles,
    forbidden_violations,
    leaf_violations,
    private_violations,
)


def test_leaf_violation_flagged() -> None:
    graph = {"spine": {"hygiene"}, "hygiene": set()}
    out = leaf_violations(graph, ("spine",))
    assert len(out) == 1
    assert out[0].kind == "leaf"
    assert "hygiene" in out[0].detail


def test_leaf_clean() -> None:
    graph = {"spine": set(), "change_detect": {"spine"}}
    assert leaf_violations(graph, ("spine",)) == []


def test_private_violation_flagged() -> None:
    graph = {"core": {"deep_research"}, "deep_research": set()}
    out = private_violations(graph, ("deep_research",))
    assert len(out) == 1
    assert out[0].kind == "private"


def test_private_module_may_import_others() -> None:
    # A private module depending on siblings is fine; only being depended ON is not.
    graph = {"deep_research": {"ratchet"}, "ratchet": set()}
    assert private_violations(graph, ("deep_research",)) == []


def test_forbidden_edge_flagged() -> None:
    graph = {"a": {"b"}, "b": set()}
    assert forbidden_violations(graph, (("a", "b"),))[0].kind == "forbidden"
    assert forbidden_violations(graph, (("b", "a"),)) == []


def test_find_cycles_detects_a_cycle() -> None:
    graph = {"a": {"b"}, "b": {"c"}, "c": {"a"}}
    cycles = find_cycles(graph)
    assert len(cycles) == 1
    assert set(cycles[0]) == {"a", "b", "c"}


def test_find_cycles_self_loop() -> None:
    assert find_cycles({"a": {"a"}}) == [["a"]]


def test_dag_has_no_cycles() -> None:
    graph = {"a": {"b"}, "b": {"c"}, "c": set()}
    assert find_cycles(graph) == []
    assert cycle_violations(graph) == []


def test_diamond_dag_revisits_black_node_without_cycle() -> None:
    # a -> b -> c and a -> c: `c` is already finished when reached the 2nd time.
    graph = {"a": {"b", "c"}, "b": {"c"}, "c": set()}
    assert find_cycles(graph) == []


def test_evaluate_without_forbid_cycles() -> None:
    # A graph that *has* a cycle passes when forbid_cycles is off.
    graph = {"a": {"b"}, "b": {"a"}}
    assert evaluate(graph, forbid_cycles=False).ok


def test_external_imports_are_ignored_by_cycle_search() -> None:
    # References to modules outside the graph must not crash or count as edges.
    graph = {"a": {"b", "stdlib_thing"}, "b": set()}
    assert find_cycles(graph) == []


def test_evaluate_aggregates_and_is_ok_when_clean() -> None:
    graph = {"spine": set(), "change_detect": {"spine"}, "deep_research": set()}
    report = evaluate(
        graph,
        leaves=("spine",),
        private=("deep_research",),
        forbid_cycles=True,
    )
    assert isinstance(report, ArchReport)
    assert report.ok
    assert report.violations == ()


def test_evaluate_reports_all_violation_kinds() -> None:
    graph = {"spine": {"x"}, "x": {"spine"}, "core": {"deep_research"}, "deep_research": set()}
    report = evaluate(
        graph,
        leaves=("spine",),
        private=("deep_research",),
        forbidden=(("x", "spine"),),
        forbid_cycles=True,
    )
    assert not report.ok
    kinds = {v.kind for v in report.violations}
    assert kinds == {"leaf", "private", "forbidden", "cycle"}


def test_build_import_graph_reads_real_imports(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "spine.py").write_text("VALUE = 1\n")
    # every import shape + a few that must be IGNORED (external, non-sibling, future)
    (pkg / "abs_from.py").write_text("from pkg.spine import VALUE\n")
    (pkg / "rel_bare.py").write_text("from . import spine\n")  # from . import x
    (pkg / "rel_mod.py").write_text("from .spine import VALUE\n")  # from .sub import x
    (pkg / "plain_import.py").write_text("import pkg.spine\n")
    (pkg / "noise.py").write_text(
        "from __future__ import annotations\n"  # absolute, not the package
        "import os\n"  # plain external
        "from pkg.ghost import X\n"  # package prefix but not a real module
        "x = 1\n"  # a non-import node
    )
    graph = build_import_graph(tmp_path, "pkg")
    assert graph["spine"] == set()
    assert graph["abs_from"] == {"spine"}
    assert graph["rel_bare"] == {"spine"}
    assert graph["rel_mod"] == {"spine"}
    assert graph["plain_import"] == {"spine"}
    assert graph["noise"] == set()  # os / __future__ / pkg.ghost all filtered out
    assert "__init__" not in graph
