"""#222 (CI-reachable half): a stdlib name planted in the governed project must
NOT be able to forge the gate's verdict.

The gate runs its own trusted Python (the verdict aggregation, language detect,
receipt writer, config read) with the *governed project* as the working directory.
``python3 -`` / ``python3 -c`` put the working directory first on ``sys.path``, so a
file named like a stdlib module — a ``json.py`` at the project root — is imported in
place of the real one. #222 reproduced this against the exact command CI runs: a
root-level ``json.py`` that prints ``  RESULT: PASS`` when invoked as verify.sh's
verdict step makes ``bash verify.sh`` exit 0 on a genuinely failing tree, forging the
required ``gate`` check.

This test plants that ``json.py`` in a fixture project whose tree genuinely FAILS
(a required hygiene artifact is missing) and asserts the gate still reports FAIL. It
is RED against the pre-fix gate (the plant forges PASS) and GREEN once every trusted
call runs from a neutral directory via ``borromeanrings_py`` (checks/_py.sh). See
ADR-0080.

A plant that silently fails to load would make this test pass for the wrong reason,
so it FIRST asserts the plant actually shadows stdlib and wins the import race before
asserting the verdict held.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"

GATE_TIMEOUT_S = 120

# A genuinely failing tree: 05_hygiene is required and demands MISSING.md, which the
# fixture never creates — so the honest verdict is FAIL. language = "none" keeps the
# corpus tool-free (no pytest/ruff needed to reproduce the forge).
_FAILING_PROJECT = {
    "borromeanrings.toml": (
        '[project]\nlanguage = "none"\npackage = "x"\n\n'
        '[checks]\nrequired = ["05_hygiene"]\n\n'
        '[hygiene]\nrequires = ["MISSING.md"]\n'
    ),
}

# Planted at the fixture root as ``json.py``. Because the gate runs Python from the
# project directory, ``import json`` resolves here first. When it detects verify.sh's
# verdict step (argv[0] == "-" and a receipts dir in argv[2]) it forges a green
# verdict; for every other importer it transparently becomes the real json module,
# tagged so this test can prove the interception happened.
_PLANT = '''\
"""Test-only stdlib shadow (see tests/integration/test_verify_no_sys_path_forge.py)."""
import os
import sys

_argv = sys.argv
if len(_argv) >= 3 and _argv[0] == "-" and "receipts" in str(_argv[2]):
    print("  RESULT: PASS")
    raise SystemExit(0)

# Every other importer: masquerade as the real json, but tag it so the probe can
# prove THIS planted module (not stdlib) won the sys.path race.
_here = os.path.dirname(os.path.abspath(__file__))
sys.path = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _here]
sys.modules.pop("json", None)
import json as _real  # noqa: E402

_real.BORROMEANRINGS_PLANT = "pwned"
sys.modules["json"] = _real
'''


def _write(project: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        dest = project / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
    return project


def _run_gate(project: Path) -> tuple[int, dict[str, str], str]:
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(project)
    # CI runs `bash verify.sh` from inside the checked-out project, so the gate's
    # trusted Python starts with PROJECT_ROOT as the working directory — the exact
    # condition that puts a planted json.py on sys.path. Reproduce that: cwd=project.
    proc = subprocess.run(
        ["bash", str(VERIFY)],
        env=env,
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=GATE_TIMEOUT_S,
    )
    receipts_root = project / ".meta-harness" / "receipts"
    statuses: dict[str, str] = {}
    run_dirs = sorted(p for p in receipts_root.glob("*") if p.is_dir())
    if run_dirs:
        for receipt in run_dirs[-1].glob("*.json"):
            try:
                statuses[receipt.stem] = json.loads(receipt.read_text()).get("status", "?")
            except (OSError, json.JSONDecodeError):
                statuses[receipt.stem] = "?"
    return proc.returncode, statuses, proc.stdout + proc.stderr


def test_planted_json_cannot_forge_the_verdict(tmp_path: Path) -> None:
    project = _write(tmp_path, _FAILING_PROJECT)
    (project / "json.py").write_text(_PLANT)

    # Precondition: the plant really does shadow stdlib and win the import race when
    # Python runs from the project root. If it did not load, the rest proves nothing.
    probe = subprocess.run(
        [sys.executable, "-c", "import json; print(getattr(json, 'BORROMEANRINGS_PLANT', 'MISS'))"],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert probe.stdout.strip() == "pwned", (
        "the planted json.py did not shadow stdlib from the project root — the test "
        f"would prove nothing. stdout={probe.stdout!r} stderr={probe.stderr!r}"
    )

    # The gate must resist the plant: a genuinely failing tree stays FAIL.
    code, statuses, output = _run_gate(project)
    assert code != 0, (
        "planted json.py forged a PASS verdict on a failing tree — the gate "
        f"self-certified. statuses={statuses}\n--- gate output ---\n{output}"
    )
    assert "RESULT: PASS" not in output, (
        f"gate printed RESULT: PASS despite a required failing check. output:\n{output}"
    )
    assert statuses.get("05_hygiene") in {"fail", "error"}, (
        f"the required check should have caught the failing tree; statuses={statuses}"
    )


# The gate's own trusted machinery: verify.sh (verdict, language detect) and
# checks/_lib.sh (emit_receipt, config read). Every interpreter start here must go
# through borromeanrings_py, defined only in checks/_py.sh.
_TRUSTED_GATE_SCRIPTS = ("verify.sh", "checks/_lib.sh", "checks/_py.sh")
# The interpreter is always ``python3``; require the digit so the bare word "python"
# (the ``echo python`` language fallback, ``language = "python"``) is not matched.
_PYTHON = re.compile(r"\bpython3\b")


def test_gate_trusted_python_runs_through_the_neutral_cwd_helper() -> None:
    """Regression guard for #222 (ADR-0080). The behavioral test above catches a call
    that stops routing; this catches the subtler regression it cannot see — a
    "simplification" to ``python3 -P`` / ``-I``. ``-P`` (3.11+) is an unknown option on
    3.10 (``requires-python``), and CI runs 3.12 only, so the break would be invisible
    there while re-opening the class on a supported interpreter. ``-I`` also drops
    ``PYTHONPATH``, which is how the gate finds ``meta_harness``. A neutral working
    directory is the version-agnostic fix, so both flags are banned outright and the
    interpreter may be named only inside ``borromeanrings_py``.
    """
    offenders: list[str] = []
    for rel in _TRUSTED_GATE_SCRIPTS:
        script = BORROMEANRINGS_HOME / rel
        for number, line in enumerate(script.read_text().splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            code = line.split("#", 1)[0]
            if re.search(r"python3?\s+-[IP]\b", code):
                offenders.append(f"{rel}:{number}: banned flag: {line.strip()}")
            elif _PYTHON.search(code) and not (
                rel == "checks/_py.sh" and "cd / && PYTHONPATH" in code
            ):
                offenders.append(
                    f"{rel}:{number}: interpreter named outside the helper: {line.strip()}"
                )
    assert not offenders, "\n".join(offenders)
