"""``adopt.sh`` upgrades an already-governed project without clobbering it.

The fourth portability entry point (#128): it rewrites ``[checks].required`` in place,
seeds ratchet baselines from CURRENT state so the first gate after adopting is green, and
refreshes skills. It edits other people's config, in place — the seam both field bugs
came from. Every test here is verified to fail if the behaviour it describes regresses.
"""

import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
ADOPT = BORROMEANRINGS_HOME / "adopt.sh"
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
TIMEOUT_S = 180

# A founding-baseline config: governed, but none of the recommended set yet.
BASELINE = (
    '[project]\nlanguage = "python"\npackage = "pkg"\nsrc_dir = "src"\ntests_dir = "tests"\n\n'
    "# tuned by hand -- must survive\n"
    '[checks]\nrequired = ["00_build", "10_format"]\n\n[hygiene]\nrequires = []\n'
)


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, cwd=cwd, capture_output=True, text=True, check=False, timeout=TIMEOUT_S
    )


def _governed(root: Path) -> Path:
    root.mkdir()
    (root / "borromeanrings.toml").write_text(BASELINE, encoding="utf-8")
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "src" / "pkg" / "__init__.py").write_text('"""pkg."""\n', encoding="utf-8")
    (root / "src" / "pkg" / "m.py").write_text(
        '"""m."""\n\n\ndef f() -> int:\n    """f."""\n    return 1\n', encoding="utf-8"
    )
    _run(["git", "init", "-q"], root)
    for k, v in (("user.email", "t@t"), ("user.name", "t")):
        _run(["git", "config", k, v], root)
    _run(["git", "add", "-A"], root)
    _run(["git", "commit", "-qm", "init"], root)
    return root


def _adopt(project: Path) -> subprocess.CompletedProcess[str]:
    return _run(["bash", str(ADOPT), str(project)], project)


def test_adopt_adds_the_recommended_set_and_preserves_tuned_config(tmp_path: Path) -> None:
    project = _governed(tmp_path / "p")
    assert _adopt(project).returncode == 0
    toml = (project / "borromeanrings.toml").read_text(encoding="utf-8")
    assert "# tuned by hand -- must survive" in toml, "adopt clobbered the owner's config"
    assert '"00_build"' in toml and '"10_format"' in toml, "existing required checks were dropped"
    assert "[hygiene]\nrequires = []" in toml, "an unrelated section was rewritten"
    from meta_harness.adopt import RECOMMENDED

    for check in RECOMMENDED:
        assert f'"{check}"' in toml, f"{check} not added"


def test_adopt_seeds_ratchet_baselines_from_current_state(tmp_path: Path) -> None:
    """A ratchet without a baseline is vacuous; seeded from current, it holds the line."""
    project = _governed(tmp_path / "p")
    _adopt(project)
    from meta_harness.adopt import RATCHET_BASELINES

    for check, filename in RATCHET_BASELINES.items():
        path = project / filename
        assert path.is_file(), f"{check}: baseline {filename} not seeded"
        assert path.read_text(encoding="utf-8").strip(), f"{filename} is empty"


def test_first_gate_after_adopting_is_green(tmp_path: Path) -> None:
    """The acceptance criterion: adopting must not start a project red."""
    project = _governed(tmp_path / "p")
    _adopt(project)
    _run(["git", "add", "-A"], project)
    _run(["git", "commit", "-qm", "chore: adopt"], project)
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(project)
    result = subprocess.run(
        ["bash", str(VERIFY)], env=env, capture_output=True, text=True, timeout=TIMEOUT_S
    )
    assert result.returncode == 0, f"gate red right after adopt:\n{result.stdout}"


def test_adopt_is_idempotent(tmp_path: Path) -> None:
    project = _governed(tmp_path / "p")
    _adopt(project)
    first = (project / "borromeanrings.toml").read_text(encoding="utf-8")
    second_run = _adopt(project)
    assert "nothing to do" in second_run.stdout
    assert (project / "borromeanrings.toml").read_text(encoding="utf-8") == first


def test_adopt_creates_a_changelog_only_when_missing(tmp_path: Path) -> None:
    project = _governed(tmp_path / "p")
    _adopt(project)
    assert (project / "CHANGELOG.md").is_file()
    marker = "# my changelog\n"
    (project / "CHANGELOG.md").write_text(marker, encoding="utf-8")
    _adopt(project)
    assert (project / "CHANGELOG.md").read_text(encoding="utf-8") == marker, (
        "an existing changelog was overwritten"
    )


def test_adopt_refreshes_skills_to_match_the_harness(tmp_path: Path) -> None:
    """Refresh means: every skill the harness ships is present, and a stale copy is
    brought back to the harness's content on the next run (the reason adopt.sh copies)."""
    project = _governed(tmp_path / "p")
    _adopt(project)
    source = BORROMEANRINGS_HOME / ".claude" / "skills"
    shipped = sorted(p.name for p in source.iterdir() if p.is_dir())
    assert shipped, "fixture assumption: the harness ships at least one skill"
    installed = project / ".claude" / "skills"
    assert sorted(p.name for p in installed.iterdir() if p.is_dir()) == shipped
    doc = installed / shipped[0] / "SKILL.md"
    original = doc.read_text(encoding="utf-8")
    doc.write_text("stale\n", encoding="utf-8")
    _adopt(project)
    assert doc.read_text(encoding="utf-8") == original, "a stale skill was not refreshed"


def test_adopt_refuses_an_ungoverned_directory(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    result = _adopt(plain)
    assert result.returncode != 0
    assert "not borromeanRings-governed" in (result.stdout + result.stderr)
