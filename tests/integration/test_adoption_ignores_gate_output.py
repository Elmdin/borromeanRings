"""A project set up by borromeanRings must stay clean after the gate runs (#219).

The property that matters is not "the line exists" — it is that the harness's own
output never becomes project content. So these tests run the real ``init.sh``
against a project with **no** ``.gitignore`` at all, then run the real gate, and
assert the working tree is still clean and the secret scanner is still looking at
the project rather than at receipt logs.

Without the entry this fails in a particularly bad way: ``12_secrets`` reads the
git index, ``git add -A`` puts the receipt logs in it, and a check log that quotes
a secret-shaped line makes the secret gate fail on generated files — still failing
after the offending source is deleted.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
INIT = BORROMEANRINGS_HOME / "init.sh"
VERIFY = BORROMEANRINGS_HOME / "verify.sh"

# Fixture data, not a credential. The marker must stay on the SAME line as the
# literal — keep this short enough that `ruff format` never wraps it away.
_KEY_BLOCK = "-----BEGIN RSA PRIVATE KEY-----"  # borromeanrings: allow-secret


def _git(project: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout


def _project(tmp_path: Path, *, secret: str | None = None) -> Path:
    project = tmp_path / "governed"
    (project / "src" / "demo").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "pyproject.toml").write_text('[project]\nname = "demo"\nversion = "0.1"\n')
    (project / "src" / "demo" / "__init__.py").write_text('"""demo."""\n')
    (project / "tests" / "test_ok.py").write_text('"""t."""\n\n\ndef test_ok():\n    assert True\n')
    if secret is not None:
        (project / "src" / "demo" / "creds.py").write_text(f'"""c."""\n\nK = "{secret}"\n')
    # init.sh's default required set does not include 12_secrets (see #230), and
    # this module is about the ignore entry, not about that default — so ask for
    # the checks under test explicitly. init.sh leaves an existing config alone.
    (project / "borromeanrings.toml").write_text(
        '[project]\npackage = "demo"\nsrc_dir = "src"\ntests_dir = "tests"\n\n'
        '[checks]\nrequired = ["00_build", "12_secrets", "40_test"]\n\n'
        "[hygiene]\nrequires = []\n",
        encoding="utf-8",
    )
    _git(project, "init")
    assert not (project / ".gitignore").exists()  # the case the acceptance names
    return project


def _init(project: Path, *flags: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(INIT), *flags, str(project)],
        capture_output=True,
        text=True,
        timeout=120,
    )


def _gate(project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(VERIFY)],
        env={**dict(__import__("os").environ), "BORROMEANRINGS_PROJECT": str(project)},
        capture_output=True,
        text=True,
        timeout=600,
    )


def test_a_project_with_no_gitignore_stays_clean_after_the_gate(tmp_path: Path) -> None:
    project = _project(tmp_path)
    result = _init(project)
    assert result.returncode == 0, result.stderr
    assert ".gitignore" in result.stdout  # the write is announced, never silent

    _git(project, "add", "-A")
    _git(project, "commit", "-m", "adopt")
    _gate(project)

    assert (project / ".meta-harness").is_dir()  # the gate really did write there
    untracked = [
        line[3:]
        for line in _git(project, "status", "--porcelain").splitlines()
        if line.startswith("??")
    ]
    # __pycache__ is the project's own business — it gets that from running its own
    # tests. Everything else left here was caused by being gated.
    caused_by_the_gate = [p for p in untracked if "__pycache__" not in p]
    assert caused_by_the_gate == [], caused_by_the_gate


def test_the_secret_gate_never_reads_the_harnesss_own_logs(tmp_path: Path) -> None:
    """The failure this issue was really about: a red secret gate you cannot fix.

    A source file carrying a private-key block is committed, so the FIRST gate run
    fails correctly. Deleting it must make the next run pass — and it only does if
    the check logs that quoted the block are not themselves in the index.
    """
    project = _project(tmp_path, secret=_KEY_BLOCK)
    assert _init(project).returncode == 0
    _git(project, "add", "-A")
    _git(project, "commit", "-m", "adopt")

    assert "12_secrets" in _gate(project).stdout  # the real secret is found

    (project / "src" / "demo" / "creds.py").unlink()
    _git(project, "add", "-A")
    _git(project, "commit", "-m", "remove the secret")

    tracked = _git(project, "ls-files")
    assert ".meta-harness" not in tracked, "the gate's receipts are tracked project content"
    assert "RESULT: PASS" in _gate(project).stdout, "removing the secret did not clear the gate"


def test_no_gitignore_flag_writes_nothing(tmp_path: Path) -> None:
    """The escape hatch is explicit, because 'deliberately absent' cannot be inferred."""
    project = _project(tmp_path)

    result = _init(project, "--no-gitignore")

    assert result.returncode == 0, result.stderr
    assert not (project / ".gitignore").exists()


@pytest.mark.parametrize("existing", ["build/\n*.pyc\n", "build/\n*.pyc"])
def test_an_existing_gitignore_is_preserved(tmp_path: Path, existing: str) -> None:
    project = _project(tmp_path)
    (project / ".gitignore").write_text(existing, encoding="utf-8")

    assert _init(project).returncode == 0

    text = (project / ".gitignore").read_text(encoding="utf-8")
    assert "build/" in text and "*.pyc" in text
    assert ".meta-harness/" in text and ".coverage" in text
    assert text.count(".meta-harness/") == 1
