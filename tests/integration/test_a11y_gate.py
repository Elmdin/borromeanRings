"""End-to-end: ``15_a11y`` never reports a hollow green (ADR-0049, #154).

The check walks the project's tracked HTML. Before this suite, a project with **no**
HTML at all wrote a ``pass`` receipt — an a11y green that proved nothing, exactly the
indistinguishable "inspected nothing" vs "inspected everything, all clean" that
ADR-0049 introduced ``noop`` to separate. These tests run the real ``verify.sh`` on
fixture projects and pin the three outcomes:

* **no HTML** — gate green, receipt ``noop``, hollowness surfaced in the gate output;
* **clean HTML** — a real ``pass``;
* **violating HTML** — ``fail``, unchanged.
"""

import json
import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
GATE_TIMEOUT_S = 120

CONFIG = (
    '[project]\nlanguage = "python"\nsrc_dir = "src"\n\n'
    '[checks]\nrequired = ["15_a11y"]\n\n[hygiene]\nrequires = []\n'
)
CLEAN_HTML = (
    '<!DOCTYPE html>\n<html lang="en"><head><title>Home</title></head>\n'
    '<body><img src="a.png" alt="a logo"></body></html>\n'
)
BAD_HTML = '<!DOCTYPE html>\n<html><head></head><body><img src="a.png"></body></html>\n'


def _run_gate(project: Path) -> tuple[int, str, dict[str, str]]:
    """Run the real gate against ``project``; return (exit, stdout, {check: status})."""
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(project)
    proc = subprocess.run(
        ["bash", str(VERIFY)],
        env=env,
        capture_output=True,
        text=True,
        timeout=GATE_TIMEOUT_S,
    )
    statuses: dict[str, str] = {}
    run_dirs = sorted(p for p in (project / ".meta-harness" / "receipts").glob("*") if p.is_dir())
    if run_dirs:
        for receipt in run_dirs[-1].glob("*.json"):
            try:
                statuses[receipt.stem] = json.loads(receipt.read_text()).get("status", "?")
            except (OSError, json.JSONDecodeError):
                statuses[receipt.stem] = "?"
    return proc.returncode, proc.stdout, statuses


def _git_project(root: Path, files: dict[str, str]) -> Path:
    """Materialize a real git repo so 'tracked HTML' is meaningful."""
    for rel, content in files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    for argv in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
    ):
        subprocess.run(argv, cwd=root, capture_output=True, check=False)
    return root


def _a11y_log(project: Path) -> str:
    return next((project / ".meta-harness" / "receipts").glob("*/15_a11y.log")).read_text(
        encoding="utf-8"
    )


def test_project_without_html_is_green_but_reported_as_noop(tmp_path: Path) -> None:
    """No HTML is legitimate (not a UI project) — but never a claim that a11y was checked."""
    project = _git_project(
        tmp_path / "nohtml",
        {"borromeanrings.toml": CONFIG, "src/mod.py": "def f() -> None:\n    pass\n"},
    )
    code, stdout, statuses = _run_gate(project)
    assert code == 0, stdout
    assert statuses.get("15_a11y") == "noop"
    # The hollowness is surfaced in the gate output, not buried in a log.
    assert "inspected NOTHING: 1 of" in stdout
    # The log says what was searched and where, so the reader can tell why.
    log = _a11y_log(project)
    assert "*.html" in log and "git-tracked" in log
    assert "node_modules" in log  # the exclusions applied to the walk


def test_clean_html_is_a_real_pass(tmp_path: Path) -> None:
    """Negative control: HTML that satisfies every invariant is a pass, not a noop."""
    project = _git_project(
        tmp_path / "clean", {"borromeanrings.toml": CONFIG, "site/index.html": CLEAN_HTML}
    )
    code, stdout, statuses = _run_gate(project)
    assert code == 0, stdout
    assert statuses.get("15_a11y") == "pass"
    assert "inspected NOTHING" not in stdout


def test_violating_html_fails_the_gate(tmp_path: Path) -> None:
    """Missing lang / alt / title is rejected, and the log names each violation."""
    project = _git_project(
        tmp_path / "bad", {"borromeanrings.toml": CONFIG, "site/index.html": BAD_HTML}
    )
    code, stdout, statuses = _run_gate(project)
    assert code != 0, f"HTML violating a11y invariants must FAIL:\n{stdout}"
    assert statuses.get("15_a11y") == "fail"
    log = _a11y_log(project)
    for rule in ("html_lang", "img_alt", "page_title"):
        assert rule in log, log


def _plain_project(root: Path, files: dict[str, str]) -> Path:
    """A project that is NOT a git repository — "tracked" has no meaning here."""
    for rel, content in files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    return root


def test_unreadable_git_index_fails_closed_rather_than_noop(tmp_path: Path) -> None:
    """A git failure inside a real repo must FAIL, never masquerade as "no HTML".

    ``git ls-files`` erroring is not the same as ``git ls-files`` returning nothing. If
    the check treated them alike, a transient git error would turn violating HTML into
    a green ``noop`` (the 12_secrets doctrine, ADR-0042: never answer from worse evidence).
    """
    project = _git_project(
        tmp_path / "brokenindex", {"borromeanrings.toml": CONFIG, "site/index.html": BAD_HTML}
    )
    (project / ".git" / "index").write_text("GARBAGE-NOT-AN-INDEX", encoding="utf-8")
    code, stdout, statuses = _run_gate(project)
    assert code != 0, f"an undecidable git state must fail closed:\n{stdout}"
    assert statuses.get("15_a11y") == "fail"
    assert "failing closed" in _a11y_log(project)


def test_non_git_project_with_violations_fails(tmp_path: Path) -> None:
    """Not a git repo ⇒ filesystem walk; violating HTML found that way still FAILS."""
    project = _plain_project(
        tmp_path / "nogit",
        {
            "borromeanrings.toml": CONFIG,
            "site/index.html": BAD_HTML,
            "node_modules/pkg/x.html": BAD_HTML,  # excluded — must not be counted
        },
    )
    code, stdout, statuses = _run_gate(project)
    assert code != 0, f"violating HTML in a non-git project must FAIL:\n{stdout}"
    assert statuses.get("15_a11y") == "fail"
    log = _a11y_log(project)
    assert "site/index.html" in log
    assert "node_modules" not in log


def test_non_git_project_without_html_is_noop(tmp_path: Path) -> None:
    """The walk fallback, finding nothing, is still an honest noop — not a pass."""
    project = _plain_project(
        tmp_path / "nogit-empty",
        {"borromeanrings.toml": CONFIG, "src/mod.py": "def f() -> None:\n    pass\n"},
    )
    code, stdout, statuses = _run_gate(project)
    assert code == 0, stdout
    assert statuses.get("15_a11y") == "noop"
