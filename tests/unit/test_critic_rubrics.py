"""Wave-2 critic rubric family (advisory). Judges stubbed — no model. ADR-0036."""

from meta_harness.critic import make_rubric_judge
from meta_harness.critic_rubrics import RUBRICS, extract_functions, run_rubric

_SRC = (
    '"""M."""\n'
    "def public(x):\n"
    "    return x\n"
    "def _private():\n"  # excluded (src scope)
    "    return 0\n"
    "class C:\n"
    "    def method(self):\n"
    "        return 1\n"
)

_TESTS = (
    "def test_real():\n"
    "    assert compute() == 3\n"
    "def helper():\n"  # excluded (not test_*)
    "    return 1\n"
    "def test_vacuous():\n"
    "    assert True\n"
)


def test_registry_has_the_family() -> None:
    assert {"error_handling", "naming", "security", "boundary_value", "test_smell"} <= set(RUBRICS)
    assert RUBRICS["test_smell"].scope == "tests"
    assert RUBRICS["naming"].scope == "src"


def test_extract_src_functions_public_only() -> None:
    names = [t.qualname for t in extract_functions(_SRC)]
    assert names == ["public", "C.method"]  # _private excluded, nested none


def test_extract_test_functions() -> None:
    names = [t.qualname for t in extract_functions(_TESTS, tests_only=True)]
    assert names == ["test_real", "test_vacuous"]  # helper excluded


def test_run_rubric_advisory_records_without_gating() -> None:
    judge = make_rubric_judge(lambda prompt: "no, problem here")
    report = run_rubric(_SRC, RUBRICS["security"], judge)
    assert report.passed is True  # advisory: nothing required
    assert [v.criterion_id for v in report.verdicts] == ["security:public", "security:C.method"]
    assert all(not v.passed for v in report.verdicts)


def test_run_rubric_required_gates() -> None:
    judge = make_rubric_judge(lambda prompt: "no")
    report = run_rubric(_TESTS, RUBRICS["test_smell"], judge, required=True)
    assert report.passed is False
    assert {v.criterion_id for v in report.failures} == {
        "test_smell:test_real",
        "test_smell:test_vacuous",
    }


def test_run_rubric_passes_when_judge_affirms() -> None:
    judge = make_rubric_judge(lambda prompt: "yes, fine")
    assert run_rubric(_SRC, RUBRICS["naming"], judge, required=True).passed is True


def test_judge_error_is_fail_closed() -> None:
    def boom(question: str, artifact: str) -> tuple[bool, str]:
        raise RuntimeError("down")

    report = run_rubric(_SRC, RUBRICS["error_handling"], boom, required=True)
    assert report.passed is False
