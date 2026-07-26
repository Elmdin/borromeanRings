"""Doc-drift: the first concrete application of the T2 critic seam.

Docstrings rot silently — the `45_docstrings` ratchet enforces that public
definitions *have* a docstring, but nothing checks the docstring still tells the
truth. That is a *semantic* question no mechanical check can answer, so it is
judged by a model **external to the generator** via :mod:`meta_harness.critic`.

Two layers, split for testability and to keep the gate deterministic:

  - **Pure core** (:func:`extract_targets`, :func:`evaluate_doc_drift`): find every
    documented public function/method and ask the injected judge whether its
    docstring matches its code. Unit-tested with stub judges — no model, no
    network.
  - **Live-judge adapter** (:func:`command_ask`): turn an operator-declared model
    command into the ``ask`` a :func:`meta_harness.critic.make_rubric_judge` needs.
    The command is the module secret (which model, how) — borromeanRings owns only
    the rubric and aggregation.

Advisory-first: the check reports drift but does not gate until the model judge
is trusted (SPEC-critic.md §7). See docs/specs/SPEC-doc-drift.md and ADR-0030.
"""

from __future__ import annotations

import ast
import shlex
import subprocess  # nosec B404 — used only to run the operator-declared, trusted judge command
from collections.abc import Callable
from dataclasses import dataclass

from meta_harness.critic import (
    Criterion,
    CriterionVerdict,
    CriticJudge,
    CriticReport,
    evaluate_rubric,
)

DRIFT_QUESTION = (
    "Does the docstring accurately and completely describe what this function does "
    "— its parameters, return value, and behavior? Answer 'no' if the docstring is "
    "stale, wrong, or misleading relative to the code."
)

_Func = (ast.FunctionDef, ast.AsyncFunctionDef)


@dataclass(frozen=True)
class DocTarget:
    """A documented public function/method and its source (the judge's artifact)."""

    qualname: str
    artifact: str


def extract_targets(source: str) -> list[DocTarget]:
    """Documented public functions/methods in ``source`` (only these can drift).

    Descends into classes (for methods) but not into functions (inner closures are
    not public API). Undocumented defs are the docstring ratchet's job, not drift's.
    """
    tree = ast.parse(source)
    targets: list[DocTarget] = []

    def visit(body: list[ast.stmt], prefix: str) -> None:
        for node in body:
            if isinstance(node, _Func) and not node.name.startswith("_"):
                if ast.get_docstring(node) is not None:
                    segment = ast.get_source_segment(source, node) or ""
                    targets.append(DocTarget(prefix + node.name, segment))
            elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                visit(node.body, f"{prefix}{node.name}.")

    visit(tree.body, "")
    return targets


def evaluate_doc_drift(source: str, judge: CriticJudge, *, required: bool = False) -> CriticReport:
    """Judge every documented public function in ``source`` for docstring drift.

    Each function is its own artifact judged against the single drift question;
    ``required=False`` (the default) makes every verdict advisory (reported, never
    gating) — the deliberate first posture for a model-backed check.
    """
    verdicts: list[CriterionVerdict] = []
    for target in extract_targets(source):
        report = evaluate_rubric(
            target.artifact,
            (Criterion(id=target.qualname, question=DRIFT_QUESTION, required=required),),
            judge,
        )
        verdicts.extend(report.verdicts)
    return CriticReport(verdicts=tuple(verdicts))


def command_ask(command: str, *, timeout: float = 60.0) -> Callable[[str], str]:
    """Adapter: turn an operator-declared ``command`` into an ``ask(prompt)->answer``.

    The command (from trusted repo config — ``[critic].judge_command``) receives the
    prompt on stdin and returns its answer on stdout. Compose with
    :func:`meta_harness.critic.make_rubric_judge` for a live, fail-closed model
    judge. A crashed/timed-out command raises, which ``evaluate_rubric`` catches as
    a failed (fail-closed) criterion.
    """
    argv = shlex.split(command)

    def ask(prompt: str) -> str:
        completed = subprocess.run(  # nosec B603 — argv is trusted [critic].judge_command config, not external input
            argv,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return completed.stdout

    return ask
