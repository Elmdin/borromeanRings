"""Adversarial self-test: the gate must REJECT known-bad projects and ACCEPT a
known-good one.

Every other test proves a *check module* behaves; none proved the assembled
gate actually rejects bad code. An earlier empirical probe showed buggy code
with vacuous tests sailing through — this makes that probe permanent. We run the
real ``verify.sh`` against a corpus of minimal fixture projects (built in tmp,
never committed, so they can't poison this repo's own ruff/bandit) and assert
the end-to-end verdict:

  - a planted defect in a *required* dimension  => RESULT: FAIL (rejected)
  - a clean project                             => RESULT: PASS (accepted)

The good fixture is the negative control: without it, a gate that failed
*everything* would pass this suite for the wrong reason. See
docs/specs/SPEC-adversarial-selftest.md and ADR-0025.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"

# Each fixture runs the full gate in a subprocess; keep the corpus tight.
GATE_TIMEOUT_S = 120


def _run_gate(project: Path) -> tuple[int, dict[str, str]]:
    """Run the real gate against ``project``; return (exit_code, {check: status})."""
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(project)
    proc = subprocess.run(
        ["bash", str(VERIFY)],
        env=env,
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
    return proc.returncode, statuses


def _write(project: Path, files: dict[str, str]) -> Path:
    """Materialize ``{relpath: content}`` under ``project`` and return it."""
    for rel, content in files.items():
        dest = project / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
    return project


def _python_project(required: str) -> str:
    return (
        '[project]\nlanguage = "python"\nsrc_dir = "src"\n\n'
        f'[checks]\nrequired = ["{required}"]\n\n[hygiene]\nrequires = []\n'
    )


# --- known-bad fixtures: (label, files, required_check) -----------------------

_LINT_BAD = {
    "borromeanrings.toml": _python_project("20_lint"),
    "src/bad.py": "import os\n",  # F401 unused import
}
_SECURITY_BAD = {
    "borromeanrings.toml": _python_project("50_security"),
    # B602: subprocess call with shell=True
    "src/bad.py": "import subprocess\n\n\ndef run(x):\n    return subprocess.call(x, shell=True)\n",
}
_HYGIENE_BAD = {
    "borromeanrings.toml": (
        '[project]\nlanguage = "none"\npackage = "x"\n\n'
        '[checks]\nrequired = ["05_hygiene"]\n\n[hygiene]\nrequires = ["MISSING.md"]\n'
    ),
}
_LAYOUT_BAD = {
    "borromeanrings.toml": (
        '[project]\nlanguage = "none"\npackage = "x"\n\n'
        '[checks]\nrequired = ["07_layout"]\n\n[hygiene]\nrequires = []\n\n'
        '[layout]\nroot_doc_allowlist = ["README.md"]\n'
    ),
    "README.md": "# ok\n",
    "NOTALLOWED.md": "# not in the allowlist\n",
}

KNOWN_BAD = [
    pytest.param(_LINT_BAD, "20_lint", id="lint-violation"),
    pytest.param(_SECURITY_BAD, "50_security", id="security-finding"),
    pytest.param(_HYGIENE_BAD, "05_hygiene", id="missing-hygiene-artifact"),
    pytest.param(_LAYOUT_BAD, "07_layout", id="disallowed-root-doc"),
]


@pytest.mark.parametrize("files,required", KNOWN_BAD)
def test_gate_rejects_known_bad(tmp_path: Path, files: dict[str, str], required: str) -> None:
    code, statuses = _run_gate(_write(tmp_path, files))
    assert code != 0, f"gate must REJECT known-bad ({required}); statuses={statuses}"
    assert statuses.get(required) in {"fail", "error"}, (
        f"the required check '{required}' must be the one that caught the defect; "
        f"statuses={statuses}"
    )


def test_gate_accepts_known_good(tmp_path: Path) -> None:
    """Negative control: a clean project must PASS, so the corpus isn't passing
    merely because the gate rejects everything."""
    good = {
        "borromeanrings.toml": (
            '[project]\nlanguage = "none"\npackage = "x"\n\n'
            '[checks]\nrequired = ["05_hygiene"]\n\n[hygiene]\nrequires = []\n'
        ),
    }
    code, statuses = _run_gate(_write(tmp_path, good))
    assert code == 0, f"gate must ACCEPT a clean project; statuses={statuses}"
    assert statuses.get("05_hygiene") == "pass", f"statuses={statuses}"
