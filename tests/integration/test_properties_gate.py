"""End-to-end: tier 1 of the verification ladder, run through the real gate.

The rule under test is binary and threshold-free (nothing is counted, ever), and it
has one sharp edge: a project that *declares* a property directory and puts nothing in
it must **fail**, not pass and not `noop`. A declaration is an affirmative claim, and a
claim with no evidence behind it is the vacuity ADR-0049 exists to catch — accepting it
would make the declaration free.

Each test drives the real ``verify.sh`` against a fixture project (built in tmp, never
committed) and asserts the end-to-end verdict *and* the receipt status, because "the
gate went green" and "this check actually looked at something" are different facts.

See docs/specs/SPEC-verification-ladder.md and ADR-0074.
"""

import json
import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
GATE_TIMEOUT_S = 180

# Only 27_properties is required, so it alone decides the verdict; the rest of the
# python lane runs and noops (the fixtures carry no source).
BASE_CONFIG = '[project]\nlanguage = "python"\nsrc_dir = "src"\n\n[hygiene]\nrequires = []\n\n'
REQUIRED = '[checks]\nrequired = ["27_properties"]\n\n'

# A property that holds for every input Hypothesis can find.
GOOD_PROPERTY = (
    "from hypothesis import given, strategies as st\n\n\n"
    "@given(st.lists(st.integers()))\n"
    "def test_sorted_is_a_sorted_permutation(xs):\n"
    "    out = sorted(xs)\n"
    "    assert out == sorted(out)\n"
    "    assert len(out) == len(xs)\n"
)
# A property that is false, and cheap for Hypothesis to falsify.
BAD_PROPERTY = (
    "from hypothesis import given, strategies as st\n\n\n"
    "@given(st.integers())\n"
    "def test_every_integer_is_positive(n):\n"
    "    assert n > 0\n"
)
# Stub that shadows the real Hypothesis for anything run from the project root: the
# runner-absent case, without uninstalling anything on the machine.
HYPOTHESIS_STUB = 'raise ImportError("hypothesis is not installed on this machine")\n'


def _project(root: Path, files: dict[str, str]) -> Path:
    """Materialize ``{relpath: content}`` under ``root`` and return it."""
    for rel, content in files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    return root


def _declaring(properties: str) -> str:
    return BASE_CONFIG + REQUIRED + f'[verification]\nproperties = "{properties}"\n'


def _run_gate(project: Path) -> tuple[int, str, str, str]:
    """Run the real gate; return (exit code, stdout, 27_properties status, its log)."""
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(project)
    proc = subprocess.run(
        ["bash", str(VERIFY)],
        env=env,
        capture_output=True,
        text=True,
        timeout=GATE_TIMEOUT_S,
    )
    run_dirs = sorted(p for p in (project / ".meta-harness" / "receipts").glob("*") if p.is_dir())
    receipt = run_dirs[-1] / "27_properties.json"
    status = json.loads(receipt.read_text(encoding="utf-8")).get("status", "?")
    log = (run_dirs[-1] / "27_properties.log").read_text(encoding="utf-8")
    return proc.returncode, proc.stdout, status, log


def test_nothing_declared_is_rule_off(tmp_path: Path) -> None:
    """No `[verification]` at all: the tier is opt-in, so the gate stays green — and
    honest that it inspected nothing (never `pass`)."""
    project = _project(tmp_path / "undeclared", {"borromeanrings.toml": BASE_CONFIG + REQUIRED})
    code, stdout, status, log = _run_gate(project)
    assert code == 0, stdout
    assert status == "noop", stdout
    assert "OFF for this project" in log
    assert "inspected NOTHING" in stdout


def test_declared_passing_suite_is_a_real_pass(tmp_path: Path) -> None:
    """Negative control. Without it, a check that noop'd on everything would satisfy
    every other test here for the wrong reason."""
    project = _project(
        tmp_path / "passing",
        {
            "borromeanrings.toml": _declaring("tests/properties"),
            "tests/properties/test_sorting.py": GOOD_PROPERTY,
        },
    )
    code, stdout, status, _ = _run_gate(project)
    assert code == 0, stdout
    assert status == "pass", stdout
    assert "inspected NOTHING" not in stdout


def test_falsified_property_fails_the_gate(tmp_path: Path) -> None:
    """A counterexample is a failure, and the log keeps the counterexample."""
    project = _project(
        tmp_path / "falsified",
        {
            "borromeanrings.toml": _declaring("tests/properties"),
            "tests/properties/test_positive.py": BAD_PROPERTY,
        },
    )
    code, stdout, status, log = _run_gate(project)
    assert code != 0, f"a falsified property must FAIL the gate:\n{stdout}"
    assert status == "fail", stdout
    assert "Falsifying example" in log, log
    assert "PROPERTY FAILED" in log


def test_declared_but_empty_directory_fails_for_vacuity(tmp_path: Path) -> None:
    """The sharp edge: a verification claim with nothing behind it is rejected.

    `pass` would be the ADR-0049 defect verbatim; `noop` would make the declaration
    free (write the key, never write a property, stay green forever).
    """
    project = _project(
        tmp_path / "empty",
        {
            "borromeanrings.toml": _declaring("tests/properties"),
            "tests/properties/README.md": "properties go here, one day\n",
        },
    )
    code, stdout, status, log = _run_gate(project)
    assert code != 0, f"a declared-but-empty suite must FAIL:\n{stdout}"
    assert status == "fail", stdout
    assert "VACUOUS VERIFICATION CLAIM" in log
    assert "no property tests" in log
    # Both remedies are named, so the fix is one line either way.
    assert "remove the declaration" in log


def test_declared_directory_that_does_not_exist_fails(tmp_path: Path) -> None:
    """Same family: a claim pointing at nothing at all."""
    project = _project(
        tmp_path / "missingdir", {"borromeanrings.toml": _declaring("tests/properties")}
    )
    code, stdout, status, log = _run_gate(project)
    assert code != 0, f"a claim pointing at no directory must FAIL:\n{stdout}"
    assert status == "fail", stdout
    assert "VACUOUS VERIFICATION CLAIM" in log
    assert "is not a directory" in log


def test_test_files_that_collect_no_tests_fail(tmp_path: Path) -> None:
    """Second vacuity layer: files that look like tests but hold none (pytest exit 5)."""
    project = _project(
        tmp_path / "collectsnothing",
        {
            "borromeanrings.toml": _declaring("tests/properties"),
            "tests/properties/test_nothing.py": "PLANNED = 'a property, some day'\n",
        },
    )
    code, stdout, status, log = _run_gate(project)
    assert code != 0, f"a suite that collects no tests must FAIL:\n{stdout}"
    assert status == "fail", stdout
    assert "collected no tests" in log


def test_absent_runner_is_a_noop_that_names_the_missing_module(tmp_path: Path) -> None:
    """borromeanRings never installs a project's toolchain. It says what is missing.

    The stub shadows the real Hypothesis only for processes started in the project
    root, so nothing on this machine is uninstalled to run this test.
    """
    project = _project(
        tmp_path / "norunner",
        {
            "borromeanrings.toml": _declaring("tests/properties"),
            "tests/properties/test_sorting.py": GOOD_PROPERTY,
            "hypothesis.py": HYPOTHESIS_STUB,
        },
    )
    code, stdout, status, log = _run_gate(project)
    assert code == 0, f"a missing runner must not fail the project:\n{stdout}"
    assert status == "noop", stdout
    assert "hypothesis" in log, log
    assert "NOT run" in log
    assert "inspected NOTHING" in stdout


def test_missing_runner_cannot_mask_a_broken_claim(tmp_path: Path) -> None:
    """Order-of-evaluation contract: everything decidable *without* a runner is decided
    first. A machine with no Hypothesis still rejects a suite that was never written."""
    project = _project(
        tmp_path / "emptyandnorunner",
        {
            "borromeanrings.toml": _declaring("tests/properties"),
            "tests/properties/README.md": "properties go here, one day\n",
            "hypothesis.py": HYPOTHESIS_STUB,
        },
    )
    code, stdout, status, log = _run_gate(project)
    assert code != 0, f"vacuity must be decided before the runner probe:\n{stdout}"
    assert status == "fail", stdout
    assert "VACUOUS VERIFICATION CLAIM" in log
