"""T2 **external rubric critic** — semantic judgment as a substrate-agnostic seam.

Every mechanical check verifies *form*; this seam verifies *intent* — does a change
do the right thing, is it well-named, does it match its requirements — against a
declared **rubric**, judged by a model that is **external to the generator**
(borromeanRings's founding principle, extended from mechanical checks to judgment).

Same shape as :mod:`meta_harness.deep_research`: a deterministic, fail-closed
harness around an **injected** judge. The volatile decision (which model, how many,
prompt wording) is a module secret behind :data:`CriticJudge`; borromeanRings owns the
rubric and the aggregation. So the mechanism is fully unit-testable with stub judges
(no network) and stays model-agnostic. Not wired to the deterministic gate yet — a
model-backed check lands later, advisory-first (SPEC-critic.md §7, ADR-0023).
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

# The injected semantic step: (rubric question, artifact) -> (passed, rationale).
# Performed by an LLM/agent (or a panel); borromeanRings structures + aggregates it.
CriticJudge = Callable[[str, str], tuple[bool, str]]


@dataclass(frozen=True)
class Criterion:
    """One yes/no rubric question. ``required`` criteria gate; advisory ones (
    ``required=False``) are reported but never block."""

    id: str
    question: str
    required: bool = True


@dataclass(frozen=True)
class CriterionVerdict:
    """The judgment for one criterion (auditable in the receipt)."""

    criterion_id: str
    passed: bool
    rationale: str
    required: bool


@dataclass(frozen=True)
class CriticReport:
    """The outcome of judging an artifact against a rubric.

    ``passed`` is fail-closed: true iff **every required** criterion passed (an
    empty rubric passes vacuously). ``failures`` lists only required criteria that
    failed — the ones that block.
    """

    verdicts: tuple[CriterionVerdict, ...]

    @property
    def passed(self) -> bool:
        """True iff every required criterion passed (fail-closed)."""
        return all(v.passed for v in self.verdicts if v.required)

    @property
    def failures(self) -> tuple[CriterionVerdict, ...]:
        """The required criteria that failed — the ones that block."""
        return tuple(v for v in self.verdicts if v.required and not v.passed)


def evaluate_rubric(artifact: str, rubric: Sequence[Criterion], judge: CriticJudge) -> CriticReport:
    """Judge ``artifact`` against each criterion, fail-closed.

    A judge that raises is caught and recorded as a **failed** criterion — a flaky
    model call must never pass a gate. Aggregation (all-required) is deterministic;
    only the per-criterion judgment is probabilistic.
    """
    verdicts: list[CriterionVerdict] = []
    for criterion in rubric:
        try:
            passed, rationale = judge(criterion.question, artifact)
        except Exception as exc:  # fail-closed: a judge error is a failed criterion
            passed, rationale = False, f"judge error: {exc}"
        verdicts.append(
            CriterionVerdict(
                criterion_id=criterion.id,
                passed=bool(passed),
                rationale=rationale,
                required=criterion.required,
            )
        )
    return CriticReport(verdicts=tuple(verdicts))


def make_rubric_judge(ask: Callable[[str], str]) -> CriticJudge:
    """Build a **fail-closed** judge from an ``ask(prompt) -> answer`` LLM/agent.

    Only an explicit affirmative ("yes …") passes; anything else — "no", "unsure",
    an empty or off-format answer — fails. Mirrors
    :func:`meta_harness.deep_research.make_entailment_judge`.
    """

    def judge(question: str, artifact: str) -> tuple[bool, str]:
        prompt = (
            "You are a strict reviewer. Answer the QUESTION about the ARTIFACT with "
            "'yes' or 'no' (if unsure, answer 'no'), then a brief reason.\n"
            f"QUESTION: {question}\nARTIFACT: {artifact}\nAnswer:"
        )
        response = ask(prompt).strip()
        return response.lower().startswith("y"), response

    return judge


def render_report(report: CriticReport) -> str:
    """Render a :class:`CriticReport` as human-readable pass/fail with rationales."""
    lines = [f"critic: {'PASS' if report.passed else 'FAIL'}"]
    for verdict in report.verdicts:
        mark = "ok" if verdict.passed else "XX"
        tag = "" if verdict.required else " (advisory)"
        lines.append(f"  [{mark}] {verdict.criterion_id}{tag}: {verdict.rationale}")
    return "\n".join(lines)
