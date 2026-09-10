"""End-to-end: the mutation lane fails closed on zero evaluated mutants, and says so.

The shape this pins was seen on PRs #160 and #168. mutmut copies only ``src/``,
``tests/``, ``setup.cfg`` and ``pyproject.toml`` into ``mutants/`` and runs pytest with
that directory as cwd. A unit test that reads any other repo path (``.claude/``,
``contracts/``, ...) passes on the fast lane and fails inside the sandbox; mutmut's
clean-test run then aborts, 0 mutants are evaluated, and the vacuous score is 1.0.
ADR-0022 says ``60_mutation`` must FAIL there ("MUTATION CHECK DID NOT RUN"), never
trust that 1.0 — this test proves it against the real ``verify.sh --heavy``.

It also asserts the gate's verdict row carries the evaluated-mutant count
(``PASS (evaluated N, score S)`` / ``FAIL (evaluated 0)``), so a reader never has to
open the log to learn whether mutmut did any work. See issue #187.

Cost: two heavy-gate runs on a one-function fixture, ~30 s each on a dev laptop (mutmut
itself is ~4 s; the rest is the full check set the gate runs regardless). This file
drives the heavy lane through bash, so it is in ``setup.cfg``'s mutmut ignore list.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from meta_harness.mutation import parse_mutmut_summary, total_evaluated

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
#: One heavy-gate run on the fixture is ~30 s; this bounds a pathological hang only.
GATE_TIMEOUT_S = 600
#: Per-check wall clock inside the gate — generous so a loaded host never trips it.
CHECK_TIMEOUT_S = "600"

CONFIG = (
    '[project]\nlanguage = "python"\nsrc_dir = "src"\ntests_dir = "tests"\n\n'
    '[checks]\nrequired = ["01_source_coherence"]\nheavy = ["60_mutation"]\n\n'
    "[hygiene]\nrequires = []\n"
)
# A tiny real package: one function → two mutants (`+ 1` → `- 1`, `+ 2`), both killed.
PACKAGE = '"""Tiny fixture package."""\n\n\ndef add_one(value: int) -> int:\n    return value + 1\n'
UNIT_TEST = (
    "from tiny import add_one\n\n\n"
    "def test_add_one() -> None:\n    assert add_one(1) == 2\n    assert add_one(-1) == 0\n"
)
# The #168 shape: a test that resolves a repo path OUTSIDE src/ and tests/ relative
# to its own file. Passes at the project root; fails under mutants/ (no .claude/ there).
PLANTED_TEST = (
    "from pathlib import Path\n\n\n"
    "def test_reads_outside_src_and_tests() -> None:\n"
    '    marker = Path(__file__).resolve().parents[1] / ".claude" / "x.txt"\n'
    '    assert marker.read_text() == "x\\n"\n'
)
PLANTED_TEST_PATH = "tests/test_reads_outside.py"
MUTMUT_CFG = "[mutmut]\nsource_paths = src/tiny/\n"
PYPROJECT = '[tool.pytest.ini_options]\npythonpath = ["src"]\ntestpaths = ["tests"]\n'


def _git_project(root: Path, files: dict[str, str]) -> Path:
    """Materialize a real git repo (several checks only count tracked files)."""
    for rel, content in files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    for argv in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
    ):
        subprocess.run(argv, cwd=root, capture_output=True, check=False)
    return root


def _run_heavy_gate(project: Path) -> tuple[int, str, dict[str, object], str]:
    """Run the real ``verify.sh --heavy``; return (exit, stdout, 60_mutation receipt, log)."""
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(project)
    env["BORROMEANRINGS_CHECK_TIMEOUT"] = CHECK_TIMEOUT_S
    env["BORROMEANRINGS_MUTATION_TIMEOUT"] = CHECK_TIMEOUT_S
    proc = subprocess.run(
        ["bash", str(VERIFY), "--heavy"],
        env=env,
        capture_output=True,
        text=True,
        timeout=GATE_TIMEOUT_S,
    )
    run_dirs = sorted(p for p in (project / ".meta-harness" / "receipts").glob("*") if p.is_dir())
    assert run_dirs, f"the gate wrote no receipts:\n{proc.stdout}\n{proc.stderr}"
    receipt_path = run_dirs[-1] / "60_mutation.json"
    assert receipt_path.exists(), f"no 60_mutation receipt:\n{proc.stdout}\n{proc.stderr}"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    log = (run_dirs[-1] / "60_mutation.log").read_text(encoding="utf-8", errors="replace")
    return proc.returncode, proc.stdout, receipt, log


def _gate_row(stdout: str, check: str) -> str:
    """The verdict-table row for ``check`` (stripped), or '' if absent."""
    return next(
        (line.strip() for line in stdout.splitlines() if line.strip().startswith(check)), ""
    )


def test_sandbox_only_failure_fails_closed_then_passes_with_a_real_count(tmp_path: Path) -> None:
    """(a) planted sandbox-only failure → FAIL, named; (b) removed → PASS with count > 0."""
    project = _git_project(
        tmp_path / "governed",
        {
            "borromeanrings.toml": CONFIG,
            "setup.cfg": MUTMUT_CFG,
            "pyproject.toml": PYPROJECT,
            "src/tiny/__init__.py": PACKAGE,
            "tests/test_tiny.py": UNIT_TEST,
            PLANTED_TEST_PATH: PLANTED_TEST,
            ".claude/x.txt": "x\n",
        },
    )

    # (a) The planted test passes at the root but fails inside mutants/: fail closed.
    code, stdout, receipt, log = _run_heavy_gate(project)
    assert code != 0, f"a mutation run that evaluated nothing must FAIL the heavy gate:\n{stdout}"
    assert receipt.get("status") == "fail", f"{receipt}\n{log}"
    assert "MUTATION CHECK DID NOT RUN" in log
    assert receipt.get("summary") == "evaluated 0"
    assert _gate_row(stdout, "60_mutation").endswith("FAIL (evaluated 0)"), stdout
    # The reason is on the record too: mutmut's clean run named the test that broke it.
    assert PLANTED_TEST_PATH in log

    # (b) Remove the planted test — and mutmut's copied tree, which would otherwise keep
    # the stale copy (copy_src_dir never deletes) and reproduce the failure.
    (project / PLANTED_TEST_PATH).unlink()
    shutil.rmtree(project / "mutants", ignore_errors=True)
    subprocess.run(["git", "add", "-A"], cwd=project, capture_output=True, check=False)

    code, stdout, receipt, log = _run_heavy_gate(project)
    assert code == 0, f"the clean fixture must pass the heavy gate:\n{stdout}\n{log}"
    assert receipt.get("status") == "pass", f"{receipt}\n{log}"
    assert "MUTATION CHECK DID NOT RUN" not in log
    evaluated = total_evaluated(parse_mutmut_summary(log))
    assert evaluated > 0, log
    assert receipt.get("summary") == f"evaluated {evaluated}, score {receipt['mutation_score']:.2f}"
    assert _gate_row(stdout, "60_mutation").endswith(f"PASS ({receipt['summary']})"), stdout
