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

    # Force the plain-git merge path deterministically. Prepending a bogus PATH entry
    # does NOT work — `gh` is still found further along PATH, so the test would pass for
    # an incidental reason (the fixture has no GitHub remote) rather than the stated one.
    # A stub that always fails makes `command -v gh && gh pr view ...` take the git path
    # for exactly the reason the comment claims.
    stub_bin = tmp_path / "stub-bin"
    stub_bin.mkdir()
    gh_stub = stub_bin / "gh"
    gh_stub.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    gh_stub.chmod(0o755)

    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(work)
    env["PATH"] = f"{stub_bin}:" + env["PATH"]
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

    # The audit receipt belongs to the merged project, not the harness, and records the
    # merge commit this path actually produced.
    receipts = list((work / ".meta-harness" / "merges").glob("*.json"))
    assert receipts
    import json

    record = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert record["merge_commit_sha"], "the local-git path must record its merge commit"
    local_head = _run(["git", "rev-parse", "main"], work).stdout.strip()
    assert record["merge_commit_sha"] == local_head


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


# --- preconditions: merge.sh refuses before it can do damage (issue #53) --------------


def _merge(work: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run merge.sh against ``work`` with gh forced to fail (plain-git path)."""
    stub_bin = work.parent / "stub-bin"
    stub_bin.mkdir(exist_ok=True)
    gh_stub = stub_bin / "gh"
    gh_stub.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    gh_stub.chmod(0o755)
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(work)
    env["PATH"] = f"{stub_bin}:" + env["PATH"]
    return subprocess.run(
        ["bash", str(MERGE), *args],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_S,
        check=False,
    )


def test_refuses_a_dirty_working_tree(tmp_path: Path) -> None:
    """Merging an uncommitted tree would merge something nobody reviewed."""
    work, _ = _governed_repo_with_origin(tmp_path)
    (work / "scratch.txt").write_text("uncommitted\n", encoding="utf-8")
    proc = _merge(work, "main")
    assert proc.returncode != 0
    assert "dirty" in (proc.stdout + proc.stderr)


def test_refuses_when_already_on_the_base_branch(tmp_path: Path) -> None:
    """There is nothing to merge, and proceeding would be a no-op with side effects."""
    work, _ = _governed_repo_with_origin(tmp_path)
    _run(["git", "checkout", "-q", "main"], work)
    proc = _merge(work, "main")
    assert proc.returncode != 0
    assert "already on" in (proc.stdout + proc.stderr)


def test_refuses_when_the_gate_fails(tmp_path: Path) -> None:
    """The gate is the precondition for merging at all — fail-closed (ADR-0007)."""
    work, _ = _governed_repo_with_origin(tmp_path)
    # Require a check this fixture cannot satisfy: a declared hygiene file that is absent.
    (work / "borromeanrings.toml").write_text(
        '[project]\nlanguage = "python"\nsrc_dir = "src"\n\n'
        '[checks]\nrequired = ["05_hygiene"]\n\n'
        '[hygiene]\nrequires = ["NOT-PRESENT.md"]\n',
        encoding="utf-8",
    )
    _run(["git", "add", "-A"], work)
    _run(["git", "commit", "-qm", "chore: require a missing file"], work)
    proc = _merge(work, "main")
    assert proc.returncode != 0
    assert "REFUSED" in (proc.stdout + proc.stderr)
    # And nothing was merged.
    assert "require a missing file" not in _run(["git", "log", "--oneline", "main"], work).stdout
