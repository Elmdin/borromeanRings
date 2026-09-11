"""Generator-loop conformance: the headless driver, end to end (SPEC-generator.md §5).

The four scenarios of §3.2 are driven for real — a real `generate.sh`, a real gate, real
receipts — against throwaway fixture projects built in tmp. Each asserts the outcome the
spec names *and* the evidence behind it (how many times the gate actually ran, which
check ids the retry named, whether the counter survived), because an outcome alone can be
produced by a loop that is right for the wrong reason.

Two negative fixtures sit alongside them: a generator that resets the gate's retry
counter, and one that edits a receipt in an earlier bundle. Neither is asked politely not
to; both are caught. A third, `commit_only.sh`, discriminates the correction ADR-0078
made to N3 — it changes what the gate reads without changing a single file.

Repo-root paths (``generate.sh``, ``.claude/hooks/``, ``tests/fixtures/``) are read here,
which is why this file lives under ``tests/integration/`` and is excluded from mutmut's
copied working dir — see ADR-0022 and ``setup.cfg``.

**Assert our own words, never another tool's.** Every string matched below is produced by
`generate.sh`, `stop_gate.sh` or a fixture in this repo. Matching git's error prose, or
assuming git's default configuration, couples a verdict to a release or a machine: CI once
went red here on nothing but `error: unrecognized input` (git 2.34) becoming `error: No
valid patches in input` (git 2.55). ADR-0077 pins the tools whose output decides a verdict,
but only Python distributions — git cannot be pinned that way, so for it the rule is not to
depend on the prose at all. See ADR-0078.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from meta_harness.receipts import verify_receipt

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
GENERATE = BORROMEANRINGS_HOME / "generate.sh"
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
STOP_GATE = BORROMEANRINGS_HOME / ".claude" / "hooks" / "stop_gate.sh"
FIXTURES = BORROMEANRINGS_HOME / "tests" / "fixtures" / "generators"

#: Generous: each driver run may start the gate up to three times, and CI is shared.
DRIVER_TIMEOUT_S = 600

#: Exit codes the driver promises (generate.sh header).
EXIT_GREEN, EXIT_ESCALATED, EXIT_GENERATOR_FAILED = 0, 1, 2
EXIT_REFUSED, EXIT_MISCONFIGURED = 3, 4

# A language-agnostic project: only checks/shared runs, so a gate run costs a second or
# two. 07_layout fails for any repo-root .md outside the allowlist — a defect a patch can
# introduce, keep, or remove, which is all the loop needs.
_LAYOUT_TOML = """\
[project]
language = "none"
package = ""

[checks]
required = ["07_layout"]

[hygiene]
requires = []

[layout]
root_doc_allowlist = ["README.md"]

[generator]
command = "{command}"
"""

# The python project, used only where the spec names 20_lint (the fixed-on-retry row).
_LINT_TOML = """\
[project]
language = "python"
src_dir = "src"

[checks]
required = ["20_lint"]

[hygiene]
requires = []

[generator]
command = "{command}"
"""

_CLEAN_MODULE = '"""Fine."""\n\n\ndef ok() -> int:\n    """Fine."""\n    return 1\n'


def _new_file_patch(path: str, line: str) -> str:
    return (
        f"diff --git a/{path} b/{path}\nnew file mode 100644\n"
        f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1 @@\n+{line}\n"
    )


def _delete_file_patch(path: str, line: str) -> str:
    return (
        f"diff --git a/{path} b/{path}\ndeleted file mode 100644\n"
        f"--- a/{path}\n+++ /dev/null\n@@ -1 +0,0 @@\n-{line}\n"
    )


def _project(
    root: Path, toml: str, files: dict[str, str], generator: str, *, gitignore: bool = True
) -> Path:
    """Build and commit a throwaway governed project driven by ``generator``.

    ``gitignore=False`` builds the case borromeanRings never establishes for itself:
    ``init.sh`` and ``adopt.sh`` write no ``.gitignore``, so a governed project whose
    evidence area is part of its own tracked tree is the DEFAULT, not the exception. Every
    fixture here used to pre-create that file, which is how a fail-open in the driver's
    change detection went unseen — so at least one case must not.
    """
    root.mkdir(parents=True, exist_ok=True)
    contents = {
        "borromeanrings.toml": toml.format(command=str(FIXTURES / generator)),
        "README.md": "# fixture\n",
        **files,
    }
    if gitignore:
        contents[".gitignore"] = ".meta-harness/\n"
    for rel, text in contents.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(
        # Identity and signing are pinned off: a fixture must not fail because the machine
        # running it signs its commits, any more than it should care which git it has.
        [
            "git",
            "-c",
            "user.name=fixture",
            "-c",
            "user.email=f@x",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "init",
        ],
        cwd=root,
        check=True,
    )
    return root


def _drive(project: Path, run_key: str = "headless") -> subprocess.CompletedProcess[str]:
    """Run the headless driver over ``project`` exactly as a human or #144 would."""
    env = dict(os.environ)
    env["BORROMEANRINGS_RUN_KEY"] = run_key
    return subprocess.run(
        ["bash", str(GENERATE), str(project)],
        env=env,
        capture_output=True,
        text=True,
        timeout=DRIVER_TIMEOUT_S,
    )


def _result(proc: subprocess.CompletedProcess[str]) -> str:
    """The driver's stated outcome, from its own report."""
    for line in proc.stdout.splitlines():
        if line.strip().startswith("GENERATOR-RESULT:"):
            return line.split(":", 1)[1].strip()
    return f"<no result line>\nstdout={proc.stdout}\nstderr={proc.stderr}"


def _bundles(project: Path) -> list[Path]:
    receipts = project / ".meta-harness" / "receipts"
    return sorted(p for p in receipts.glob("*") if p.is_dir()) if receipts.is_dir() else []


def _logs(project: Path, run_key: str = "headless") -> list[Path]:
    log_dir = project / ".meta-harness" / "generator" / run_key
    return sorted(log_dir.glob("*.log")) if log_dir.is_dir() else []


def _counter(project: Path, run_key: str = "headless") -> Path:
    return project / ".meta-harness" / "stop_attempts" / run_key


def _receipt_status(bundle: Path, check_id: str) -> str:
    return str(json.loads((bundle / f"{check_id}.json").read_text(encoding="utf-8"))["status"])


# --- §3.2's four scenarios ----------------------------------------------------


def test_fixed_on_retry_is_green_at_attempt_two(tmp_path: Path) -> None:
    """1.diff breaks the lint, 2.diff fixes it: green at attempt 2, and the retry in
    between named the check that failed — read off the verdict's rows, not its summary."""
    project = _project(
        tmp_path / "fixed",
        _LINT_TOML,
        {
            "src/ok.py": _CLEAN_MODULE,
            "patches/1.diff": _new_file_patch("src/bad.py", "import os"),
            "patches/2.diff": _delete_file_patch("src/bad.py", "import os"),
        },
        "apply_patch.sh",
    )
    proc = _drive(project)

    assert _result(proc) == "green"
    assert proc.returncode == EXIT_GREEN
    bundles = _bundles(project)
    assert len(bundles) == 2, "the gate runs once per attempt — twice, no more"
    assert _receipt_status(bundles[0], "20_lint") == "fail"
    assert _receipt_status(bundles[1], "20_lint") == "pass"

    # N1/N2 and §5.4: attempt 2 was handed the verdict's path and exactly the check ids
    # that attempt 1's bundle recorded as failing — not a separately-maintained list.
    last_verdict = project / ".meta-harness" / "last_verdict.json"
    second = _logs(project)[1].read_text(encoding="utf-8")
    assert "attempt=2 cap=3" in second
    assert f"verdict=[{last_verdict}]" in second
    failed_in_bundle = [cid for cid in ("20_lint",) if _receipt_status(bundles[0], cid) != "pass"]
    assert f"failing=[{','.join(failed_in_bundle)}]" in second

    assert not _counter(project).exists(), "the counter is cleared on green"
    assert json.loads((project / ".meta-harness" / "last_verdict.json").read_text("utf-8"))[
        "intent"
    ] == {"generator": "headless:apply_patch.sh"}


def test_never_fixed_escalates_after_exactly_cap_attempts(tmp_path: Path) -> None:
    """Three patches that each keep the defect: three gate runs, three bundles, then the
    human. Not two, not four — the bound is the whole point."""
    project = _project(
        tmp_path / "never",
        _LAYOUT_TOML,
        {f"patches/{n}.diff": _new_file_patch(f"BAD{n}.md", "still broken") for n in (1, 2, 3)},
        "apply_patch.sh",
    )
    proc = _drive(project)

    assert _result(proc) == "escalated"
    assert proc.returncode == EXIT_ESCALATED
    assert len(_bundles(project)) == 3
    assert [p.name for p in _logs(project)] == ["1.log", "2.log", "3.log"]
    assert not _counter(project).exists(), "the counter is cleared at escalation"
    assert "ESCALATION" in proc.stderr


def test_no_change_escalates_immediately_without_gating(tmp_path: Path) -> None:
    """Exit 0 with an untouched tree is "I have nothing to add": retrying an idempotent
    generator only spends attempts, so the gate is never asked."""
    project = _project(tmp_path / "nochange", _LAYOUT_TOML, {}, "apply_patch.sh")
    proc = _drive(project)

    assert _result(proc) == "escalated"
    assert proc.returncode == EXIT_ESCALATED
    assert _bundles(project) == [], "no gate run at all — there was nothing to gate"
    assert len(_logs(project)) == 1, "and no second attempt"


def test_a_crashing_generator_is_generator_failed(tmp_path: Path) -> None:
    """A malformed patch makes git apply refuse; the driver reports that as the
    generator's failure, keeps its output, and never pretends a gate ran.

    What is asserted about the log is the fixture's OWN marker, on stderr. Asserting git's
    phrasing here — "error: unrecognized input" on git 2.34, "error: No valid patches in
    input" on 2.55 — asserts a git release; the property meant is that the driver captures
    what the generator wrote, on both streams, and that belongs to the driver."""
    project = _project(
        tmp_path / "crash",
        _LAYOUT_TOML,
        {"patches/1.diff": "this is not a diff at all\n"},
        "apply_patch.sh",
    )
    proc = _drive(project)

    assert _result(proc) == "generator-failed"
    assert proc.returncode == EXIT_GENERATOR_FAILED
    assert _bundles(project) == [], "no receipt bundle for an attempt that produced nothing"
    log = _logs(project)[0].read_text(encoding="utf-8")
    assert "apply_patch: git apply refused" in log, "stderr is captured"
    assert "handed: attempt=1" in log, "and stdout, in the same log"


# --- §2.3: what the gate owns and the generator cannot touch ------------------


def test_a_generator_that_resets_the_retry_counter_is_caught(tmp_path: Path) -> None:
    """The counter lives with the gate. A generator that edits it has forged an attempt,
    so the run ends there — it does not buy itself a fresh set of three."""
    project = _project(tmp_path / "reset", _LAYOUT_TOML, {}, "reset_counter.sh")
    proc = _drive(project)

    assert _result(proc) == "generator-failed"
    assert proc.returncode == EXIT_GENERATOR_FAILED
    assert "modified: stop_attempts/headless" in proc.stderr
    assert _bundles(project) == [], "a run this untrustworthy is never gated"


def test_the_generator_is_told_its_attempt_as_a_number(tmp_path: Path) -> None:
    """The generator needs no counter: the attempt and the cap arrive as numbers.

    Note what this does NOT claim. A generator runs as the same user in the same tree; it
    is handed the project path, and from attempt two it is handed a path inside
    ``.meta-harness/`` (the verdict it must read). The counter is therefore *readable*,
    and saying otherwise would be a comfortable fiction. What holds is that reading it
    buys nothing and writing it is caught — the two tests either side of this one."""
    project = _project(tmp_path / "handed", _LAYOUT_TOML, {}, "apply_patch.sh")
    _drive(project)

    handed = _logs(project)[0].read_text(encoding="utf-8")
    assert "attempt=1 cap=3" in handed


def test_an_edited_receipt_is_caught_and_stops_verifying(tmp_path: Path) -> None:
    """Two defences, both shown: the driver sees the write into the gate's evidence, and
    the edited receipt no longer matches its own content hash (ADR-0026 — what the
    verdict reports as !TAMPERED)."""
    project = _project(
        tmp_path / "tamper", _LAYOUT_TOML, {"BAD.md": "disallowed\n"}, "edit_receipt.sh"
    )
    # A bundle for the generator to go after: one real, failing gate run.
    subprocess.run(
        ["bash", str(VERIFY)],
        env={**os.environ, "BORROMEANRINGS_PROJECT": str(project)},
        capture_output=True,
        text=True,
        timeout=DRIVER_TIMEOUT_S,
    )
    bundle = _bundles(project)[0]
    receipt_path = bundle / "07_layout.json"
    assert _receipt_status(bundle, "07_layout") == "fail"

    proc = _drive(project)

    assert _result(proc) == "generator-failed"
    assert "modified: " in proc.stderr and "07_layout.json" in proc.stderr
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "pass", "the fixture really did forge a pass"
    log_text = Path(str(receipt["log"])).read_text(encoding="utf-8", errors="replace")
    assert verify_receipt(receipt, log_text) is False, "and the forgery does not verify"


def test_run_keys_keep_independent_counters(tmp_path: Path) -> None:
    """§5.3: the attempt key selects the counter. Another key's count is neither read,
    reset, nor shared — the property the Stop hook has per session_id."""
    project = _project(
        tmp_path / "keys", _LAYOUT_TOML, {"patches/1.diff": "bad\n"}, "apply_patch.sh"
    )
    other = _counter(project, "another-agent")
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_text("2", encoding="utf-8")

    proc = _drive(project, run_key="mine")

    assert _result(proc) == "generator-failed"
    assert other.read_text(encoding="utf-8") == "2", "the other key's count is untouched"
    assert not _counter(project, "mine").exists()
    assert len(_logs(project, "mine")) == 1
    assert _logs(project, "another-agent") == []


# --- §2.3 / §5.2: one CAP, and provenance in the verdict ----------------------


def test_neither_adapter_owns_a_second_copy_of_cap() -> None:
    """CAP is declared once, in meta_harness.generator, and read by both adapters. A
    literal in either script is a second source of truth that can silently drift."""
    for adapter in (STOP_GATE, GENERATE):
        text = adapter.read_text(encoding="utf-8")
        assert "from meta_harness.generator import CAP" in text, adapter
        assert "CAP=3" not in text.replace(" ", ""), f"{adapter} hardcodes the cap"


def test_the_stop_hook_records_itself_as_the_generator(tmp_path: Path) -> None:
    """§5.2: the claude-code adapter's verdicts carry its identity, session and all."""
    project = _project(tmp_path / "hooked", _LAYOUT_TOML, {}, "apply_patch.sh")
    proc = subprocess.run(
        ["bash", str(STOP_GATE)],
        input=json.dumps({"stop_hook_active": False, "session_id": "sess-42"}),
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(project)},
        capture_output=True,
        text=True,
        timeout=DRIVER_TIMEOUT_S,
    )
    assert proc.returncode in (0, 2), proc.stderr
    verdict = json.loads((project / ".meta-harness" / "last_verdict.json").read_text("utf-8"))
    assert verdict["intent"] == {"generator": "claude-code:sess-42"}


def test_a_gate_run_with_no_adapter_records_no_generator(tmp_path: Path) -> None:
    """§5.2's other half: unset means unset. The gate never guesses who ran it."""
    project = _project(tmp_path / "bare", _LAYOUT_TOML, {}, "apply_patch.sh")
    env = {k: v for k, v in os.environ.items() if k != "BORROMEANRINGS_GENERATOR"}
    env["BORROMEANRINGS_PROJECT"] = str(project)
    subprocess.run(
        ["bash", str(VERIFY)], env=env, capture_output=True, text=True, timeout=DRIVER_TIMEOUT_S
    )
    verdict = json.loads((project / ".meta-harness" / "last_verdict.json").read_text("utf-8"))
    assert verdict["intent"] == {"generator": ""}


def test_the_driver_refuses_a_project_with_no_declared_generator(tmp_path: Path) -> None:
    """Absent [generator].command ⇒ there is no headless generator. Never a silent
    default to some built-in fixer."""
    project = tmp_path / "undeclared"
    project.mkdir()
    (project / "borromeanrings.toml").write_text(
        '[checks]\nrequired = ["07_layout"]\n', encoding="utf-8"
    )
    proc = _drive(project)

    assert proc.returncode == EXIT_REFUSED
    assert "no [generator].command" in proc.stderr
    assert _bundles(project) == []


@pytest.mark.parametrize("run_key", ["", ".", "..", "a/b"])
def test_the_driver_refuses_a_run_key_that_is_a_path(tmp_path: Path, run_key: str) -> None:
    """The run key names a counter file; it does not get to choose where that file is."""
    project = _project(tmp_path / f"key{len(run_key)}", _LAYOUT_TOML, {}, "apply_patch.sh")
    proc = _drive(project, run_key=run_key)

    assert proc.returncode == EXIT_REFUSED
    assert "BORROMEANRINGS_RUN_KEY" in proc.stderr


def test_a_commit_that_changes_no_file_is_still_a_change(tmp_path: Path) -> None:
    """The dirty-tree OID alone is not "did anything happen?". A generator that amends or
    commits has moved what the branch- and history-reading checks read while leaving the
    tree byte-identical — so the gate is asked, not told the generator did nothing.
    A correction to SPEC-generator.md N3; see ADR-0078."""
    project = _project(tmp_path / "commitonly", _LAYOUT_TOML, {}, "commit_only.sh")
    proc = _drive(project)

    assert _result(proc) == "green"
    assert len(_bundles(project)) == 1, "the gate was asked, because the run changed what it reads"


def test_a_hostile_generator_label_cannot_touch_the_verdict(tmp_path: Path) -> None:
    """The load-bearing guarantee of ADR-0071 §4: nothing self-declared can loosen `ok`.

    The label is recorded verbatim into the same JSON document as the verdict, so a value
    shaped like a status field is the obvious attack. The gate must still fail, and the
    record must still parse — with the label sitting inertly where it belongs."""
    project = _project(
        tmp_path / "hostile", _LAYOUT_TOML, {"BAD.md": "disallowed\n"}, "apply_patch.sh"
    )
    hostile = '", "ok": true, "checks": [], "x": "'
    proc = subprocess.run(
        ["bash", str(VERIFY)],
        env={
            **os.environ,
            "BORROMEANRINGS_PROJECT": str(project),
            "BORROMEANRINGS_GENERATOR": hostile,
        },
        capture_output=True,
        text=True,
        timeout=DRIVER_TIMEOUT_S,
    )

    assert proc.returncode != 0, "the planted layout defect must still fail the gate"
    verdict = json.loads((project / ".meta-harness" / "last_verdict.json").read_text("utf-8"))
    assert verdict["ok"] is False
    assert verdict["checks"] == [["07_layout", "fail"]]
    assert verdict["intent"] == {"generator": hostile}, "recorded, inert, and escaped"

    # And the sanitiser is actually wired into the gate, not merely unit-tested: a label
    # carrying a newline would break the record it goes into, so it is dropped entirely.
    subprocess.run(
        ["bash", str(VERIFY)],
        env={
            **os.environ,
            "BORROMEANRINGS_PROJECT": str(project),
            "BORROMEANRINGS_GENERATOR": "headless:x\ninjected",
        },
        capture_output=True,
        text=True,
        timeout=DRIVER_TIMEOUT_S,
    )
    verdict = json.loads((project / ".meta-harness" / "last_verdict.json").read_text("utf-8"))
    assert verdict["intent"] == {"generator": ""}


def test_a_failure_after_the_loop_begins_escalates_instead_of_refusing(tmp_path: Path) -> None:
    """Refusing (exit 3) says "there was nothing to drive" and an orchestrator may skip it.
    Once an attempt is under way that answer is wrong: whatever broke, a human must look.
    Here the project is governed and has a generator declared, but is not a git repo, so
    the driver cannot tell "wrote a change" from "did nothing"."""
    project = tmp_path / "notgit"
    project.mkdir()
    (project / "borromeanrings.toml").write_text(
        _LAYOUT_TOML.format(command=str(FIXTURES / "apply_patch.sh")), encoding="utf-8"
    )
    proc = _drive(project)

    assert proc.returncode == EXIT_ESCALATED
    assert _result(proc) == "escalated (the driver could not continue)"
    assert "git repository is required" in proc.stderr
    assert not _counter(project).exists(), "a terminal outcome leaves no live counter behind"


def test_an_unreadable_config_says_so_rather_than_blaming_the_generator(tmp_path: Path) -> None:
    """A broken borromeanrings.toml and an undeclared command are different problems."""
    project = tmp_path / "badtoml"
    project.mkdir()
    (project / "borromeanrings.toml").write_text("[checks\nrequired = ", encoding="utf-8")
    proc = _drive(project)

    assert proc.returncode == EXIT_MISCONFIGURED
    assert "cannot read" in proc.stderr
    assert "no [generator].command" not in proc.stderr


# --- change detection: what the gate can see, and nothing the driver wrote itself ------


@pytest.mark.parametrize("gitignore", [True, False], ids=["ignored", "tracked"])
def test_an_inert_generator_escalates_however_the_evidence_area_is_treated(
    tmp_path: Path, gitignore: bool
) -> None:
    """A generator that runs cleanly and writes nothing has said "I have nothing to add",
    and that answer cannot depend on whether the project gitignores `.meta-harness/`.

    It did: the driver captured the generator's stdout inside the gated tree, so on a
    project without the ignore the tree "changed" every attempt and the run was reported
    **green** — exit 0, "a change was written and the gate accepted it", for a run in
    which nothing was written. `init.sh` writes no `.gitignore`, so that was the default
    configuration, and every fixture here pre-created the file that hid it."""
    project = _project(
        tmp_path / f"inert-{gitignore}", _LAYOUT_TOML, {}, "inert.sh", gitignore=gitignore
    )
    proc = _drive(project)

    assert _result(proc) == "escalated"
    assert proc.returncode == EXIT_ESCALATED
    assert _bundles(project) == [], "the gate is never asked about a change nobody made"


def test_moving_another_ref_is_a_change(tmp_path: Path) -> None:
    """Creating `refs/remotes/origin/dev` leaves branch, HEAD, tree and index identical and
    moves what six checks resolve their diff base from (`origin/dev dev origin/main main`).
    A generator that fixes one of those is not a generator that did nothing.

    The fixture deliberately does not move `refs/heads/main`: where `init.defaultBranch` is
    `main`, that ref already points at HEAD and setting it to HEAD proves nothing. Assuming
    another tool's default configuration is the same defect as assuming its error prose."""
    project = _project(tmp_path / "refs", _LAYOUT_TOML, {}, "move_a_ref.sh")
    proc = _drive(project)

    assert _result(proc) == "green"
    assert len(_bundles(project)) == 1, "the gate was asked, because its base moved"


def test_untracking_a_file_is_a_change(tmp_path: Path) -> None:
    """`git rm --cached` changes `git ls-files`, which three checks enumerate from, while
    the file stays on disk and a dirty-tree OID built with `add -A` puts it straight back."""
    project = _project(tmp_path / "index", _LAYOUT_TOML, {}, "untrack_a_file.sh")
    proc = _drive(project)

    assert len(_bundles(project)) == 1, "the gate was asked, because what it enumerates moved"
    assert _result(proc) in {"green", "escalated"}


# --- the retry bound survives a deleted counter ---------------------------------------


def test_deleting_the_counter_alone_no_longer_resets_the_hooks_bound(tmp_path: Path) -> None:
    """The shipped adapter's hole: the counter is one small file in the agent's own tree,
    and deleting it used to hand back a fresh set of three — an unbounded retry loop with
    nothing to detect it. The bound is anchored to the gate's append-only verdict history
    as well, picked out by this session's provenance label.

    Read the name literally: this covers the ONE sabotage the anchor defeats. Deleting the
    history, appending a forged green row for the label, or relabelling the rows each still
    defeat it, because the anchor is a second file in the same tree rather than a second
    authority. A real bound is issue #218. A test named for the property rather than for
    the case would be a claim this suite cannot support."""
    project = _project(
        tmp_path / "hooked-bound", _LAYOUT_TOML, {"BAD.md": "disallowed\n"}, "inert.sh"
    )
    codes = []
    for _ in range(3):
        shutil.rmtree(project / ".meta-harness" / "stop_attempts", ignore_errors=True)
        proc = subprocess.run(
            ["bash", str(STOP_GATE)],
            input=json.dumps({"stop_hook_active": False, "session_id": "s-anchor"}),
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(project)},
            capture_output=True,
            text=True,
            timeout=DRIVER_TIMEOUT_S,
        )
        codes.append((proc.returncode, "ESCALATION" in proc.stderr))

    assert codes == [(2, False), (2, False), (0, True)], (
        "three attempts then the human, however often the counter is deleted"
    )


def test_a_resumed_run_key_does_not_get_a_fresh_set_of_attempts(tmp_path: Path) -> None:
    """N5 bounds the attempt KEY, not the invocation. A driver killed mid-run leaves its
    counter behind; starting again on that key resumes rather than restarting."""
    project = _project(tmp_path / "resume", _LAYOUT_TOML, {}, "apply_patch.sh")
    counter = _counter(project)
    counter.parent.mkdir(parents=True, exist_ok=True)
    counter.write_text("3", encoding="utf-8")

    proc = _drive(project)

    assert proc.returncode == EXIT_ESCALATED
    assert "already spent 3 of 3" in proc.stderr
    assert _logs(project) == [], "the generator is not invoked for an attempt it cannot have"
    assert not counter.exists()


def test_a_broken_config_is_misconfigured_not_merely_absent(tmp_path: Path) -> None:
    """ "There is no config here" and "the config is here and broken" are different facts,
    and an orchestrator branches on the number, not on the sentence. The second is a
    governed project about to go ungated and unnoticed."""
    project = tmp_path / "brokentoml"
    project.mkdir()
    (project / "borromeanrings.toml").write_text("[checks\nrequired = ", encoding="utf-8")
    proc = _drive(project)

    assert proc.returncode == EXIT_MISCONFIGURED
    assert proc.returncode != EXIT_REFUSED
    assert "cannot read" in proc.stderr
