"""Executor conformance: `worktree` must say exactly what `local` says.

`local` (plain `./verify.sh`) is the reference executor; `worktree`
(`./run-in-worktree.sh`, ADR-0076) is the second implementation of the same
contract. This test is what makes the contract real: it runs the **whole fast
lane** over one fixture project under both executors and compares the two receipt
bundles field by field, logs included, under the equivalence relation in
`meta_harness.executor` (SPEC-executor.md §5, lands with #203).

The fixture is built to *discriminate* — every property the worktree executor
could plausibly get wrong shows up as a receipt difference here:

* it sits on a `feat/` branch whose commit touches `src/`, so `08_branch` names the
  branch in its log and `13_adr` **fails**. A detached snapshot reports its branch as
  `HEAD`: `13_adr` would flip to pass and `08_branch`'s log would name `HEAD`. That
  is G8 — and the cases below prove the other half of it, that the branch identity
  cannot *drift* mid-run either.
* it has an uncommitted edit to a tracked file *and* an untracked file, each with
  its own lint error, so `20_lint`'s log names both — and `40_test`'s
  `coverage_percent` counts the untracked file's lines, so it moves if the file is
  not materialised.
* it has an ignored file (a forged `pass` receipt under `.meta-harness/`) that must
  NOT be materialised — asserted directly against the worktree, and against the
  bundle it is absent from.

Everything the two runs legitimately disagree about — the `log` path, the
`content_sha256` that covers it, the `run_id` in every path, test durations — is
masked by the equivalence relation and by nothing else.

The last group of cases is about a primary that MOVES. A single sequential run
cannot catch a HEAD that follows the primary's branch, and concurrency is the whole
motivation (#144), so those cases commit on the primary — after a run, during a run,
and alongside a second concurrent run — and assert the receipts do not notice.
"""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from meta_harness.executor import canonicalise_log, receipt_differences
from meta_harness.receipts import read_log_text, verify_receipt

REPO = Path(__file__).resolve().parents[2]
VERIFY = REPO / "verify.sh"
RUN_IN_WORKTREE = REPO / "run-in-worktree.sh"

BRANCH = "feat/executor-fixture"
FORGED_RECEIPT = ".meta-harness/receipts/old/20_lint.json"
UNTRACKED = "src/fixturepkg/scratch.py"

CONFIG = """\
[project]
language = "python"
package = "fixturepkg"
src_dir = "src"
tests_dir = "tests"

[collaboration]
protected_branches = ["main"]
branch_patterns = ["feat/*", "fix/*"]
commit_types = ["feat", "fix", "docs", "chore"]
subject_max_length = 72

[hygiene]
requires = ["README.md", "pyproject.toml"]

[checks]
required = [
  "00_build",
  "01_source_coherence",
  "05_hygiene",
  "07_layout",
  "08_branch",
  "09_commits",
  "12_secrets",
  "13_adr",
  "20_lint",
  "30_typecheck",
  "40_test",
  "45_docstrings",
  "50_security",
]
"""

PYPROJECT = """\
[project]
name = "fixturepkg"
version = "0.0.0"

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.coverage.run]
source = ["src"]
branch = true
"""

GITIGNORE = """\
.meta-harness/
mutants/
__pycache__/
.pytest_cache/
.ruff_cache/
.mypy_cache/
.coverage
"""

CORE = '''\
"""The fixture package's only module."""


def shout(text: str) -> str:
    """Return ``text`` in upper case."""
    return text.upper()
'''

# The committed feature change: it touches src/, which is what makes 13_adr
# (feature branch + no ADR) have something to say.
FEATURE = '''\


def whisper(text: str) -> str:
    """Return ``text`` in lower case."""
    return text.lower()
'''

# The UNCOMMITTED edit to a tracked file: an unused import, so ruff (F401) names
# this file. Proves the dirty tree is transported.
DIRTY_EDIT = """\


import calendar  # noqa: E402
"""

# The UNTRACKED file: another unused import, so ruff names it too, and its
# uncovered lines move 40_test's coverage_percent. Proves untracked-not-ignored
# files are transported.
SCRATCH = '''\
"""Scratch module, never committed."""

import decimal
'''

TESTS = '''\
"""Tests for the fixture package."""

from pathlib import Path

import fixturepkg
from fixturepkg.core import shout


def test_shout() -> None:
    assert shout("hi") == "HI"


def test_the_package_resolves_to_the_tree_being_gated() -> None:
    """The editable-install tripwire (SPEC-executor §3.2, ADR-0076).

    If an editable install shadowed the snapshot, this import would resolve to
    another checkout and the whole run would be reporting on the wrong tree.
    """
    assert Path(fixturepkg.__file__).resolve().is_relative_to(Path.cwd().resolve())
'''


def _git(project: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(project), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _write(project: Path, rel: str, text: str) -> None:
    path = project / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture_project(project: Path) -> Path:
    """A minimal governed Python project with every class of path the snapshot names."""
    _git(project, "init", "-q", "-b", "main")
    _git(project, "config", "user.email", "fixture@example.com")
    _git(project, "config", "user.name", "fixture")

    _write(project, "borromeanrings.toml", CONFIG)
    _write(project, "pyproject.toml", PYPROJECT)
    _write(project, ".gitignore", GITIGNORE)
    _write(project, "README.md", "# fixturepkg\n\nA fixture project.\n")
    _write(
        project,
        "src/fixturepkg/__init__.py",
        '"""The fixture package."""\n\nfrom fixturepkg.core import shout\n\n__all__ = ["shout"]\n',
    )
    _write(project, "src/fixturepkg/core.py", CORE)
    _write(project, "tests/test_core.py", TESTS)
    # Ratchet baselines, seeded from a healthy state so the ratchets are meaningful
    # (an absent baseline reads as 0 and would fail for a non-conformance reason).
    _write(project, ".borromeanrings-complexity-baseline", "10\n")
    _write(project, ".borromeanrings-coupling-baseline", "5\n")
    _write(project, ".borromeanrings-docstring-baseline", "0\n")
    _write(project, ".borromeanrings-coverage-baseline", "0\n")
    _git(project, "add", "-A")
    _git(project, "commit", "-q", "-m", "chore: fixture project")

    _git(project, "checkout", "-q", "-b", BRANCH)
    with (project / "src/fixturepkg/core.py").open("a", encoding="utf-8") as fh:
        fh.write(FEATURE)
    _git(project, "add", "-A")
    _git(project, "commit", "-q", "-m", "feat: whisper")

    # Dirty tracked edit, untracked file, ignored file — none of them committed.
    with (project / "src/fixturepkg/core.py").open("a", encoding="utf-8") as fh:
        fh.write(DIRTY_EDIT)
    _write(project, UNTRACKED, SCRATCH)
    _write(project, FORGED_RECEIPT, json.dumps({"check": "20_lint", "status": "pass"}) + "\n")
    return project


def _gate_env() -> dict[str, str]:
    """One env for both executors, so the only difference is the executor itself."""
    env = dict(os.environ)
    for key in ("BORROMEANRINGS_PROJECT", "CLAUDE_PROJECT_DIR", "PYTHONPATH"):
        env.pop(key, None)
    env["BORROMEANRINGS_HEAVY"] = "0"  # never let an outer heavy run leak in
    env["BORROMEANRINGS_CHECK_TIMEOUT"] = "300"
    return env


def _run_dirs(project: Path) -> set[Path]:
    receipts = project / ".meta-harness" / "receipts"
    return {p for p in receipts.iterdir() if p.is_dir()} if receipts.is_dir() else set()


def _run_local(project: Path) -> tuple[Path, subprocess.CompletedProcess[str]]:
    before = _run_dirs(project)
    result = subprocess.run(
        ["bash", str(VERIFY)],
        cwd=project,
        env={**_gate_env(), "BORROMEANRINGS_PROJECT": str(project)},
        capture_output=True,
        text=True,
        timeout=900,
    )
    new = _run_dirs(project) - before
    assert len(new) == 1, f"expected exactly one new run dir, got {new}\n{result.stdout}"
    return new.pop(), result


def _run_worktree(project: Path) -> tuple[Path, Path, subprocess.CompletedProcess[str]]:
    result = subprocess.run(
        ["bash", str(RUN_IN_WORKTREE), "--project", str(project), "--keep"],
        cwd=project,
        env=_gate_env(),
        capture_output=True,
        text=True,
        timeout=900,
    )
    receipts = _marker(result.stdout, "RECEIPTS: ")
    worktree = _marker(result.stdout, "WORKTREE: ")
    return Path(receipts), Path(worktree), result


def _marker(stdout: str, prefix: str) -> str:
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    raise AssertionError(f"no '{prefix}' line in:\n{stdout}")


def _bundle(run_dir: Path) -> dict[str, dict[str, object]]:
    """Every receipt in a run dir, by check id (`coverage.json` is not a receipt)."""
    out: dict[str, dict[str, object]] = {}
    for jf in sorted(run_dir.glob("*.json")):
        data = json.loads(jf.read_text(encoding="utf-8"))
        if "check" in data:
            assert data["check"] == jf.stem
            out[jf.stem] = data
    return out


def _canonical_logs(run_dir: Path, project_root: Path) -> dict[str, str]:
    """Each receipt's log with this run's paths and durations masked.

    ``run_dir`` is where the bundle *is* (for the worktree executor, where it was
    copied to); ``project_root`` is where the checks *ran*. A transported bundle's
    logs name the producing run dir, which no longer exists — so both spellings are
    masked, and longest-needle-first ordering keeps the run dir from being eaten by
    the project root that contains it.
    """
    produced_in = project_root / ".meta-harness" / "receipts" / run_dir.name
    masks = (
        (str(run_dir), "<RUN>"),
        (str(run_dir.resolve()), "<RUN>"),
        (str(produced_in), "<RUN>"),
        (str(project_root), "<ROOT>"),
        (str(project_root.resolve()), "<ROOT>"),
    )
    return {
        receipt_id: canonicalise_log(
            (run_dir / f"{receipt_id}.log").read_text(encoding="utf-8", errors="replace"), masks
        )
        for receipt_id in _bundle(run_dir)
    }


@pytest.fixture(scope="module")
def transported(concurrent_runs: dict) -> dict[str, object]:
    """One of the concurrent (no --keep) runs: the real transported-bundle case.

    The worktree — and the log path recorded inside every receipt — is gone by the
    time the bundle is read, which is the only way to test reader-side log resolution
    honestly: with a worktree kept alive the recorded path still resolves and the
    fallback is never exercised. Reuses the concurrency fixture's runs rather than
    paying for a gate run of its own.
    """
    run_dir = concurrent_runs["run_dirs"][0]
    return {
        "run_dir": run_dir,
        "worktree_path": Path(_sidecar(run_dir)["worktree"]),
    }


def _sidecar(run_dir: Path) -> dict[str, str]:
    """The `executor.txt` sidecar as key → value."""
    out: dict[str, str] = {}
    for line in (run_dir / "executor.txt").read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition(": ")
        if sep:
            out[key] = value
    return out


@pytest.fixture(scope="module")
def conformance(tmp_path_factory: pytest.TempPathFactory) -> object:
    """Run the fast lane twice — once per executor — over one fixture project."""
    project = _build_fixture_project(tmp_path_factory.mktemp("executor_project"))
    local_dir, local_result = _run_local(project)
    worktree_dir, worktree_path, worktree_result = _run_worktree(project)
    try:
        yield {
            "project": project,
            "local_dir": local_dir,
            "local_result": local_result,
            "worktree_dir": worktree_dir,
            "worktree_path": worktree_path,
            "worktree_result": worktree_result,
        }
    finally:
        subprocess.run(
            ["git", "-C", str(project), "worktree", "remove", "--force", str(worktree_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        shutil.rmtree(worktree_path.parent, ignore_errors=True)


# --------------------------------------------------------------------------
# §5.1 — the same bundle
# --------------------------------------------------------------------------


def test_both_executors_produce_the_same_receipt_set(conformance: dict) -> None:
    local = set(_bundle(conformance["local_dir"]))
    worktree = set(_bundle(conformance["worktree_dir"]))
    assert worktree == local
    assert "20_lint" in local  # the bundle is not vacuously empty


def test_both_bundles_carry_the_same_harness_version(conformance: dict) -> None:
    local = (conformance["local_dir"] / "harness_version.txt").read_text(encoding="utf-8")
    worktree = (conformance["worktree_dir"] / "harness_version.txt").read_text(encoding="utf-8")
    assert worktree == local


def test_the_worktree_bundle_carries_an_executor_sidecar(conformance: dict) -> None:
    sidecar = conformance["worktree_dir"] / "executor.txt"
    text = sidecar.read_text(encoding="utf-8")
    assert "kind: worktree\n" in text
    assert f"branch: {BRANCH}\n" in text
    # A sidecar, never an extra *.json: every JSON in a run dir is read as a receipt.
    assert not (conformance["worktree_dir"] / "executor.json").exists()
    assert "executor" not in _bundle(conformance["worktree_dir"])


def test_the_local_bundle_has_no_executor_sidecar(conformance: dict) -> None:
    assert not (conformance["local_dir"] / "executor.txt").exists()


def test_both_runs_reach_the_same_verdict(conformance: dict) -> None:
    assert conformance["worktree_result"].returncode == conformance["local_result"].returncode
    assert "RESULT: FAIL" in conformance["local_result"].stdout
    assert "RESULT: FAIL" in conformance["worktree_result"].stdout


# --------------------------------------------------------------------------
# §5.2 — field-by-field equivalence
# --------------------------------------------------------------------------


def test_every_receipt_verifies_against_its_own_log(conformance: dict) -> None:
    for run_dir in (conformance["local_dir"], conformance["worktree_dir"]):
        for receipt_id, receipt in _bundle(run_dir).items():
            assert verify_receipt(receipt, read_log_text(receipt, run_dir)), receipt_id


def test_receipts_are_equal_field_by_field(conformance: dict) -> None:
    local = _bundle(conformance["local_dir"])
    worktree = _bundle(conformance["worktree_dir"])
    divergences = {
        receipt_id: receipt_differences(receipt, worktree[receipt_id])
        for receipt_id, receipt in local.items()
        if receipt_differences(receipt, worktree[receipt_id])
    }
    assert divergences == {}


def test_logs_are_equal_after_canonicalisation(conformance: dict) -> None:
    local = _canonical_logs(conformance["local_dir"], conformance["project"])
    worktree = _canonical_logs(conformance["worktree_dir"], conformance["worktree_path"])
    differing = sorted(k for k in local if local[k] != worktree[k])
    detail = "\n\n".join(
        f"### {k}\n--- local\n{local[k]}\n--- worktree\n{worktree[k]}" for k in differing
    )
    assert differing == [], f"log divergence survives canonicalisation:\n{detail}"


# --------------------------------------------------------------------------
# §5.3 — the discriminating fixtures
# --------------------------------------------------------------------------


def test_branch_identity_is_the_primary_s_g8(conformance: dict) -> None:
    project, worktree = conformance["project"], conformance["worktree_path"]
    assert _git(worktree, "rev-parse", "HEAD") == _git(project, "rev-parse", "HEAD")
    assert _git(worktree, "rev-parse", "--abbrev-ref", "HEAD") == BRANCH
    assert _git(project, "rev-parse", "--abbrev-ref", "HEAD") == BRANCH


def test_the_branch_reading_checks_see_the_branch_name(conformance: dict) -> None:
    # The two checks that read the branch NAME on this base. A detached worktree
    # would flip 13_adr to a pass and put "HEAD" in 08_branch's log — so these
    # assertions are what give the log comparison above its teeth.
    local = _bundle(conformance["local_dir"])
    worktree = _bundle(conformance["worktree_dir"])
    assert local["13_adr"]["status"] == "fail"
    assert worktree["13_adr"]["status"] == "fail"
    assert local["08_branch"]["status"] == "pass"
    assert worktree["08_branch"]["status"] == "pass"
    for run_dir in (conformance["local_dir"], conformance["worktree_dir"]):
        for receipt_id in ("08_branch", "13_adr"):
            assert BRANCH in (run_dir / f"{receipt_id}.log").read_text(encoding="utf-8")


def test_the_dirty_tree_and_the_untracked_file_are_transported(conformance: dict) -> None:
    worktree = conformance["worktree_path"]
    assert (worktree / UNTRACKED).exists()
    assert "import calendar" in (worktree / "src/fixturepkg/core.py").read_text(encoding="utf-8")
    # Both lint errors are reported, by both executors, naming both files.
    for run_dir in (conformance["local_dir"], conformance["worktree_dir"]):
        log = (run_dir / "20_lint.log").read_text(encoding="utf-8")
        assert "src/fixturepkg/core.py" in log
        assert "src/fixturepkg/scratch.py" in log
    assert _bundle(conformance["local_dir"])["20_lint"]["status"] == "fail"
    assert _bundle(conformance["worktree_dir"])["20_lint"]["status"] == "fail"


def test_the_untracked_file_stays_untracked_in_the_worktree(conformance: dict) -> None:
    # read-tree alone would put it in the index and make every tracked-file check
    # (12_secrets, 01_source_coherence) see a different project than `local` does.
    project, worktree = conformance["project"], conformance["worktree_path"]
    assert _git(worktree, "ls-files") == _git(project, "ls-files")
    assert UNTRACKED not in _git(worktree, "ls-files").splitlines()
    assert _git(worktree, "status", "--porcelain=v1", "-uall") == _git(
        project, "status", "--porcelain=v1", "-uall"
    )


def test_the_ignored_file_is_not_materialised(conformance: dict) -> None:
    worktree = conformance["worktree_path"]
    assert (conformance["project"] / FORGED_RECEIPT).exists()  # it is there in the primary
    assert not (worktree / FORGED_RECEIPT).exists()
    assert not (worktree / ".meta-harness" / "receipts" / "old").exists()
    # …and the forged receipt is in neither bundle.
    assert "20_lint" in _bundle(conformance["worktree_dir"])
    assert _bundle(conformance["worktree_dir"])["20_lint"]["status"] == "fail"


def test_coverage_counts_the_untracked_file_in_both(conformance: dict) -> None:
    # A receipt EXTRA that discriminates: coverage_percent counts scratch.py's
    # uncovered lines, so it moves if the untracked file is not materialised.
    local = _bundle(conformance["local_dir"])["40_test"]
    worktree = _bundle(conformance["worktree_dir"])["40_test"]
    assert local["coverage_percent"] == worktree["coverage_percent"]
    assert float(str(local["coverage_percent"])) < 100.0


# --------------------------------------------------------------------------
# §2.3 — the transported bundle stays verifiable (and stays tamper-evident)
# --------------------------------------------------------------------------


def test_the_executor_removes_its_worktree(transported: dict) -> None:
    # The default path (no --keep): the worktree and its temp dir are gone, and the
    # receipts are not. Nothing is left behind for an orchestrator to leak.
    assert not transported["worktree_path"].exists()
    assert not transported["worktree_path"].parent.exists()
    assert transported["run_dir"].is_dir()


# --------------------------------------------------------------------------
# The primary is allowed to move (PR #212 review; ADR-0076)
#
# These are the cases a single sequential run structurally cannot catch, and
# concurrency is the entire motivation (#144). Under the first implementation —
# a `git worktree` whose HEAD pointed at the primary's LIVE branch ref — the
# worktree's HEAD silently followed the primary's next commit while its
# materialised tree stayed pinned, so the branch-reading checks judged a commit
# range that did not correspond to the tree in front of them.
# --------------------------------------------------------------------------

INJECTED_SUBJECT = "WIP not a conventional subject"


def _move_the_primary(project: Path) -> str:
    """Commit on the primary. A live-ref worktree would follow this; a snapshot must not.

    Deliberately chosen to move BOTH branch-reading checks if it is followed: the
    subject is not a declared `commit_type` (`09_commits` would fail) and it adds an
    ADR (`13_adr` would flip from fail to pass). Only the ADR file is committed, so
    the dirty edit and the untracked file stay as they were.
    """
    _write(project, "docs/adr/0001-injected.md", "# injected decision\n")
    _git(project, "add", "docs/adr/0001-injected.md")
    _git(project, "commit", "-q", "-m", INJECTED_SUBJECT)
    return _git(project, "rev-parse", "HEAD")


def _await_materialisation(tmpdir: Path, timeout: float = 120.0) -> Path | None:
    """Wait for a run's snapshot tree to appear under ``tmpdir``, or ``None`` on timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        found = sorted(tmpdir.glob("borromeanrings-worktree.*/tree/borromeanrings.toml"))
        if found:
            return found[0]
        time.sleep(0.01)
    return None


@pytest.fixture(scope="module")
def moving_primary(tmp_path_factory: pytest.TempPathFactory) -> object:
    """One kept run, with the primary committing **while the gate is running in it**.

    The snapshot is captured before the commit and the branch-reading checks run
    after it, so this single run answers every "the primary moved" question: the
    receipts, the worktree's own HEAD, and what the primary's ref looks like
    afterwards.
    """
    project = _build_fixture_project(tmp_path_factory.mktemp("moving_primary"))
    tmpdir = tmp_path_factory.mktemp("moving_primary_tmp")
    captured = _git(project, "rev-parse", "HEAD")
    ref_before = _git(project, "rev-parse", f"refs/heads/{BRANCH}")
    reflog_before = _git(project, "reflog", "show", "--format=%H", BRANCH)
    process = subprocess.Popen(
        ["bash", str(RUN_IN_WORKTREE), "--project", str(project), "--keep"],
        cwd=project,
        env={**_gate_env(), "TMPDIR": str(tmpdir)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        materialised = _await_materialisation(tmpdir)
        assert materialised is not None, (
            "never saw the snapshot materialise — the test would be vacuous"
        )
        moved = _move_the_primary(project)
        stdout, stderr = process.communicate(timeout=900)
    finally:
        if process.poll() is None:  # pragma: no cover — only on a hang
            process.kill()
            process.communicate()
    worktree = Path(_marker(stdout, "WORKTREE: "))
    try:
        yield {
            "project": project,
            "worktree": worktree,
            "run_dir": Path(_marker(stdout, "RECEIPTS: ")),
            "captured": captured,
            "moved": moved,
            "ref_before": ref_before,
            "reflog_before": reflog_before,
            "stderr": stderr,
        }
    finally:
        shutil.rmtree(worktree.parent, ignore_errors=True)


def test_the_worktree_head_cannot_follow_the_primary_branch(moving_primary: dict) -> None:
    # The structural half: the worktree still exists, the primary has moved on, and
    # the worktree's HEAD has not.
    worktree = moving_primary["worktree"]
    assert moving_primary["moved"] != moving_primary["captured"]
    assert _git(worktree, "rev-parse", "HEAD") == moving_primary["captured"]
    assert _git(worktree, "rev-parse", f"refs/heads/{BRANCH}") == moving_primary["captured"]
    # …and G8 still holds: it is the branch, by name, not a detached HEAD.
    assert _git(worktree, "rev-parse", "--abbrev-ref", "HEAD") == BRANCH


def test_a_commit_on_the_primary_during_a_run_does_not_change_the_receipts(
    moving_primary: dict,
) -> None:
    # The receipt half: the commit landed after the snapshot was captured and before
    # the branch-reading checks ran. They must say what a quiet primary would produce.
    run_dir = moving_primary["run_dir"]
    bundle = _bundle(run_dir)
    assert _sidecar(run_dir)["head"] == moving_primary["captured"]
    # 09_commits: the injected subject is not a declared commit type. If HEAD had
    # followed the branch, this would be a fail naming that subject.
    assert bundle["09_commits"]["status"] == "pass", moving_primary["stderr"]
    assert INJECTED_SUBJECT not in (run_dir / "09_commits.log").read_text(encoding="utf-8")
    # 13_adr: the injected commit adds an ADR. If HEAD had followed the branch, this
    # would have flipped from fail to pass.
    assert bundle["13_adr"]["status"] == "fail"
    assert "0001-injected.md" not in (run_dir / "13_adr.log").read_text(encoding="utf-8")
    assert bundle["08_branch"]["status"] == "pass"


def test_the_worktree_owns_its_refs_and_borrows_only_objects(moving_primary: dict) -> None:
    worktree = moving_primary["worktree"]
    # Its own repository, not a linked worktree of the primary…
    assert (worktree / ".git").is_dir()
    alternates = (worktree / ".git" / "objects" / "info" / "alternates").read_text(encoding="utf-8")
    assert alternates.strip().endswith("/objects")
    # …so the primary holds no metadata about it, and it copies no objects of its own.
    assert not list((worktree / ".git" / "objects" / "pack").glob("*.pack"))
    # The ref state is a snapshot of the primary's: the base the range-reading checks
    # resolve is present, at the primary's commit.
    primary = moving_primary["project"]
    assert _git(worktree, "rev-parse", "main") == _git(primary, "rev-parse", "main")


def test_the_executor_never_writes_the_primary_s_branch_ref(moving_primary: dict) -> None:
    # Property 3, in the presence of a moving primary: the ONLY thing that moved the
    # branch during the run was the test's own commit — the ref sits exactly at it and
    # the reflog grew by exactly that one entry, so the executor wrote neither.
    project = moving_primary["project"]
    assert _git(project, "rev-parse", f"refs/heads/{BRANCH}") == moving_primary["moved"]
    reflog_now = _git(project, "reflog", "show", "--format=%H", BRANCH).splitlines()
    assert reflog_now == [moving_primary["moved"], *moving_primary["reflog_before"].splitlines()]


@pytest.fixture(scope="module")
def concurrent_runs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    """#144's actual shape: two agents gated at once, on one branch, in one project."""
    project = _build_fixture_project(tmp_path_factory.mktemp("concurrent"))
    ref_before = _git(project, "rev-parse", f"refs/heads/{BRANCH}")
    processes = [
        subprocess.Popen(
            ["bash", str(RUN_IN_WORKTREE), "--project", str(project)],
            cwd=project,
            env=_gate_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    outputs = []
    try:
        for process in processes:
            outputs.append(process.communicate(timeout=900))
    finally:
        for process in processes:
            if process.poll() is None:  # pragma: no cover — only on a hang
                process.kill()
                process.communicate()
    return {
        "project": project,
        "ref_before": ref_before,
        "run_dirs": [Path(_marker(stdout, "RECEIPTS: ")) for stdout, _ in outputs],
        "outputs": outputs,
    }


def test_two_concurrent_runs_on_one_branch_both_succeed(concurrent_runs: dict) -> None:
    run_dirs = concurrent_runs["run_dirs"]
    assert run_dirs[0] != run_dirs[1], "two runs must not share a receipt bundle"
    first, second = (_bundle(d) for d in run_dirs)
    assert set(first) == set(second)
    divergences = {
        cid: receipt_differences(receipt, second[cid])
        for cid, receipt in first.items()
        if receipt_differences(receipt, second[cid])
    }
    assert divergences == {}
    # Same snapshot, separate worktrees, and the primary's branch ref is where it was.
    assert {_sidecar(d)["head"] for d in run_dirs} == {
        _git(concurrent_runs["project"], "rev-parse", "HEAD")
    }
    assert _sidecar(run_dirs[0])["worktree"] != _sidecar(run_dirs[1])["worktree"]
    assert (
        _git(concurrent_runs["project"], "rev-parse", f"refs/heads/{BRANCH}")
        == concurrent_runs["ref_before"]
    )


def test_the_executor_refuses_a_worktree_inside_the_repository(conformance: dict) -> None:
    # A $TMPDIR inside the governed repo would put the worktree into the next run's
    # snapshot. The refusal happens after cleanup is armed, so the temp dir it
    # refuses to use is not left behind either.
    project = conformance["project"]
    before = set(project.iterdir())
    result = subprocess.run(
        ["bash", str(RUN_IN_WORKTREE), "--project", str(project)],
        cwd=project,
        env={**_gate_env(), "TMPDIR": str(project)},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 1
    assert "refusing to build the worktree inside the repository" in result.stderr
    assert set(project.iterdir()) == before


def test_the_transported_bundle_verifies_once_the_worktree_is_gone(
    transported: dict,
) -> None:
    # The hazard SPEC-executor §2.3 names: `log` is an absolute path in the
    # executor's namespace and it is INSIDE the hash. Without reader-side
    # resolution every one of these receipts would read `!TAMPERED` here.
    run_dir = transported["run_dir"]
    receipts = _bundle(run_dir)
    assert receipts, "the transported bundle is empty"
    for receipt_id, receipt in receipts.items():
        recorded = Path(str(receipt["log"]))
        assert not recorded.exists(), f"{receipt_id}: the worktree is supposed to be gone"
        assert verify_receipt(receipt, read_log_text(receipt, run_dir)), receipt_id


def test_a_transported_bundle_with_an_edited_log_still_fails(
    transported: dict, tmp_path: Path
) -> None:
    # Resolution finds WHERE the log is, never WHAT it says: transport does not
    # weaken tamper evidence.
    moved = tmp_path / "tampered"
    shutil.copytree(transported["run_dir"], moved)
    (moved / "20_lint.log").write_text("All checks passed!\n", encoding="utf-8")
    receipt = json.loads((moved / "20_lint.json").read_text(encoding="utf-8"))
    assert not verify_receipt(receipt, read_log_text(receipt, moved))
