"""The rest of the Wave-2 critic family, as a registry of rubrics over the same
doc-drift machinery (extract functions → judge each against a question).

Each rubric is the *same* mechanism as doc-drift — a model judge external to the
generator, fail-closed, advisory until wired — differing only in its **question**
and **scope** (source functions vs test functions). One module, many rubrics
(Single Choice), so a new semantic check is a data entry, not new plumbing.

All advisory: run and report, never gate, until a judge command is configured
and the check is deliberately promoted. See docs/specs/SPEC-critic-rubrics.md and
ADR-0036.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

from meta_harness.critic import (
    Criterion,
    CriterionVerdict,
    CriticJudge,
    CriticReport,
    evaluate_rubric,
)
from meta_harness.doc_drift import DocTarget

_Func = (ast.FunctionDef, ast.AsyncFunctionDef)


@dataclass(frozen=True)
class Rubric:
    """One semantic question and the scope of functions it judges."""

    id: str
    question: str
    scope: str  # "src" (public functions) | "tests" (test_* functions)


RUBRICS: dict[str, Rubric] = {
    "error_handling": Rubric(
        "error_handling",
        "Does this function handle errors properly — no bare 'except:', no silently "
        "swallowed exceptions, failures surfaced rather than hidden? Answer 'no' if it "
        "swallows or mishandles errors.",
        "src",
    ),
    "naming": Rubric(
        "naming",
        "Are this function's name and its parameter names clear, accurate, and "
        "unambiguous for what it does? Answer 'no' for misleading or cryptic names.",
        "src",
    ),
    "security": Rubric(
        "security",
        "Does this function have a security flaw — command/SQL injection, unsafe "
        "eval/exec, shell=True on untrusted input, path traversal, or unvalidated "
        "external input? Answer 'no' if it is safe.",
        "src",
    ),
    "boundary_value": Rubric(
        "boundary_value",
        "Does this function handle boundary and edge cases for its inputs (empty, "
        "zero, negative, very large, None)? Answer 'no' if an obvious edge case is "
        "unhandled.",
        "src",
    ),
    "test_smell": Rubric(
        "test_smell",
        "Is this test meaningful — does it assert real behavior? Answer 'no' if it is "
        "vacuous (no assertion, asserts a constant, or so over-mocked it tests "
        "nothing).",
        "tests",
    ),
}


def extract_functions(source: str, *, tests_only: bool = False) -> list[DocTarget]:
    """Public functions/methods (or ``test_*`` when ``tests_only``) with their source.

    Descends into classes but not into functions (nested closures are excluded)."""
    targets: list[DocTarget] = []

    def wanted(name: str) -> bool:
        return name.startswith("test_") if tests_only else not name.startswith("_")

    def visit(body: list[ast.stmt], prefix: str) -> None:
        for node in body:
            if isinstance(node, _Func) and wanted(node.name):
                segment = ast.get_source_segment(source, node) or ""
                targets.append(DocTarget(prefix + node.name, segment))
            elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                visit(node.body, f"{prefix}{node.name}.")

    visit(ast.parse(source).body, "")
    return targets


def run_rubric(
    source: str, rubric: Rubric, judge: CriticJudge, *, required: bool = False
) -> CriticReport:
    """Judge every in-scope function in ``source`` against ``rubric``'s question."""
    verdicts: list[CriterionVerdict] = []
    for target in extract_functions(source, tests_only=rubric.scope == "tests"):
        report = evaluate_rubric(
            target.artifact,
            (
                Criterion(
                    id=f"{rubric.id}:{target.qualname}",
                    question=rubric.question,
                    required=required,
                ),
            ),
            judge,
        )
        verdicts.extend(report.verdicts)
    return CriticReport(verdicts=tuple(verdicts))
