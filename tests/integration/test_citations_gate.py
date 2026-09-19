"""End-to-end: the real gate rejects a branch whose docs cite what it does not contain.

The unit tests pin the extractor's decisions; these run `verify.sh` itself against fixture
repositories, so the parts no pure function can cover are exercised for real — the config
switch, the merge-base diff, resolution against git-tracked paths, and every fail-closed
edge. Each fixture is a two-commit repository: a `main` baseline, then a feature branch
that changes documentation.

See docs/specs/SPEC-citations.md and ADR-0073.
"""

import json
import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
GATE_TIMEOUT_S = 120

# language = "none" selects a per-language check dir that does not exist, so only the
# shared checks run: this fixture is about 26_citations, not about pytest or ruff.
CONFIG = (
    '[project]\nlanguage = "none"\nsrc_dir = "src"\n\n'
    '[checks]\nrequired = ["26_citations"]\n\n'
    "[hygiene]\nrequires = []\n\n"
    "[citations]\nenabled = true\n"
)
CONFIG_OFF = CONFIG.replace("enabled = true", "enabled = false")
CONFIG_BROKEN = CONFIG + "paths = 5\n"

BASELINE = {
    "README.md": "# Fixture\n\nSee `docs/GUIDE.md`.\n",
    "docs/GUIDE.md": "# Guide\n\n## A real section\n\nNothing yet.\n",
}


def _git(root: Path, *argv: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *argv],
        cwd=root,
        capture_output=True,
        check=False,
    )


def _write(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")


def _project(
    root: Path,
    branch_files: dict[str, str],
    *,
    config: str = CONFIG,
    removed: tuple[str, ...] = (),
    untracked: dict[str, str] | None = None,
) -> Path:
    """A repo with a `main` baseline and a feature branch that changes documentation.

    ``untracked`` files are written **after** the commit and never added, so they exist on
    disk but not on the branch — the distinction the resolver is built on.
    """
    root.mkdir(parents=True)
    _write(root, {"borromeanrings.toml": config, **BASELINE})
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "baseline")
    _git(root, "branch", "-M", "main")
    _git(root, "checkout", "-q", "-b", "feat/docs")
    _write(root, branch_files)
    for rel in removed:
        (root / rel).unlink()
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "docs: change")
    if untracked:
        _write(root, untracked)
    return root


def _run_gate(project: Path) -> tuple[int, str, str, str]:
    """Run the real gate; return (exit code, stdout, 26_citations status, its log)."""
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(project)
    proc = subprocess.run(
        ["bash", str(VERIFY)],
        env=env,
        capture_output=True,
        text=True,
        timeout=GATE_TIMEOUT_S,
    )
    runs = sorted(p for p in (project / ".meta-harness" / "receipts").glob("*") if p.is_dir())
    status, log = "MISSING", ""
    if runs:
        receipt = runs[-1] / "26_citations.json"
        if receipt.exists():
            status = json.loads(receipt.read_text()).get("status", "?")
        log_path = runs[-1] / "26_citations.log"
        if log_path.exists():
            log = log_path.read_text(encoding="utf-8")
    return proc.returncode, proc.stdout, status, log


def test_off_unless_the_project_declares_the_rule(tmp_path: Path) -> None:
    """No `[citations].enabled` ⇒ the check reports `noop`, never a `pass`.

    "I inspected nothing" and "I inspected everything" must stay distinguishable even
    when the answer is green (ADR-0049).
    """
    project = _project(
        tmp_path / "off", {"docs/NEW.md": "See `docs/NOWHERE.md`.\n"}, config=CONFIG_OFF
    )
    code, stdout, status, log = _run_gate(project)
    assert code == 0, stdout
    assert status == "noop"
    assert "[citations].enabled is not set" in log


def test_a_branch_that_changed_no_documentation_is_a_noop(tmp_path: Path) -> None:
    project = _project(tmp_path / "nodocs", {"src/mod.py": "X = 1\n"})
    code, stdout, status, log = _run_gate(project)
    assert code == 0, stdout
    assert status == "noop"
    assert "no changed Markdown under [citations].paths" in log


def test_resolving_citations_pass(tmp_path: Path) -> None:
    """Every citation kind, all resolvable on this branch: paths, an anchor, and a link."""
    project = _project(
        tmp_path / "clean",
        {
            "docs/NEW.md": (
                "# New\n\n"
                "Prose cites `docs/GUIDE.md` and `README.md`.\n"
                "An anchor: `docs/GUIDE.md#a-real-section`.\n"
                "A link: [guide](GUIDE.md).\n"
            )
        },
    )
    code, stdout, status, log = _run_gate(project)
    assert code == 0, stdout
    assert status == "pass"
    assert "every citation resolves on this branch" in log


def test_a_dead_citation_fails_and_names_file_and_line(tmp_path: Path) -> None:
    """The defect from PR #184, reproduced: a doc citing a file that is on another branch."""
    project = _project(
        tmp_path / "dead",
        {
            "docs/NEW.md": (
                "# New\n\n"
                "The rule is restated in `docs/HANDOFF.md` section 3.\n"
                "The anchor `docs/GUIDE.md#no-such-section` is dead too.\n"
            )
        },
    )
    code, stdout, status, log = _run_gate(project)
    assert code != 0, f"a branch citing what it does not contain must FAIL:\n{stdout}"
    assert status == "fail"
    assert "docs/NEW.md:3 — docs/HANDOFF.md — does not exist on this branch" in log
    assert "docs/NEW.md:4 — docs/GUIDE.md#no-such-section — does not exist on this branch" in log


def test_a_labelled_forward_reference_is_allowed(tmp_path: Path) -> None:
    """The same dead citation, labelled in the one recognised form, passes."""
    project = _project(
        tmp_path / "labelled",
        {"docs/NEW.md": "# New\n\nRestated in `docs/HANDOFF.md` (lands with #147).\n"},
    )
    code, stdout, status, log = _run_gate(project)
    assert code == 0, stdout
    assert status == "pass"


def test_a_citation_in_a_deleted_document_is_ignored(tmp_path: Path) -> None:
    """A branch REMOVING a document is withdrawing its claims, not making them."""
    project = _project(
        tmp_path / "deleted",
        {"docs/GUIDE.md": "# Guide\n\nSee `docs/GONE.md`.\n", "docs/NEW.md": "# New\n"},
        removed=(),
    )
    # Rewrite history so the dead citation exists only in a file this branch deletes.
    (project / "docs" / "DOOMED.md").write_text("See `docs/GONE.md`.\n", encoding="utf-8")
    _git(project, "add", "-A")
    _git(project, "commit", "-qm", "docs: add doomed")
    (project / "docs" / "DOOMED.md").unlink()
    (project / "docs" / "GUIDE.md").write_text(
        "# Guide\n\n## A real section\n\nNothing.\n", encoding="utf-8"
    )
    _git(project, "add", "-A")
    _git(project, "commit", "-qm", "docs: delete doomed")
    code, stdout, status, log = _run_gate(project)
    assert code == 0, f"a deleted document's citations must not gate:\n{stdout}\n{log}"
    assert status == "pass"


def test_a_file_present_but_untracked_does_not_satisfy_a_citation(tmp_path: Path) -> None:
    """Resolution is against the BRANCH, not the working directory.

    The file is right there on disk, so a filesystem-based resolver would pass this. It is
    not on the branch, so a reader who checks the branch out finds nothing — and neither
    does anyone reading the PR. Untracked scratch must never be able to satisfy a claim.
    """
    project = _project(
        tmp_path / "untracked",
        {"docs/NEW.md": "# New\n\nSee `docs/SCRATCH.md`.\n"},
        untracked={"docs/SCRATCH.md": "# Scratch\n\nPresent on disk, absent from git.\n"},
    )
    assert (project / "docs" / "SCRATCH.md").exists(), "fixture must leave the file present"
    listed = subprocess.run(
        ["git", "ls-files", "docs/SCRATCH.md"],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    assert listed.stdout.strip() == "", "fixture must leave the file untracked"

    code, stdout, status, log = _run_gate(project)
    assert code != 0, f"an untracked file must not satisfy a citation:\n{stdout}"
    assert status == "fail"
    assert "docs/NEW.md:3 — docs/SCRATCH.md — does not exist on this branch" in log


def test_an_unreadable_citations_config_fails_closed(tmp_path: Path) -> None:
    """A `[citations]` section the spine cannot parse must FAIL, never quietly `noop`.

    A `noop` there would report green for a check that never ran — precisely the
    hollow-green this repository exists to prevent.
    """
    project = _project(
        tmp_path / "brokencfg", {"docs/NEW.md": "See `docs/GUIDE.md`.\n"}, config=CONFIG_BROKEN
    )
    code, stdout, status, log = _run_gate(project)
    assert code != 0, f"an unreadable config must fail closed:\n{stdout}"
    assert status == "fail"
    assert "failing closed" in log
