"""End-to-end: the README's counts are a checked claim, not decoration.

Runs the real ``verify.sh`` against fixture projects whose README states a count. A wrong
count is rejected; a right one passes; no count is ``noop`` (a README may choose not to
state one). See docs/specs/SPEC-describe.md and ADR-0052.
"""

import json
import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
TIMEOUT_S = 180
REGISTRY_SIZE = len(
    [
        p
        for lane in ("shared", "python", "ci")
        for p in (BORROMEANRINGS_HOME / "checks" / lane).glob("[0-9]*.sh")
    ]
)

CONFIG = (
    '[project]\nlanguage = "python"\nsrc_dir = "src"\n\n'
    '[checks]\nrequired = ["04_self_description", "05_hygiene"]\n\n[hygiene]\nrequires = []\n'
)


def _gate(project: Path) -> tuple[int, str, dict[str, str]]:
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(project)
    proc = subprocess.run(
        ["bash", str(VERIFY)], env=env, capture_output=True, text=True, timeout=TIMEOUT_S
    )
    statuses: dict[str, str] = {}
    runs = sorted(p for p in (project / ".meta-harness" / "receipts").glob("*") if p.is_dir())
    if runs:
        for r in runs[-1].glob("*.json"):
            try:
                statuses[r.stem] = json.loads(r.read_text()).get("status", "?")
            except (OSError, json.JSONDecodeError):
                statuses[r.stem] = "?"
    return proc.returncode, proc.stdout, statuses


def _project(root: Path, readme: str | None) -> Path:
    root.mkdir()
    (root / "borromeanrings.toml").write_text(CONFIG, encoding="utf-8")
    if readme is not None:
        (root / "README.md").write_text(readme, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True, check=False)
    return root


def test_wrong_readme_count_is_rejected(tmp_path: Path) -> None:
    project = _project(
        tmp_path / "wrong", f"**{REGISTRY_SIZE + 5} checks** here (two gates on this repo)"
    )
    code, stdout, statuses = _gate(project)
    assert code != 0, f"a stale count must fail:\n{stdout}"
    assert statuses.get("04_self_description") == "fail"


def test_correct_readme_counts_pass(tmp_path: Path) -> None:
    project = _project(
        tmp_path / "right", f"**{REGISTRY_SIZE} checks** on disk (two gates on this repo)"
    )
    code, stdout, statuses = _gate(project)
    assert code == 0, stdout
    assert statuses.get("04_self_description") == "pass"


def test_readme_without_counts_is_noop(tmp_path: Path) -> None:
    project = _project(tmp_path / "silent", "# A project\nNo numbers stated.\n")
    code, stdout, statuses = _gate(project)
    assert code == 0, stdout
    assert statuses.get("04_self_description") == "noop"
    assert "inspected NOTHING" in stdout
