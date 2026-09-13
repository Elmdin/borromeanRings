"""End-to-end: the prior-art gate demands a survey for new public surface, and only then.

Runs the real ``verify.sh`` against fixture repos and asserts the three outcomes that must
stay distinct: new surface without a survey is rejected; with a survey it passes; a change
that adds no public surface reports ``noop`` — the gate looked and found no question to
ask (ADR-0049). See docs/specs/SPEC-prior-art.md and ADR-0051.
"""

import json
import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
TIMEOUT_S = 180

CONFIG = (
    '[project]\nlanguage = "python"\nsrc_dir = "src"\n\n'
    '[checks]\nrequired = ["17_prior_art"]\n\n[hygiene]\nrequires = []\n'
)


def _run(argv: list[str], cwd: Path) -> None:
    subprocess.run(argv, cwd=cwd, capture_output=True, check=False)


def _gate(project: Path) -> tuple[int, str, dict[str, str]]:
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(project)
    proc = subprocess.run(
        ["bash", str(VERIFY)], env=env, capture_output=True, text=True, timeout=TIMEOUT_S
    )
    statuses: dict[str, str] = {}
    runs = sorted(p for p in (project / ".meta-harness" / "receipts").glob("*") if p.is_dir())
    if runs:
        for receipt in runs[-1].glob("*.json"):
            try:
                statuses[receipt.stem] = json.loads(receipt.read_text()).get("status", "?")
            except (OSError, json.JSONDecodeError):
                statuses[receipt.stem] = "?"
    return proc.returncode, proc.stdout, statuses


def _feature_repo(root: Path, feature_files: dict[str, str]) -> Path:
    """main with one module, then feat/x adding ``feature_files`` on top."""
    root.mkdir()
    _run(["git", "init", "-q", "-b", "main"], root)
    for key, value in (("user.email", "t@t"), ("user.name", "t")):
        _run(["git", "config", key, value], root)
    (root / "borromeanrings.toml").write_text(CONFIG, encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "core.py").write_text("def existing():\n    pass\n", encoding="utf-8")
    _run(["git", "add", "-A"], root)
    _run(["git", "commit", "-qm", "init"], root)
    _run(["git", "checkout", "-q", "-b", "feat/x"], root)
    for rel, content in feature_files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    _run(["git", "add", "-A"], root)
    _run(["git", "commit", "-qm", "feat: change"], root)
    return root


def test_new_public_surface_without_a_survey_is_rejected(tmp_path: Path) -> None:
    project = _feature_repo(
        tmp_path / "nosurvey",
        {"src/core.py": "def existing():\n    pass\n\ndef hash_bytes(b):\n    return 0\n"},
    )
    code, stdout, statuses = _gate(project)
    assert code != 0, f"new surface with no survey must be rejected:\n{stdout}"
    assert statuses.get("17_prior_art") == "fail"
    log = next((project / ".meta-harness" / "receipts").glob("*/17_prior_art.log"))
    assert "hash_bytes" in log.read_text(encoding="utf-8")


def test_new_public_surface_with_a_survey_passes(tmp_path: Path) -> None:
    project = _feature_repo(
        tmp_path / "surveyed",
        {
            "src/core.py": "def existing():\n    pass\n\ndef hash_bytes(b):\n    return 0\n",
            "docs/surveys/0001-hashing.md": "# Survey\nLooked: hashlib exists; need bytes API.\n",
        },
    )
    code, stdout, statuses = _gate(project)
    assert code == 0, stdout
    assert statuses.get("17_prior_art") == "pass"


def test_change_adding_no_public_surface_is_noop(tmp_path: Path) -> None:
    """A refactor with nothing new to survey: the gate looked, found no question."""
    project = _feature_repo(
        tmp_path / "refactor",
        {"src/core.py": "def existing():\n    return None\n\ndef _helper():\n    pass\n"},
    )
    code, stdout, statuses = _gate(project)
    assert code == 0, stdout
    assert statuses.get("17_prior_art") == "noop"
    assert "inspected NOTHING" in stdout


def test_unreadable_config_fails_closed_not_noop(tmp_path: Path) -> None:
    """A broken spine must never read as 'nothing to inspect'."""
    project = _feature_repo(tmp_path / "p", {"src/new_mod.py": "def brand_new():\n    pass\n"})
    (project / "borromeanrings.toml").write_text(
        CONFIG + "\n[project]\nsrc_dir = 42\n", encoding="utf-8"
    )
    code, _, statuses = _gate(project)
    assert code != 0
    assert statuses.get("17_prior_art") == "fail"
