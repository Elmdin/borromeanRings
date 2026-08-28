"""End-to-end: the gate distinguishes a hollow green from a real one.

The defect this locks down was found in the field. A governed project reported
``ok: true``, 12/12 green, while seven of those twelve checks had inspected *nothing*:
its ``src_dir`` pointed at a directory that did not exist, and the real code lived in
``tools/``. Every source-reading check honestly logged "greenfield — nothing to analyze"
and exited 0, so the verdict said PASS.

These tests run the real ``verify.sh`` against fixture projects and assert the two
outcomes that must stay distinct:

* **greenfield** (no source anywhere) — still green, reported as ``noop``. Planning must
  never be forced to scaffold code to satisfy the gate.
* **misconfigured** (declared path empty, real source elsewhere) — **rejected**.

See docs/specs/SPEC-self-status.md and ADR-0049.
"""

import json
import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
GATE_TIMEOUT_S = 120

CONFIG = (
    '[project]\nlanguage = "python"\nsrc_dir = "src"\n\n'
    '[checks]\nrequired = ["01_source_coherence"]\n\n[hygiene]\nrequires = []\n'
)


def _run_gate(project: Path) -> tuple[int, str, dict[str, str]]:
    """Run the real gate against ``project``; return (exit, stdout, {check: status})."""
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(project)
    proc = subprocess.run(
        ["bash", str(VERIFY)],
        env=env,
        capture_output=True,
        text=True,
        timeout=GATE_TIMEOUT_S,
    )
    statuses: dict[str, str] = {}
    run_dirs = sorted(p for p in (project / ".meta-harness" / "receipts").glob("*") if p.is_dir())
    if run_dirs:
        for receipt in run_dirs[-1].glob("*.json"):
            try:
                statuses[receipt.stem] = json.loads(receipt.read_text()).get("status", "?")
            except (OSError, json.JSONDecodeError):
                statuses[receipt.stem] = "?"
    return proc.returncode, proc.stdout, statuses


def _git_project(root: Path, files: dict[str, str]) -> Path:
    """Materialize a real git repo so 'tracked source' is meaningful."""
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


def test_greenfield_project_is_green_but_reported_as_noop(tmp_path: Path) -> None:
    """No source anywhere is legitimate — pass, but never claim anything was inspected."""
    project = _git_project(tmp_path / "greenfield", {"borromeanrings.toml": CONFIG})
    code, stdout, statuses = _run_gate(project)
    assert code == 0, stdout
    assert statuses.get("01_source_coherence") == "noop"
    # The hollowness is surfaced in the gate output, not buried in a log.
    assert "inspected NOTHING" in stdout


def test_misconfigured_src_dir_fails_the_gate(tmp_path: Path) -> None:
    """The field defect: src_dir resolves to nothing while real code sits in tools/."""
    project = _git_project(
        tmp_path / "misconfigured",
        {
            "borromeanrings.toml": CONFIG,
            "tools/alpha.py": "def a() -> None:\n    pass\n",
            "tools/beta.py": "def b() -> None:\n    pass\n",
        },
    )
    code, stdout, statuses = _run_gate(project)
    assert code != 0, f"a gate blind to all of the project's code must FAIL:\n{stdout}"
    assert statuses.get("01_source_coherence") == "fail"
    # The failure must name where the code actually is, so the fix is one config line.
    log = next((project / ".meta-harness" / "receipts").glob("*/01_source_coherence.log"))
    assert "tools" in log.read_text(encoding="utf-8")


def test_tdd_red_state_is_not_treated_as_misconfiguration(tmp_path: Path) -> None:
    """A failing test written before the implementation must NOT fail the gate.

    Test-first development spends real time in exactly this state (a tracked test, no
    implementation yet). Failing it would punish the workflow borromeanRings exists to
    support — and this check is in adopt.py's RECOMMENDED set, so the false positive
    would propagate to every project that adopts it.
    """
    project = _git_project(
        tmp_path / "tddred",
        {
            "borromeanrings.toml": CONFIG,
            "tests/test_feature.py": "def test_x():\n    from pkg.f import g  # noqa\n",
        },
    )
    code, stdout, statuses = _run_gate(project)
    assert code == 0, f"TDD-RED must stay green:\n{stdout}"
    assert statuses.get("01_source_coherence") == "noop"


def test_empty_src_dir_config_fails_closed(tmp_path: Path) -> None:
    """An unresolvable src_dir must FAIL, not silently scan the whole repo and pass.

    ``project_root / ""`` is the repo root, whose recursive scan finds source in almost
    any project — so a broken config would otherwise yield a confident PASS from the one
    check whose whole job is catching a config that doesn't match reality.
    """
    broken = (
        '[project]\nlanguage = "python"\nsrc_dir = ""\n\n'
        '[checks]\nrequired = ["01_source_coherence"]\n\n[hygiene]\nrequires = []\n'
    )
    project = _git_project(
        tmp_path / "brokencfg",
        {"borromeanrings.toml": broken, "pkg/mod.py": "def f() -> None:\n    pass\n"},
    )
    code, stdout, statuses = _run_gate(project)
    assert code != 0, f"an unresolvable src_dir must fail closed:\n{stdout}"
    assert statuses.get("01_source_coherence") == "fail"


def test_unset_package_is_reported_not_failed(tmp_path: Path) -> None:
    """`package` is legitimately optional, but its absence blinds three checks.

    The guard must not certify "the gate sees your code" in silence while
    32_complexity/33_coupling/45_docstrings measure nothing — it says so instead.
    """
    project = _git_project(
        tmp_path / "nopackage",
        {"borromeanrings.toml": CONFIG, "src/mod.py": "def f() -> None:\n    pass\n"},
    )
    code, stdout, statuses = _run_gate(project)
    assert code == 0, stdout
    assert statuses.get("01_source_coherence") == "pass"
    log = next((project / ".meta-harness" / "receipts").glob("*/01_source_coherence.log"))
    text = log.read_text(encoding="utf-8")
    assert "package" in text and "32_complexity" in text


def test_correctly_configured_project_passes_for_the_right_reason(tmp_path: Path) -> None:
    """Negative control: source at the declared path is a real pass, not a noop."""
    project = _git_project(
        tmp_path / "configured",
        {"borromeanrings.toml": CONFIG, "src/pkg/mod.py": "def f() -> None:\n    pass\n"},
    )
    code, stdout, statuses = _run_gate(project)
    assert code == 0, stdout
    assert statuses.get("01_source_coherence") == "pass"
    assert "inspected NOTHING" not in stdout
