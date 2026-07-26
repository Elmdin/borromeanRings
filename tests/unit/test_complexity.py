"""Cyclomatic-complexity measurement (ratcheted by 32_complexity). ADR-0031."""

from pathlib import Path

from meta_harness.complexity import function_complexities, worst_complexity


def test_straight_line_is_one() -> None:
    assert function_complexities("def f():\n    return 1\n") == {"f": 1}


def test_each_branch_adds_one() -> None:
    src = (
        "def f(x):\n"
        "    if x:\n"  # +1
        "        return 1\n"
        "    for _ in range(x):\n"  # +1
        "        pass\n"
        "    while x:\n"  # +1
        "        break\n"
        "    return x\n"
    )
    assert function_complexities(src)["f"] == 4  # 1 + 3


def test_boolean_operators_add_per_extra_operand() -> None:
    # `a and b and c` = 2 extra decision points
    assert function_complexities("def f(a, b, c):\n    return a and b and c\n")["f"] == 3


def test_ternary_and_comprehension_if() -> None:
    src = "def f(xs):\n    return [x for x in xs if x] or (1 if xs else 0)\n"
    # comprehension `if` (+1) + ternary IfExp (+1) + `or` (+1) = 4
    assert function_complexities(src)["f"] == 4


def test_except_and_assert() -> None:
    src = (
        "def f():\n"
        "    try:\n"
        "        assert True\n"  # +1
        "    except ValueError:\n"  # +1
        "        pass\n"
        "    except KeyError:\n"  # +1
        "        pass\n"
    )
    assert function_complexities(src)["f"] == 4


def test_match_counts_cases() -> None:
    src = (
        "def f(x):\n"
        "    match x:\n"
        "        case 1:\n"  # +1
        "            return 1\n"
        "        case _:\n"  # +1
        "            return 0\n"
    )
    assert function_complexities(src)["f"] == 3  # 1 + 2 cases


def test_nested_functions_measured_separately() -> None:
    src = (
        "def outer(x):\n"
        "    if x:\n"  # outer +1 -> 2
        "        pass\n"
        "    def inner(y):\n"
        "        return 1 if y else 0\n"  # inner ternary -> 2
        "    return inner\n"
    )
    c = function_complexities(src)
    assert c["outer"] == 2  # nested inner's branch NOT counted in outer
    assert c["outer.inner"] == 2


def test_methods_qualified_by_class() -> None:
    src = "class C:\n    def m(self, x):\n        return 1 if x else 0\n"
    assert function_complexities(src) == {"C.m": 2}


def test_worst_complexity_over_package(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "a.py").write_text("def simple():\n    return 1\n")
    # `also_simple` (complexity 1) after `branchy` exercises the not-greater path
    (pkg / "b.py").write_text(
        "def branchy(x):\n    return 1 if x else (2 if x else 3)\n"
        "def also_simple():\n    return 0\n"
    )
    value, name = worst_complexity(tmp_path, "pkg")
    assert value == 3
    assert name == "b.py::branchy"


def test_empty_package_is_zero(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    assert worst_complexity(tmp_path, "pkg") == (0, "")
