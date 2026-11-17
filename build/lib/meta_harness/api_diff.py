"""Public-API breaking-change detection.

A library's public surface is a contract with its consumers; removing a symbol,
renaming a parameter, or adding a required argument silently breaks them (matrix
row **D — public-API breaking-change detection**). This is only *justified* for a
project whose API others depend on — e.g. the ``examples/textkit`` library, not
the meta-harness itself (ADR-0039).

Two layers: a pure signature model (:func:`public_api`) and a pure diff
(:func:`breaking_changes`), both unit-tested from source text; the check script
supplies the "before" text from git. Native stdlib ``ast``; no external tool. See
docs/specs/SPEC-api-diff.md and ADR-0040.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

_Func = (ast.FunctionDef, ast.AsyncFunctionDef)


@dataclass(frozen=True)
class Signature:
    """A public symbol's shape: its kind, its parameter names, and how many are
    required (positional without a default). Enough to decide breakage."""

    kind: str  # "function" | "class"
    params: tuple[str, ...]
    required: int


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> Signature:
    args = node.args
    positional = [*args.posonlyargs, *args.args]
    params = [a.arg for a in positional]
    if args.vararg:
        params.append(f"*{args.vararg.arg}")
    params += [a.arg for a in args.kwonlyargs]
    if args.kwarg:
        params.append(f"**{args.kwarg.arg}")
    required = len(positional) - len(args.defaults)
    return Signature("function", tuple(params), required)


def public_api(source: str) -> dict[str, Signature]:
    """Public functions/methods/classes in ``source`` and their signatures.

    Public = name not starting with ``_``. Descends into classes (for methods)
    but not into functions (nested closures are not public API)."""
    api: dict[str, Signature] = {}

    def visit(body: list[ast.stmt], prefix: str) -> None:
        for node in body:
            if isinstance(node, _Func) and not node.name.startswith("_"):
                api[prefix + node.name] = _signature(node)
            elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                api[prefix + node.name] = Signature("class", (), 0)
                visit(node.body, f"{prefix}{node.name}.")

    visit(ast.parse(source).body, "")
    return api


def breaking_changes(old: dict[str, Signature], new: dict[str, Signature]) -> list[str]:
    """Backwards-incompatible changes from ``old`` to ``new`` (adding an optional
    parameter or a new symbol is NOT breaking)."""
    breaks: list[str] = []
    for name in sorted(old):
        if name not in new:
            breaks.append(f"removed: {name}")
            continue
        before, after = old[name], new[name]
        if before.kind != after.kind:
            breaks.append(f"{name}: kind changed ({before.kind} -> {after.kind})")
            continue
        if after.required > before.required:
            breaks.append(
                f"{name}: added required parameter(s) "
                f"(required {before.required} -> {after.required})"
            )
        gone = [p for p in before.params if p not in after.params]
        if gone:
            breaks.append(f"{name}: removed/renamed parameter(s): {', '.join(gone)}")
    return breaks
