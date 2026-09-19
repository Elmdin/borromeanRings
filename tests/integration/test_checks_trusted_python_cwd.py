"""Every check's trusted Python runs from ``/``, observed rather than grepped (#240).

``python3 -`` puts the working directory first on ``sys.path``, so a ``meta_harness/``
planted in the governed project replaces the gate's own analysis unless the step runs
through ``borromeanrings_py`` (``checks/_py.sh``, which starts from ``/``). The static
guard in ``test_verify_no_sys_path_forge.py`` reads the scripts' text; this test watches
them run.

A decoy that is never imported proves nothing if the step that would have imported it
never ran — a check that exits early because it is not required, or because a
precondition is unmet, is silently vacuous. So this test has a POSITIVE control, and it
is attributed to the exact program: a ``python3`` shim on ``PATH`` records the working
directory and the SHA-256 of every ``python3 -`` program it is handed. The expected set
is every heredoc program in the check scripts whose body imports ``meta_harness`` —
derived from the text however the program is INVOKED, so a check reverted to a bare
``python3`` stays expected and is then seen starting from the project. For each one:

* it RAN in this fixture — matched by hash, so the ``emit_receipt`` program every check
  ends with cannot stand in for it (named below if unreachable here, with the reason),
* every run started from ``/``, and
* the decoy ``meta_harness/`` at the project root was never imported.

The fixture is a Python project on a ``feat/`` branch off ``main`` that adds public
surface, requires every shared and Python-lane check, and enables the opt-in rules, so
every program has a reason to run. The heavy (CI) lane is not run here; the static guard
in ``test_verify_no_sys_path_forge.py`` is its only coverage.
"""

import hashlib
import os
import re
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
LANES = ("shared", "python")

# Programs that do not run on this fixture, keyed "<script>:<heredoc line>", and why.
# Every entry must stay true: the test fails if a listed program DOES run (a stale excuse).
UNREACHABLE_HERE: dict[str, str] = {}

_DECOY = """\
import os
import sys

with open(os.environ["BORROMEANRINGS_DECOY_MARKER"], "a", encoding="utf-8") as fh:
    fh.write(" ".join(sys.argv) + "\\n")
raise ImportError("decoy meta_harness imported from the governed project")
"""

# Logs "<cwd>\t<sha256 of the program>" for each `python3 -`, then runs the real one.
_SHIM = """\
#!/usr/bin/env bash
if [ "${1:-}" = "-" ]; then
  body="$(cat)"
  sum="$(printf '%s' "$body" | sha256sum | cut -c1-64)"
  printf '%s\\t%s\\n' "$PWD" "$sum" >> "$SHIM_LOG"
  exec "$REAL_PYTHON3" "$@" <<<"$body"
fi
exec "$REAL_PYTHON3" "$@"
"""

_HEREDOC = re.compile(r"<<-?\s*'(\w+)'")


def _trusted_programs() -> dict[str, str]:
    """``{sha256: "<script>:<line>"}`` for every heredoc program importing meta_harness."""
    found: dict[str, str] = {}
    for lane in LANES:
        for script in sorted((BORROMEANRINGS_HOME / "checks" / lane).glob("[0-9]*.sh")):
            lines = script.read_text(encoding="utf-8").splitlines()
            rel = script.relative_to(BORROMEANRINGS_HOME).as_posix()
            for i, line in enumerate(lines):
                m = _HEREDOC.search(line.split("#", 1)[0])
                if not m:
                    continue
                end = next((k for k in range(i + 1, len(lines)) if lines[k] == m.group(1)), None)
                assert end is not None, f"{rel}:{i + 1}: unterminated heredoc {m.group(1)}"
                body = "\n".join(lines[i + 1 : end]).rstrip("\n")
                if re.search(r"^(from|import) meta_harness", body, re.M):
                    found[hashlib.sha256(body.encode()).hexdigest()] = f"{rel}:{i + 1}"
    return found


def _fixture(root: Path) -> Path:
    project = root / "proj"
    (project / "src" / "pkg").mkdir(parents=True)
    (project / "tests").mkdir()
    required = sorted(
        p.stem for lane in LANES for p in (BORROMEANRINGS_HOME / "checks" / lane).glob("[0-9]*.sh")
    )
    (project / "borromeanrings.toml").write_text(
        '[project]\nlanguage = "python"\npackage = "pkg"\nsrc_dir = "src"\n'
        'tests_dir = "tests"\n\n[predicates]\nenabled = true\n\n'
        "[citations]\nenabled = true\n\n"
        # `true` stands in for the judge: a local command, no model, no network. It only
        # has to exist for 55_doc_drift and 56_critics to reach their programs.
        '[critic]\njudge_command = "true"\nrubrics = ["naming"]\n\n'
        '[test]\nfast_paths = ["tests"]\n\n[checks]\nrequired = ['
        + ", ".join(f'"{c}"' for c in required)
        + "]\n",
        encoding="utf-8",
    )
    (project / "src" / "pkg" / "__init__.py").write_text('"""pkg."""\n')
    (project / "README.md").write_text("# proj\n")
    (project / "Dockerfile").write_text("FROM scratch\n")  # 14_container has a file to read
    (project / "hello.sh").write_text('#!/usr/bin/env bash\necho "hello"\n')  # 16_shellcheck
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
    for argv in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "add", "-A"],
        [*git, "commit", "-qm", "chore: base"],
        ["git", "checkout", "-q", "-b", "feat/fixture"],
    ):
        subprocess.run(argv, cwd=project, capture_output=True, check=True)
    # The feature branch adds public surface, so the diff-reading checks have work to do.
    (project / "src" / "pkg" / "__init__.py").write_text(
        '"""pkg."""\n\n\ndef double(x: int) -> int:\n    """Double x."""\n    return 2 * x\n'
    )
    (project / "tests" / "test_pkg.py").write_text(
        "from pkg import double\n\n\ndef test_double() -> None:\n    assert double(2) == 4\n"
    )
    for argv in (["git", "add", "-A"], [*git, "commit", "-qm", "feat: double"]):
        subprocess.run(argv, cwd=project, capture_output=True, check=True)
    decoy = project / "meta_harness"
    decoy.mkdir()
    (decoy / "__init__.py").write_text(_DECOY)  # after the commit: untracked, still on sys.path
    return project


def test_every_trusted_check_program_runs_from_root(tmp_path: Path) -> None:
    project = _fixture(tmp_path)
    marker, log, bindir = tmp_path / "decoy-imported", tmp_path / "shim.log", tmp_path / "bin"
    bindir.mkdir()
    shim = bindir / "python3"
    shim.write_text(_SHIM)
    shim.chmod(0o755)
    real = subprocess.run(["bash", "-c", "command -v python3"], capture_output=True, text=True)

    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "CLAUDE_PROJECT_DIR")}
    env.update(
        PATH=f"{bindir}{os.pathsep}{env['PATH']}",
        REAL_PYTHON3=real.stdout.strip(),
        SHIM_LOG=str(log),
        BORROMEANRINGS_DECOY_MARKER=str(marker),
        BORROMEANRINGS_PROJECT=str(project),
        BORROMEANRINGS_HEAVY="0",
        BORROMEANRINGS_CHECK_TIMEOUT="300",
    )
    # Both lanes: 40_test's fast-path program runs only under --fast with fast_paths set.
    output = ""
    for lane_args in ([], ["--fast"]):
        proc = subprocess.run(
            ["bash", str(VERIFY), *lane_args],
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
            timeout=900,
        )
        output += f"{proc.stdout}{proc.stderr}"

    runs: dict[str, set[str]] = {}
    for line in log.read_text(encoding="utf-8").splitlines() if log.exists() else []:
        cwd, digest = line.split("\t")
        runs.setdefault(digest, set()).add(cwd)

    programs = _trusted_programs()
    assert len(programs) > 25, f"found only {sorted(programs.values())} — derivation broken"

    ran = {where for digest, where in programs.items() if digest in runs}
    not_run = sorted(set(programs.values()) - ran - set(UNREACHABLE_HERE))
    assert not not_run, f"these trusted programs never ran here: {not_run}\n{output}"
    stale = sorted(set(UNREACHABLE_HERE) & ran)
    assert not stale, f"listed as unreachable but ran — remove the excuse: {stale}"

    outside = sorted(
        f"{programs[d]} from {sorted(runs[d] - {'/'})}"
        for d in programs
        if runs.get(d, {"/"}) != {"/"}
    )
    assert not outside, f"trusted programs started outside /: {outside}"
    assert not marker.exists(), f"the decoy was imported:\n{marker.read_text()}\n{output}"
