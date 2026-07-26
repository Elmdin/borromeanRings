"""Tests for the T2 external rubric-critic seam (docs/specs/SPEC-critic.md, ADR-0023).

The whole mechanism is exercised with stub judges — no model, deterministic
(QAS C-4). Fail-closed aggregation is the point: unsure/errored judgments fail.
"""

from meta_harness.critic import (
    Criterion,
    CriterionVerdict,
    CriticReport,
    evaluate_rubric,
    make_rubric_judge,
    render_report,
)

_RUBRIC = (
    Criterion(id="does_task", question="Does the change do what the task asked?"),
    Criterion(id="named_well", question="Are the names clear?"),
)


def _yes(_q: str, _a: str) -> tuple[bool, str]:
    return True, "looks right"


def _no(_q: str, _a: str) -> tuple[bool, str]:
    return False, "does not"


def test_passes_when_all_required_criteria_pass() -> None:
    report = evaluate_rubric("artifact", _RUBRIC, _yes)
    assert report.passed is True
    assert report.failures == ()
    assert len(report.verdicts) == 2


def test_fails_closed_when_a_required_criterion_fails() -> None:
    # first criterion fails, second passes → overall fails (all-required rule).
    def judge(question: str, artifact: str) -> tuple[bool, str]:
        return (question != _RUBRIC[0].question, "judged")

    report = evaluate_rubric("artifact", _RUBRIC, judge)
    assert report.passed is False
    assert [v.criterion_id for v in report.failures] == ["does_task"]


def test_advisory_criterion_failure_does_not_block() -> None:
    rubric = (
        Criterion(id="req", question="required?"),
        Criterion(id="adv", question="advisory?", required=False),
    )

    def judge(question: str, _a: str) -> tuple[bool, str]:
        return (question == "required?", "j")  # advisory fails, required passes

    report = evaluate_rubric("x", rubric, judge)
    assert report.passed is True  # advisory failure is reported, not blocking
    assert report.failures == ()  # failures lists only required failures
    assert any(not v.passed and not v.required for v in report.verdicts)  # advisory recorded


def test_judge_that_raises_is_failed_closed() -> None:
    def boom(_q: str, _a: str) -> tuple[bool, str]:
        raise RuntimeError("model timeout")

    report = evaluate_rubric("x", (Criterion(id="c", question="q?"),), boom)
    assert report.passed is False
    assert "judge error" in report.verdicts[0].rationale
    assert "model timeout" in report.verdicts[0].rationale


def test_empty_rubric_is_vacuously_passed() -> None:
    report = evaluate_rubric("x", (), _no)
    assert report.passed is True
    assert report.verdicts == ()


def test_make_rubric_judge_passes_only_on_explicit_yes() -> None:
    judge = make_rubric_judge(lambda prompt: "yes — the change matches the task")
    passed, rationale = judge("does it?", "artifact")
    assert passed is True
    assert "matches the task" in rationale


def test_make_rubric_judge_is_fail_closed_on_non_affirmative() -> None:
    for answer in ("no, it regresses X", "I'm not sure", ""):
        judge = make_rubric_judge(lambda prompt, a=answer: a)
        passed, _ = judge("q?", "art")
        assert passed is False


def test_report_and_verdict_types_are_public() -> None:
    verdict = CriterionVerdict(criterion_id="c", passed=True, rationale="r", required=True)
    report = CriticReport(verdicts=(verdict,))
    assert report.passed is True


def test_render_report_shows_pass_fail_and_rationales() -> None:
    passing = render_report(evaluate_rubric("x", (Criterion("c", "q?"),), _yes))
    assert passing.startswith("critic: PASS")
    assert "[ok] c" in passing

    failing = render_report(
        evaluate_rubric("x", (Criterion("c", "q?"), Criterion("a", "q?", required=False)), _no)
    )
    assert failing.startswith("critic: FAIL")
    assert "[XX] c" in failing
    assert "(advisory)" in failing
