"""A check that runs and fails outside the required set must say so, not vanish (#229).

Every check script in a lane runs; only `[checks].required` (and `heavy` under
`--heavy`) decides the verdict. A non-required check that FAILS still writes its `fail`
receipt, but the summary listed only the expected set, so the run directory and the
verdict disagreed about what happened, and the verdict is the one people read. The
failure is now printed on an advisory line, and it still does not decide the verdict.
"""

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VERIFY = REPO / "verify.sh"

CONFIG = """\
[project]
language = "none"

[git]
name = "declared"
email = "declared@example.com"

[checks]
required = ["05_hygiene"]

[hygiene]
requires = []
"""


def _git(project: Path, *args: str, author: str = "declared <declared@example.com>") -> None:
    name, email = author[: author.index(" <")], author[author.index("<") + 1 : -1]
    subprocess.run(
        ["git", "-c", f"user.name={name}", "-c", f"user.email={email}", *args],
        cwd=project,
        capture_output=True,
        check=True,
    )


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "borromeanrings.toml").write_text(CONFIG, encoding="utf-8")
    _git(project, "init", "-q", "-b", "main")
    _git(project, "add", "-A")
    _git(project, "commit", "-qm", "chore: base")
    _git(project, "checkout", "-q", "-b", "feat/x")
    (project / "change.txt").write_text("x\n", encoding="utf-8")
    _git(project, "add", "-A")
    # A commit by someone other than the declared identity: 06_git_identity fails on it.
    _git(project, "commit", "-qm", "feat: x", author="someone <someone@example.com>")
    return project


def _gate(project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(VERIFY)],
        cwd=project,
        env={**os.environ, "BORROMEANRINGS_PROJECT": str(project)},
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_a_failing_check_outside_the_required_set_is_reported_as_advisory(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    proc = _gate(project)

    # The premise: the identity check really ran and really failed, off the record.
    receipts = sorted((project / ".meta-harness" / "receipts").glob("*/06_git_identity.json"))
    assert receipts and '"status": "fail"' in receipts[-1].read_text(encoding="utf-8")

    # It does not decide the verdict ...
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "RESULT: PASS" in proc.stdout
    # ... but the verdict no longer pretends it did not happen.
    assert "advisory — not required, did not decide the verdict: 06_git_identity (fail)" in (
        proc.stdout
    ), proc.stdout


def test_a_passing_run_with_no_advisory_failure_prints_no_advisory_line(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _git(project, "commit", "--amend", "-q", "--no-edit", "--reset-author")  # declared author

    proc = _gate(project)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "advisory" not in proc.stdout
