"""Doc-drift critic: pure extraction + judge aggregation, and the live-command
adapter. Judges are stubbed (no model/network). See meta_harness/doc_drift.py."""

from meta_harness.critic import make_rubric_judge
from meta_harness.doc_drift import (
    DocTarget,
    command_ask,
    evaluate_doc_drift,
    extract_targets,
)

_SRC = (
    '"""Module."""\n'
    "def public(x):\n"
    '    """Add one."""\n'
    "    return x + 1\n"
    "def _private():\n"  # excluded: private
    "    return 0\n"
    "def undocumented():\n"  # excluded: no docstring (ratchet's job, not drift)
    "    return 1\n"
    "class C:\n"
    '    """A class."""\n'
    "    def method(self):\n"
    '        """Does a thing."""\n'
    "        def inner():\n"  # excluded: nested
    '            """nested"""\n'
    "            return 2\n"
    "        return inner\n"
)


def test_extract_targets_only_documented_public_functions() -> None:
    names = [t.qualname for t in extract_targets(_SRC)]
    assert names == ["public", "C.method"]


def test_extract_targets_carries_source_segment() -> None:
    target = next(t for t in extract_targets(_SRC) if t.qualname == "public")
    assert isinstance(target, DocTarget)
    assert "def public(x):" in target.artifact
    assert "Add one" in target.artifact


def test_evaluate_advisory_records_verdicts_without_gating() -> None:
    # A judge that flags everything as drift; advisory (required=False) => report
    # passes (nothing required) but each verdict records the failure.
    judge = make_rubric_judge(lambda prompt: "no, the docstring is stale")
    report = evaluate_doc_drift(_SRC, judge)
    assert report.passed is True  # advisory: no required criteria
    assert [v.criterion_id for v in report.verdicts] == ["public", "C.method"]
    assert all(v.passed is False for v in report.verdicts)


def test_evaluate_required_gates_on_drift() -> None:
    judge = make_rubric_judge(lambda prompt: "no")
    report = evaluate_doc_drift(_SRC, judge, required=True)
    assert report.passed is False
    assert {v.criterion_id for v in report.failures} == {"public", "C.method"}


def test_evaluate_passes_when_judge_affirms() -> None:
    judge = make_rubric_judge(lambda prompt: "yes, matches")
    report = evaluate_doc_drift(_SRC, judge, required=True)
    assert report.passed is True


def test_judge_error_is_fail_closed() -> None:
    def boom(question: str, artifact: str) -> tuple[bool, str]:
        raise RuntimeError("model down")

    report = evaluate_doc_drift(_SRC, boom, required=True)
    assert report.passed is False
    assert all("judge error" in v.rationale for v in report.verdicts)


def test_no_targets_passes_vacuously() -> None:
    report = evaluate_doc_drift('"""Only a module docstring."""\n', lambda q, a: (False, ""))
    assert report.verdicts == ()
    assert report.passed is True


def test_command_ask_runs_command_and_returns_stdout() -> None:
    ask = command_ask("python3 -c \"import sys; sys.stdout.write('yes: ' + sys.stdin.read())\"")
    assert ask("looks fine").strip() == "yes: looks fine"


def test_command_ask_composes_into_a_live_judge() -> None:
    # A fake 'model' command that always answers yes -> criterion passes.
    judge = make_rubric_judge(command_ask("python3 -c \"print('yes ok')\""))
    passed, rationale = judge("does it match?", "def f(): ...")
    assert passed is True
    assert rationale.startswith("yes")
