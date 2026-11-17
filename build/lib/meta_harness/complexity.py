"""Cyclomatic-complexity ratchet (native, McCabe).

The worst-case function complexity in the codebase may not *regress* past a
recorded baseline — a non-regression signal, not an arbitrary ceiling to game (in
keeping with the project's stance against number gates). A new branch-heavy
function that pushes the maximum up fails the gate until it is simplified (or the
baseline is deliberately raised).

Complexity = 1 + decision points (``if``/``for``/``while``/``except``/``with``/
``assert``/ternary/comprehension-``if``/boolean-operator/``match``-case). Measured
per function, **excluding nested defs** (each nested function is its own unit).
Native stdlib ``ast``; no external tool. See docs/specs/SPEC-complexity.md and
ADR-0031.
"""

from __future__ import annotations

import ast
from pathlib import Path

_Def = (ast.FunctionDef, ast.AsyncFunctionDef)
_DECISIONS = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.ExceptHandler,
    ast.With,
    ast.AsyncWith,
    ast.Assert,
    ast.IfExp,
    ast.comprehension,
)


def _complexity(func: ast.AST) -> int:
    """McCabe complexity of one function, not descending into nested defs."""
    complexity = 1
    stack = list(ast.iter_child_nodes(func))
    while stack:
        node = stack.pop()
        if isinstance(node, (*_Def, ast.ClassDef)):
            continue  # a nested scope is measured on its own
        if isinstance(node, _DECISIONS):
            complexity += 1
        elif isinstance(node, ast.BoolOp):
            complexity += len(node.values) - 1
        elif isinstance(node, ast.Match):
            complexity += len(node.cases)
        stack.extend(ast.iter_child_nodes(node))
    return complexity


def function_complexities(source: str) -> dict[str, int]:
    """Map every function/method qualname in ``source`` to its complexity."""
    result: dict[str, int] = {}

    def visit(body: list[ast.stmt], prefix: str) -> None:
        for node in body:
            if isinstance(node, _Def):
                result[prefix + node.name] = _complexity(node)
                visit(node.body, f"{prefix}{node.name}.")
            elif isinstance(node, ast.ClassDef):
                visit(node.body, f"{prefix}{node.name}.")

    visit(ast.parse(source).body, "")
    return result


def worst_complexity(src_root: Path | str, package: str) -> tuple[int, str]:
    """The highest function complexity across ``package`` and the function's name."""
    worst_value = 0
    worst_name = ""
    pkg_dir = Path(src_root) / package
    for path in sorted(pkg_dir.rglob("*.py")):
        for name, value in function_complexities(path.read_text(encoding="utf-8")).items():
            if value > worst_value:
                worst_value, worst_name = value, f"{path.name}::{name}"
    return worst_value, worst_name
