"""API-usage contracts — a project's own API rules as deterministic, binary AST checks.

When a project targets a specific API (a HAL, a driver, an SDK, a library with usage
rules), the rules are usually enforced by reminding the agent every session. This
module makes them gate-enforceable: declarative rules over call sites, evaluated with
the stdlib ``ast`` — no LLM, no thresholds, fail closed on anything unreadable. It is
:mod:`meta_harness.architecture` (import-direction invariants) generalised to a second
family of predicates. See docs/specs/SPEC-api-contracts.md and ADR-0054 (#130).

Honest limits: Python only (C/C++ is the ``ast-grep`` path recorded in the ADR);
``paired`` / ``requires_before`` are per-function, lexical and statement-ordered — the
conservative reading, documented on the rule.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

import tomllib

#: ``forbidden_in`` scope token meaning "any ``async def``" (a coroutine body).
ASYNC_SCOPE = "<async>"

#: Rule kinds and the extra field each requires beyond ``symbol``.
KINDS: dict[str, str | None] = {
    "banned": None,
    "forbidden_in": "within",
    "must_check": None,
    "required_arg": "arg",
    "paired": "pair",
    "requires_before": "before",
}


@dataclass(frozen=True)
class Rule:
    """One declarative API-usage rule (immutable)."""

    kind: str
    symbol: str
    target: str = ""  # the kind-specific field: within / arg / pair / before
    message: str = ""
    source: str = ""  # provenance (URL or document section); required in packs

    def describe(self) -> str:
        """One line naming the rule for a violation report."""
        extra = f" {KINDS[self.kind]}={self.target}" if KINDS[self.kind] else ""
        return f"[{self.kind}] {self.symbol}{extra}"


@dataclass(frozen=True)
class Violation:
    """One rule broken at one call site."""

    rule: Rule
    path: str
    line: int
    message: str


@dataclass(frozen=True)
class Report:
    """Violations found plus how many call sites matched ANY rule's symbol.

    ``references == 0`` with rules declared means the rules inspected nothing — the
    gate reports ``noop``, never ``pass`` (ADR-0049).
    """

    violations: tuple[Violation, ...] = ()
    references: int = 0


def parse_rules(raw: Sequence[Mapping[str, object]]) -> tuple[Rule, ...]:
    """Validate raw rule tables into :class:`Rule`s; fail closed on any malformed rule."""
    rules: list[Rule] = []
    for entry in raw:
        kind = str(entry.get("kind", ""))
        if kind not in KINDS:
            raise ValueError(f"unknown rule kind {kind!r}; expected one of {sorted(KINDS)}")
        symbol = str(entry.get("symbol", ""))
        if not symbol:
            raise ValueError(f"rule of kind {kind!r} is missing 'symbol'")
        field = KINDS[kind]
        target = str(entry.get(field, "")) if field else ""
        if field and not target:
            raise ValueError(f"rule {kind!r} on {symbol!r} is missing '{field}'")
        rules.append(
            Rule(
                kind=kind,
                symbol=symbol,
                target=target,
                message=str(entry.get("message", "")),
                source=str(entry.get("source", "")),
            )
        )
    return tuple(rules)


def load_pack(name: str, packs_dir: Path | str) -> tuple[Rule, ...]:
    """Rules from ``<packs_dir>/<name>.toml``; every pack rule must cite a ``source``."""
    path = Path(packs_dir) / f"{name}.toml"
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    rules = parse_rules(raw.get("rules", []))
    for rule in rules:
        if not rule.source:
            raise ValueError(f"pack {name!r}: rule {rule.describe()} has no 'source' (provenance)")
    return rules


# --- AST evaluation -------------------------------------------------------------------------


def _dotted(node: ast.AST) -> str | None:
    """``a.b.c`` for a Name/Attribute chain; ``None`` for anything else."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else None
    return None


def _matches(rule: Rule, name: str) -> bool:
    """Does the call name match the rule's symbol glob (case-sensitive)?"""
    return fnmatchcase(name, rule.symbol)


@dataclass(frozen=True)
class _Call:
    """A call site with the lexical context the rules need."""

    name: str
    node: ast.Call
    discarded: bool  # the call is a bare expression statement
    function: str  # enclosing function name ("" at module level)
    order: int  # statement order within the enclosing function body
    is_async: bool = False  # enclosing function is ``async def``


def _calls_in_statement(
    stmt: ast.stmt, ctx: tuple[str, int, bool], discarded: set[int]
) -> list[_Call]:
    """Call sites in one statement, excluding nested definitions (visited separately)."""
    function, order, is_async = ctx
    out: list[_Call] = []
    for node in ast.walk(stmt):
        if isinstance(node, ast.Call):
            name = _dotted(node.func)
            if name is not None:
                out.append(_Call(name, node, id(node) in discarded, function, order, is_async))
    return out


def _nested_defs(stmt: ast.stmt) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Function definitions nested anywhere inside ``stmt`` (blocks, with, try, ...)."""
    return [
        node
        for node in ast.walk(stmt)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node is not stmt
    ]


def _calls(tree: ast.Module) -> list[_Call]:
    """Every call site with the context the rules need, in source order."""
    found: list[_Call] = []
    discarded = {
        id(stmt.value)
        for stmt in ast.walk(tree)
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)
    }

    def visit(body: Iterable[ast.stmt], function: str, is_async: bool = False) -> None:
        for order, stmt in enumerate(body):
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(stmt.body, stmt.name, isinstance(stmt, ast.AsyncFunctionDef))
            elif isinstance(stmt, ast.ClassDef):
                visit(stmt.body, function, is_async)
            else:
                found.extend(_calls_in_statement(stmt, (function, order, is_async), discarded))
                for node in _nested_defs(stmt):
                    visit(node.body, node.name, isinstance(node, ast.AsyncFunctionDef))

    visit(tree.body, "")
    return found


def _banned(rule: Rule, call: _Call) -> str | None:
    """``banned``: any call is a violation."""
    return rule.message or f"{call.name} is banned"


def _forbidden_in(rule: Rule, call: _Call) -> str | None:
    """``forbidden_in``: a call inside a function matching ``within`` (or any coroutine)."""
    in_scope = (
        call.is_async if rule.target == ASYNC_SCOPE else fnmatchcase(call.function, rule.target)
    )
    if call.function and in_scope:
        return rule.message or f"{call.name} must not be called in {call.function}"
    return None


def _must_check(rule: Rule, call: _Call) -> str | None:
    """``must_check``: the call's value may not be discarded."""
    if call.discarded:
        return rule.message or f"the result of {call.name} must not be discarded"
    return None


def _required_arg(rule: Rule, call: _Call) -> str | None:
    """``required_arg``: the call must pass the keyword argument."""
    if any(kw.arg == rule.target for kw in call.node.keywords):
        return None
    return rule.message or f"{call.name} must pass {rule.target}="


#: Rules decided at a single call site: kind -> predicate returning the violation message.
_SITE_RULES: dict[str, Callable[[Rule, _Call], str | None]] = {
    "banned": _banned,
    "forbidden_in": _forbidden_in,
    "must_check": _must_check,
    "required_arg": _required_arg,
}


def _by_function(calls: Sequence[_Call]) -> dict[str, list[_Call]]:
    """Call sites grouped by enclosing function (module level excluded: no scope)."""
    groups: dict[str, list[_Call]] = {}
    for call in calls:
        if call.function:
            groups.setdefault(call.function, []).append(call)
    return groups


def _paired_missing(rule: Rule, subject: _Call, partners: Sequence[_Call]) -> str | None:
    """``paired``: the subject's function body must call the partner somewhere."""
    if partners:
        return None
    return rule.message or f"{subject.name} in {subject.function} has no matching {rule.target}"


def _before_missing(rule: Rule, subject: _Call, partners: Sequence[_Call]) -> str | None:
    """``requires_before``: a partner call must precede the subject in statement order."""
    if any(p.order < subject.order for p in partners):
        return None
    return rule.message or f"{subject.name} in {subject.function} is not preceded by {rule.target}"


#: Rules decided per enclosing function body: kind -> predicate over (subject, partners).
_SCOPE_RULES: dict[str, Callable[[Rule, _Call, Sequence[_Call]], str | None]] = {
    "paired": _paired_missing,
    "requires_before": _before_missing,
}


def _scope_violations(rule: Rule, calls: Sequence[_Call], path: str) -> list[Violation]:
    """Evaluate a scope rule over every function body (lexical, statement-ordered)."""
    decide = _SCOPE_RULES[rule.kind]
    out: list[Violation] = []
    for mine in (group for _, group in sorted(_by_function(calls).items())):
        partners = [c for c in mine if fnmatchcase(c.name, rule.target)]
        for subject in (c for c in mine if _matches(rule, c.name)):
            message = decide(rule, subject, partners)
            if message is not None:
                out.append(Violation(rule, path, subject.node.lineno, message))
    return out


def check_source(source: str, rules: Sequence[Rule], path: str = "") -> Report:
    """Evaluate ``rules`` over one file's source (pure)."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        rule = Rule("syntax", "*")
        return Report((Violation(rule, path, exc.lineno or 1, f"cannot parse: {exc.msg}"),), 0)
    calls = _calls(tree)
    references = sum(1 for c in calls if any(_matches(r, c.name) for r in rules))
    violations: list[Violation] = []
    for rule in rules:
        if rule.kind in _SCOPE_RULES:
            violations.extend(_scope_violations(rule, calls, path))
            continue
        decide = _SITE_RULES[rule.kind]
        for call in calls:
            if _matches(rule, call.name):
                message = decide(rule, call)
                if message is not None:
                    violations.append(Violation(rule, path, call.node.lineno, message))
    violations.sort(key=lambda v: (v.line, v.rule.kind))
    return Report(tuple(violations), references)


def check_tree(files: Iterable[Path | str], rules: Sequence[Rule]) -> Report:
    """Fold :func:`check_source` over ``files`` (read as UTF-8, errors replaced)."""
    violations: list[Violation] = []
    references = 0
    for file in files:
        p = Path(file)
        report = check_source(p.read_text(encoding="utf-8", errors="replace"), rules, str(p))
        violations.extend(report.violations)
        references += report.references
    return Report(tuple(violations), references)
