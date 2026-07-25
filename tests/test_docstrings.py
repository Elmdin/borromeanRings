"""Docstring-coverage measurement (ratcheted by check 35... see ADR-0029)."""

from pathlib import Path

from meta_harness.docstrings import DocstringStats, analyze_source, measure_package


def test_coverage_fraction() -> None:
    assert DocstringStats(3, 4).coverage == 0.75
    assert DocstringStats(0, 0).coverage == 1.0  # nothing to document ⇒ full


def test_stats_add() -> None:
    assert (DocstringStats(1, 2) + DocstringStats(2, 3)) == DocstringStats(3, 5)


def test_module_docstring_counted() -> None:
    assert analyze_source('"""Module doc."""\n') == DocstringStats(1, 1)
    assert analyze_source("x = 1\n") == DocstringStats(0, 1)  # module undocumented


def test_public_function_and_class_counted() -> None:
    src = (
        '"""M."""\n'
        "def public():\n"
        '    """doc"""\n'
        "    return 1\n"
        "class Thing:\n"
        '    """doc"""\n'
        "    def method(self):\n"
        '        """doc"""\n'
        "        return 2\n"
    )
    # module + public + Thing + method = 4, all documented
    assert analyze_source(src) == DocstringStats(4, 4)


def test_private_and_dunder_names_excluded() -> None:
    src = (
        '"""M."""\n'
        "def _helper():\n"
        "    return 1\n"
        "class C:\n"
        '    """doc"""\n'
        "    def __init__(self):\n"
        "        self.x = 1\n"
    )
    # module (doc) + C (doc); _helper and __init__ are excluded ⇒ 2/2
    assert analyze_source(src) == DocstringStats(2, 2)


def test_nested_functions_are_excluded() -> None:
    # An inner closure inside a documented function is not public API surface.
    src = (
        '"""M."""\n'
        "def outer():\n"
        '    """doc"""\n'
        "    def inner(x):\n"  # nested — must NOT count
        "        return x\n"
        "    return inner\n"
    )
    # module + outer = 2/2 ; inner excluded
    assert analyze_source(src) == DocstringStats(2, 2)


def test_methods_and_nested_classes_counted() -> None:
    src = (
        '"""M."""\n'
        "class Outer:\n"
        '    """doc"""\n'
        "    def method(self):\n"
        '        """doc"""\n'
        "        return 1\n"
        "    class Inner:\n"  # nested class DOES count (still API surface)
        '        """doc"""\n'
    )
    # module + Outer + method + Inner = 4/4
    assert analyze_source(src) == DocstringStats(4, 4)


def test_undocumented_public_lowers_coverage() -> None:
    src = '"""M."""\ndef undocumented():\n    return 1\n'
    stats = analyze_source(src)
    assert stats == DocstringStats(1, 2)
    assert stats.coverage == 0.5


def test_measure_package_excludes_init(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")  # empty marker — must not count
    (pkg / "a.py").write_text('"""A."""\ndef f():\n    """d"""\n    return 1\n')
    (pkg / "b.py").write_text("x = 1\n")  # undocumented module, no defs
    stats = measure_package(tmp_path, "pkg")
    # a.py: module+f = 2/2 ; b.py: module = 0/1 ; __init__ excluded ⇒ 2/3
    assert stats == DocstringStats(2, 3)
