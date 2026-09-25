"""`06_git_identity` end to end: what it requires, and what it refuses to guess (#229).

The check demanded that a commit's *display name* match the declared one. Every commit
on `dev` carries the right address and the name "Imaan", because GitHub stamps a squash
merge with the account's profile name and no local `user.name` survives that. So the
check could never pass on this project's own trunk, and it was quietly dropped from the
required set: work done, signal discarded.

The address is the durable identity and the one a project actually specifies, so that is
what is required by default; a project that controls how its commits are made can ask for
the name too (`[git].require = "email+name"`).

The second half is #186's: the authors are read with `git log`, and a `git log` that
FAILS must never read as "no commits to attribute" — the verdict is computed entirely
from that list, so an empty one from a broken repository would print "identity OK" over
commits nobody read.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
GATE_TIMEOUT_S = 300

DECLARED_EMAIL = "maintainer@example.com"
DECLARED_NAME = "wimaan3"


def _config(require: str | None = None, declared_email: str = DECLARED_EMAIL) -> str:
    rule = f'require = "{require}"\n' if require else ""
    return (
        '[project]\nlanguage = "none"\n\n'
        f'[git]\nname = "{DECLARED_NAME}"\nemail = "{declared_email}"\n{rule}\n'
        '[checks]\nrequired = ["06_git_identity"]\n'
    )


def _commit(project: Path, name: str, email: str, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=project, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", f"user.name={name}", "-c", f"user.email={email}", "commit", "-qm", message],
        cwd=project,
        check=True,
        capture_output=True,
    )


def _project(tmp_path: Path, config: str) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "borromeanrings.toml").write_text(config, encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project, check=True)
    subprocess.run(["git", "config", "maintenance.auto", "false"], cwd=project, check=True)
    _commit(project, DECLARED_NAME, DECLARED_EMAIL, "chore: base")
    return project


def _branch_commit(project: Path, name: str, email: str) -> None:
    subprocess.run(["git", "checkout", "-q", "-b", "feat/x"], cwd=project, check=True)
    (project / "change.txt").write_text("x\n", encoding="utf-8")
    _commit(project, name, email, "feat: x")


def _gate(project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(VERIFY)],
        cwd=project,
        env={**os.environ, "BORROMEANRINGS_PROJECT": str(project)},
        capture_output=True,
        text=True,
        timeout=GATE_TIMEOUT_S,
    )


def _receipt(project: Path) -> tuple[str, str]:
    run_dir = sorted((project / ".meta-harness" / "receipts").glob("*/"))[-1]
    status = json.loads((run_dir / "06_git_identity.json").read_text(encoding="utf-8"))["status"]
    return status, (run_dir / "06_git_identity.log").read_text(encoding="utf-8", errors="replace")


def test_the_squash_merge_display_name_is_not_a_violation(tmp_path: Path) -> None:
    """The exact shape that made this check unpassable on dev: the address is the
    declared one, the name is whatever the merging host stamped."""
    project = _project(tmp_path, _config())
    _branch_commit(project, "Imaan", DECLARED_EMAIL)

    proc = _gate(project)
    status, log = _receipt(project)

    assert status == "pass", log
    assert proc.returncode == 0, proc.stdout


def test_a_commit_from_another_account_still_fails(tmp_path: Path) -> None:
    """What the check is for: provenance. The email is the thing being asserted."""
    project = _project(tmp_path, _config())
    _branch_commit(project, DECLARED_NAME, "someone@else.example")

    proc = _gate(project)
    status, log = _receipt(project)

    assert status == "fail", log
    assert proc.returncode != 0
    assert "someone@else.example" in log


def test_a_project_can_require_the_display_name_too(tmp_path: Path) -> None:
    project = _project(tmp_path, _config(require="email+name"))
    _branch_commit(project, "Imaan", DECLARED_EMAIL)

    proc = _gate(project)
    status, log = _receipt(project)

    assert status == "fail", log
    assert proc.returncode != 0
    assert "Imaan" in log


def test_an_unknown_requirement_refuses_the_run(tmp_path: Path) -> None:
    """A typo must not silently relax what is enforced: the gate refuses before any
    check runs, the way it does for an unknown language."""
    project = _project(tmp_path, _config(require="name"))

    proc = _gate(project)

    assert proc.returncode != 0
    assert "[git].require" in proc.stdout + proc.stderr
    assert "refusing to run" in proc.stderr
    assert "not a rule" in proc.stderr and "email+name" in proc.stderr


def test_declaring_no_identity_inspects_nothing_and_says_so(tmp_path: Path) -> None:
    """ADR-0049: "not enforced" must never be indistinguishable from "every commit was
    checked and is right". It was a `pass`; it is a `noop`."""
    project = _project(
        tmp_path, '[project]\nlanguage = "none"\n\n[checks]\nrequired = ["06_git_identity"]\n'
    )
    _branch_commit(project, "anyone", "anyone@example.com")

    proc = _gate(project)
    status, log = _receipt(project)

    assert status == "noop", log
    assert proc.returncode == 0
    assert "nothing to attribute" in log


def test_a_failed_git_log_fails_closed_rather_than_attributing_nothing(tmp_path: Path) -> None:
    """#186: the verdict is computed from the author list, so a git failure that yields
    an empty one would print "identity OK" over commits nobody read."""
    project = _project(tmp_path, _config())
    _branch_commit(project, DECLARED_NAME, "someone@else.example")
    # An emptied object store: `git log` fails ("bad object"), while
    # `rev-parse --is-inside-work-tree` still says this is a repository.
    # `missing_ok`: git's background maintenance writes and removes files under
    # .git/objects while this walks, which failed one CI run as a race in the test.
    for obj in (project / ".git" / "objects").rglob("*"):
        if obj.is_file():
            obj.unlink(missing_ok=True)

    proc = _gate(project)
    status, log = _receipt(project)

    assert status == "fail", log
    assert proc.returncode != 0
    assert "could not read" in log
