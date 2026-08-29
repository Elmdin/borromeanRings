"""``merge.sh`` merges the GOVERNED project, not borromeanRings itself.

The bug this locks down (#121) was found in the field while bootstrapping governance on
another repo: ``merge.sh`` unconditionally ``cd``-ed into borromeanRings's own directory,
so invoking it from a governed project checked *borromeanRings's* working tree for
dirtiness and would have merged *borromeanRings's* branches. Wrong repository entirely.

``verify.sh`` has always honoured ``BORROMEANRINGS_PROJECT``; ``merge.sh`` had not.
"""

import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
MERGE = BORROMEANRINGS_HOME / "merge.sh"
TIMEOUT_S = 180

# A project gated on one cheap, always-satisfiable check, so the test exercises merge
# scoping rather than the check suite.
CONFIG = (
    '[project]\nlanguage = "python"\nsrc_dir = "src"\n\n'
    '[checks]\nrequired = ["05_hygiene"]\n\n[hygiene]\nrequires = []\n'
)


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False)


def _governed_repo_with_origin(tmp_path: Path) -> tuple[Path, Path]:
    """A project repo on a feature branch, wired to a local bare 'origin'."""
    origin = tmp_path / "origin.git"
    origin.mkdir()
    _run(["git", "init", "--bare", "-q", "-b", "main", str(origin)], tmp_path)

    work = tmp_path / "project"
    work.mkdir()
    _run(["git", "init", "-q", "-b", "main"], work)
    for key, value in (("user.email", "t@t"), ("user.name", "t")):
        _run(["git", "config", key, value], work)
    (work / "borromeanrings.toml").write_text(CONFIG, encoding="utf-8")
    _run(["git", "add", "-A"], work)
    _run(["git", "commit", "-qm", "init"], work)
    _run(["git", "remote", "add", "origin", str(origin)], work)
    _run(["git", "push", "-q", "-u", "origin", "main"], work)

    _run(["git", "checkout", "-q", "-b", "feat/change"], work)
    (work / "feature.txt").write_text("added by the feature branch\n", encoding="utf-8")
    _run(["git", "add", "-A"], work)
    _run(["git", "commit", "-qm", "feat: add feature file"], work)
    return work, origin


def test_merge_operates_on_the_governed_project_not_the_harness(tmp_path: Path) -> None:
    work, _ = _governed_repo_with_origin(tmp_path)
    harness_branch_before = _run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], BORROMEANRINGS_HOME
    ).stdout.strip()

    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(work)
    env["PATH"] = "/nonexistent-so-gh-is-absent:" + env["PATH"]  # force the plain-git path
    proc = subprocess.run(
        ["bash", str(MERGE), "main"],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_S,
    )

    assert proc.returncode == 0, f"merge failed:\n{proc.stdout}\n{proc.stderr}"

    # The PROJECT's main now carries the feature commit ...
    merged = _run(["git", "log", "--oneline", "main"], work).stdout
    assert "add feature file" in merged, merged

    # ... and borromeanRings itself was never touched.
    harness_branch_after = _run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], BORROMEANRINGS_HOME
    ).stdout.strip()
    assert harness_branch_after == harness_branch_before

    # The audit receipt belongs to the merged project, not the harness.
    assert list((work / ".meta-harness" / "merges").glob("*.json"))


def test_refuses_when_the_target_is_not_governed(tmp_path: Path) -> None:
    """Without a borromeanrings.toml there is no policy to merge under — refuse."""
    plain = tmp_path / "plain"
    plain.mkdir()
    _run(["git", "init", "-q", "-b", "main"], plain)
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(plain)
    proc = subprocess.run(
        ["bash", str(MERGE)], cwd=plain, env=env, capture_output=True, text=True, timeout=TIMEOUT_S
    )
    assert proc.returncode != 0
    assert "not governed" in (proc.stdout + proc.stderr)
