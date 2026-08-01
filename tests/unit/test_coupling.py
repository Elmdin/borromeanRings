"""Coupling metrics + worst-fan-out ratchet. ADR-0038."""

from pathlib import Path

from meta_harness.coupling import fan_in, fan_out, worst_fan_out


def test_fan_out_counts_imports() -> None:
    graph = {"a": {"b", "c"}, "b": {"c"}, "c": set()}
    assert fan_out(graph) == {"a": 2, "b": 1, "c": 0}


def test_fan_in_counts_importers() -> None:
    graph = {"a": {"c"}, "b": {"c"}, "c": set()}
    assert fan_in(graph) == {"a": 0, "b": 0, "c": 2}


def test_fan_in_ignores_external_targets() -> None:
    graph = {"a": {"b", "stdlib"}, "b": set()}  # 'stdlib' not a node
    assert fan_in(graph) == {"a": 0, "b": 1}


def test_worst_fan_out_over_package(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "leaf.py").write_text("X = 1\n")
    (pkg / "mid.py").write_text("from pkg.leaf import X\n")
    (pkg / "god.py").write_text("from pkg.leaf import X\nimport pkg.mid\n")  # fan-out 2
    value, name = worst_fan_out(tmp_path, "pkg")
    assert value == 2
    assert name == "god"


def test_worst_fan_out_empty_package(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    assert worst_fan_out(tmp_path, "pkg") == (0, "")
