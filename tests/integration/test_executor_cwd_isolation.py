"""The worktree executor's own Python must not import from the caller's directory.

`run-in-worktree.sh` asks the harness two questions in Python before it gates: what
the project's config says (`project_cfg`) and whether an editable install shadows
the snapshot (`import_shadow_violation`). Both run as `python3 -` heredocs, and for
a stdin script Python puts the CURRENT DIRECTORY on `sys.path` ahead of
`PYTHONPATH`. A `meta_harness/` in the caller's directory — this repo carries a
stale one at its root (#215) — is then imported instead of the harness.

That fails OPEN: a decoy that breaks the import empties `PACKAGE`, which skips the
shadow check entirely, and the gate goes on to report on code it never proved it
was testing. The harness's shell helpers solved this once already
(`borromeanrings_py`, a neutral cwd); the executor must do the same.
"""

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUN_IN_WORKTREE = REPO / "run-in-worktree.sh"

CONFIG = """\
[project]
language = "python"
package = "fixturepkg"
src_dir = "src"
tests_dir = "tests"

[checks]
required = ["05_hygiene"]

[hygiene]
requires = ["README.md"]
"""

DECOY = """\
import os

with open(os.environ["DECOY_MARKER"], "a", encoding="utf-8") as fh:
    fh.write("imported\\n")
raise ImportError("decoy meta_harness imported from the caller's directory")
"""


def _project(root: Path) -> Path:
    project = root / "proj"
    (project / "src" / "fixturepkg").mkdir(parents=True)
    (project / "src" / "fixturepkg" / "__init__.py").write_text('"""Fixture."""\n')
    (project / "README.md").write_text("# proj\n")
    (project / "borromeanrings.toml").write_text(CONFIG)
    for argv in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
    ):
        subprocess.run(argv, cwd=project, capture_output=True, check=True)
    return project


def test_a_meta_harness_in_the_callers_directory_is_never_imported(tmp_path: Path) -> None:
    project = _project(tmp_path)
    caller = tmp_path / "caller"
    (caller / "meta_harness").mkdir(parents=True)
    (caller / "meta_harness" / "__init__.py").write_text(DECOY)
    marker = tmp_path / "decoy-imported"

    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "CLAUDE_PROJECT_DIR")}
    env.update(
        DECOY_MARKER=str(marker),
        BORROMEANRINGS_HEAVY="0",
        BORROMEANRINGS_CHECK_TIMEOUT="120",
    )
    result = subprocess.run(
        ["bash", str(RUN_IN_WORKTREE), "--project", str(project)],
        cwd=caller,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )

    assert not marker.exists(), (
        "the executor imported meta_harness from the caller's directory:\n"
        f"{result.stdout}\n{result.stderr}"
    )
    assert "RECEIPTS: " in result.stdout, result.stderr


def test_a_package_that_cannot_be_located_refuses_rather_than_skipping(tmp_path: Path) -> None:
    """Review of #212: if asking where the package imports from fails, the answer is
    unknown, not "nowhere". An empty ORIGIN read as "not importable, nothing to shadow",
    the same fail-open shape as the config read."""
    project = _project(tmp_path)
    # A DOTTED package: locating `fixturepkg.core` imports its parent, whose __init__
    # raises something the probe does not expect. (A top-level find_spec runs no code.)
    (project / "borromeanrings.toml").write_text(
        CONFIG.replace('package = "fixturepkg"', 'package = "fixturepkg.core"')
    )
    (project / "src" / "fixturepkg" / "core").mkdir()
    (project / "src" / "fixturepkg" / "core" / "__init__.py").write_text('"""Core."""\n')
    init = project / "src" / "fixturepkg" / "__init__.py"
    init.write_text('raise RuntimeError("an import-time failure the probe did not expect")\n')
    subprocess.run(["git", "add", "-A"], cwd=project, capture_output=True, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "boom"],
        cwd=project,
        capture_output=True,
        check=True,
    )
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "CLAUDE_PROJECT_DIR")}
    env.update(BORROMEANRINGS_HEAVY="0", BORROMEANRINGS_CHECK_TIMEOUT="120")
    result = subprocess.run(
        ["bash", str(RUN_IN_WORKTREE), "--project", str(project)],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "could not locate where" in result.stderr
    assert "RECEIPTS: " not in result.stdout
