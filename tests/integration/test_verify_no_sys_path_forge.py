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
# ``-I`` / ``-P`` in any short-flag cluster — ``-I``, ``-P``, and combined ``-IP`` /
# ``-PI`` / ``-sP`` (which evade a plain ``-[IP]\b``, #224 review S4).
_BANNED_FLAGS = re.compile(r"python3\s+-[A-Za-z]*[IP]")

# The 18 analysis heredocs whose stdout/exit code becomes a required check's status.
# #222 routed every one through borromeanrings_py; if any reverts to a bare ``python3
# -``/``-c`` the shadow reopens for that check, so guard the property directly (the
# behavioral test above uses language="none" and exercises none of them).
_ROUTED_HEREDOC_CHECKS = (
    "checks/shared/05_hygiene.sh",
    "checks/shared/06_git_identity.sh",
    "checks/shared/07_layout.sh",
    "checks/shared/08_branch.sh",
    "checks/shared/09_commits.sh",
    "checks/shared/11_changelog.sh",
    "checks/shared/12_secrets.sh",
    "checks/shared/13_adr.sh",
    "checks/shared/14_container.sh",
    "checks/shared/15_a11y.sh",
    "checks/python/32_complexity.sh",
    "checks/python/33_coupling.sh",
    "checks/python/34_api_diff.sh",
    "checks/python/35_architecture.sh",
    "checks/python/45_docstrings.sh",
    "checks/python/55_doc_drift.sh",
    "checks/python/56_critics.sh",
    "checks/ci/74_secret_history.sh",
)


def _code_lines(rel: str):
    for number, line in enumerate((BORROMEANRINGS_HOME / rel).read_text().splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        yield number, line, line.split("#", 1)[0]


def test_gate_trusted_python_runs_through_the_neutral_cwd_helper() -> None:
    """Regression guard for #222 (ADR-0080). The behavioral test above catches a call
    that stops routing; this catches the subtler regression it cannot see — a
    "simplification" to ``python3 -P`` / ``-I`` (or a combined ``-IP``). ``-P`` (3.11+)
    is an unknown option on 3.10 (``requires-python``), and CI runs 3.12 only, so the
    break would be invisible there while re-opening the class on a supported
    interpreter. ``-I`` also drops ``PYTHONPATH``, which is how the gate finds
    ``meta_harness``. A neutral working directory is the version-agnostic fix, so both
    flags are banned outright and the interpreter may be named only inside
    ``borromeanrings_py``.
    """
    offenders: list[str] = []
    for rel in _TRUSTED_GATE_SCRIPTS:
        for number, line, code in _code_lines(rel):
            if _BANNED_FLAGS.search(code):
                offenders.append(f"{rel}:{number}: banned flag: {line.strip()}")
            elif _PYTHON.search(code) and not (rel == "checks/_py.sh" and "cd /" in code):
                offenders.append(
                    f"{rel}:{number}: interpreter named outside the helper: {line.strip()}"
                )
    assert not offenders, "\n".join(offenders)


def test_routed_analysis_heredocs_stay_routed() -> None:
    """#224 review S3: the 18 verdict-deciding heredocs must keep routing through
    borromeanrings_py. Each must invoke it and must NOT name a bare ``python3``
    interpreter start (these files run no tool, so every ``python3`` here would be a
    trusted call that regressed off the helper)."""
    offenders: list[str] = []
    for rel in _ROUTED_HEREDOC_CHECKS:
        text = (BORROMEANRINGS_HOME / rel).read_text()
        if "borromeanrings_py" not in text:
            offenders.append(f"{rel}: no longer invokes borromeanrings_py")
        for number, line, code in _code_lines(rel):
            if _BANNED_FLAGS.search(code):
                offenders.append(f"{rel}:{number}: banned flag: {line.strip()}")
            elif _PYTHON.search(code):
                offenders.append(
                    f"{rel}:{number}: bare python3 (must be borromeanrings_py): {line.strip()}"
                )
    assert not offenders, "\n".join(offenders)


def test_build_check_routes_compileall() -> None:
    """#224 review S2: 00_build's compileall (stdlib, path-arg, no project code) must
    run through borromeanrings_py so a planted compileall.py cannot forge exit 0. The
    ``import <package>`` half legitimately runs project code and stays unrouted (M7)."""
    text = (BORROMEANRINGS_HOME / "checks/python/00_build.sh").read_text()
    assert "borromeanrings_py -m compileall" in text, (
        "00_build must route the compileall step through borromeanrings_py"
    )


# --- #224 review S1: a user-site startup hook must not forge the verdict ----------

_USERCUSTOMIZE = """\
import builtins as _b
_orig = _b.print
def _p(*a, **k):
    s = " ".join(str(x) for x in a)
    if "RESULT: FAIL" in s:
        s = s.replace("FAIL", "PASS")
    return _orig(s, **k)
_b.print = _p
import sys as _s
_s.stderr.write("USERCUSTOMIZE-RAN\\n")
"""


def _fake_user_site(tmp_path: Path) -> Path:
    ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    site = tmp_path / "userbase" / "lib" / f"python{ver}" / "site-packages"
    site.mkdir(parents=True)
    (site / "usercustomize.py").write_text(_USERCUSTOMIZE)
    return tmp_path / "userbase"


def test_user_site_startup_hook_cannot_forge_the_verdict(tmp_path: Path) -> None:
    """`cd /` closes the project-directory shadow but NOT a user-site startup hook: a
    `usercustomize.py` in the gate-running user's site-packages runs at interpreter
    startup and is on sys.path even after `cd /` (#224 review S1). The fix is
    `PYTHONNOUSERSITE=1` in `borromeanrings_py`, which suppresses it WITHOUT dropping
    `PYTHONPATH` (so `meta_harness` still resolves)."""
    userbase = _fake_user_site(tmp_path)
    src = str(BORROMEANRINGS_HOME / "src")
    env = dict(os.environ)
    env["PYTHONUSERBASE"] = str(userbase)
    env.pop("PYTHONNOUSERSITE", None)

    # Attack is live: the neutral-cwd form WITHOUT PYTHONNOUSERSITE (the pre-fix helper)
    # runs the planted hook, which rewrites RESULT: FAIL -> PASS.
    pre = subprocess.run(
        ["bash", "-c", 'cd / && PYTHONPATH="$1" python3 -c "print(\'RESULT: FAIL\')"', "sh", src],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "USERCUSTOMIZE-RAN" in pre.stderr, f"hook did not run: {pre.stderr!r}"
    assert "RESULT: PASS" in pre.stdout, f"pre-fix attack did not forge: {pre.stdout!r}"

    helper = (
        f'export BORROMEANRINGS_HOME="{BORROMEANRINGS_HOME}"; '
        f'source "{BORROMEANRINGS_HOME}/checks/_py.sh"; '
    )
    # The actual helper (PYTHONNOUSERSITE=1): the hook never runs, verdict holds.
    fixed = subprocess.run(
        ["bash", "-c", helper + "borromeanrings_py -c \"print('RESULT: FAIL')\""],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "USERCUSTOMIZE-RAN" not in fixed.stderr, f"hook still ran: {fixed.stderr!r}"
    assert fixed.stdout.strip() == "RESULT: FAIL", f"verdict altered: {fixed.stdout!r}"

    # meta_harness + stdlib still resolve with user-site disabled.
    resolves = subprocess.run(
        ["bash", "-c", helper + "borromeanrings_py -c \"import meta_harness, json; print('OK')\""],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert resolves.stdout.strip() == "OK", f"lost meta_harness/stdlib: {resolves.stderr!r}"


# --- #224 review S2: a planted compileall.py must not forge 00_build --------------

_SYNTAX_ERROR_PROJECT = {
    "borromeanrings.toml": '[project]\nlanguage = "python"\nsrc_dir = "src"\npackage = "pkg"\n',
    "src/pkg/__init__.py": "def broken(:\n    pass\n",  # genuine SyntaxError
}
# Planted at the project root as compileall.py: `python3 -m compileall` (run from the
# project) imports THIS instead of stdlib and exits 0, faking a clean compile. Guarded
# so a plain `import compileall` (the probe) does not trip the SystemExit.
_COMPILEALL_PLANT = 'if __name__ == "__main__":\n    import sys\n    raise SystemExit(0)\n'


def test_planted_compileall_cannot_forge_the_build_check(tmp_path: Path) -> None:
    project = _write(tmp_path, _SYNTAX_ERROR_PROJECT)
    (project / "compileall.py").write_text(_COMPILEALL_PLANT)

    # Attack is live: from the project cwd, the plant wins the import race and
    # `-m compileall` exits 0 despite the syntax error.
    who = subprocess.run(
        [sys.executable, "-c", "import compileall,sys;print(compileall.__file__)"],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert who.stdout.strip() == str(project / "compileall.py"), who.stdout
    forged = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", "src"],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert forged.returncode == 0, "plant should have forged a clean compile (rc 0)"

    # The routed 00_build runs real stdlib compileall from a neutral dir and catches it.
    receipt_dir = project / ".receipts"
    receipt_dir.mkdir()
    env = dict(os.environ)
    env["PROJECT_ROOT"] = str(project)
    env["RECEIPT_DIR"] = str(receipt_dir)
    env["BORROMEANRINGS_HOME"] = str(BORROMEANRINGS_HOME)
    proc = subprocess.run(
        ["bash", str(BORROMEANRINGS_HOME / "checks/python/00_build.sh")],
        env=env,
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=60,
    )
    status = json.loads((receipt_dir / "00_build.json").read_text()).get("status")
    assert proc.returncode != 0, f"00_build passed a syntax-error tree; rc={proc.returncode}"
    assert status == "fail", f"00_build receipt should be fail, got {status!r}"
