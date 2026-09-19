"""Every check's trusted Python runs from ``/``, observed rather than grepped (#240).

``python3 -`` puts the working directory first on ``sys.path``, so a ``meta_harness/``
planted in the governed project replaces the gate's own analysis unless the step runs
through ``borromeanrings_py`` (``checks/_py.sh``, which starts from ``/``). The static
guard in ``test_verify_no_sys_path_forge.py`` reads the scripts' text; this test watches
them run.

A decoy that is never imported proves nothing if the step that would have imported it
never ran — a check that exits early because it is not required, or because its tool is
absent, is silently vacuous. So this test has a POSITIVE control. A ``python3`` shim on
``PATH`` records, for every ``python3 -`` start, the working directory, the check script
that started it, and the ``meta_harness`` modules its stdin program imports. The test
then requires, for every check whose source contains such a program:

* it RAN in this fixture (or is named below as unreachable here, with the reason),
* every run started from ``/``, and
* the decoy ``meta_harness/`` at the project root was never imported.

The set of checks is derived from the scripts' text, so a check added later is covered
without editing this file. The fixture is a Python project that requires every shared
and Python-lane check, so both lanes run in full.
"""

import os
import re
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
LANES = ("shared", "python")

# Checks whose trusted program does not run on this fixture, and why. Every entry must
# stay true: the test fails if a listed check DOES run its program here (a stale excuse).
UNREACHABLE_HERE: dict[str, str] = {}

_DECOY = """\
import os
import sys

with open(os.environ["BORROMEANRINGS_DECOY_MARKER"], "a", encoding="utf-8") as fh:
    fh.write(" ".join(sys.argv) + "\\n")
raise ImportError("decoy meta_harness imported from the governed project")
"""

# Logs "<cwd>\t<check script>\t<modules>" for each `python3 -`, then runs the real one.
_SHIM = """\
#!/usr/bin/env bash
if [ "${1:-}" = "-" ]; then
  body="$(cat)"
  parent="$(tr '\\0' ' ' < /proc/$PPID/cmdline |
    grep -o 'checks/[a-z]*/[0-9][0-9A-Za-z_]*\\.sh' | head -1)"
  mods="$(printf '%s\\n' "$body" | grep -oE '^(from|import) meta_harness[.a-z_]*' |
    sort -u | tr '\\n' ' ')"
  printf '%s\\t%s\\t%s\\n' "$PWD" "${parent:--}" "$mods" >> "$SHIM_LOG"
  exec "$REAL_PYTHON3" "$@" <<<"$body"
fi
exec "$REAL_PYTHON3" "$@"
"""

_PROGRAM = re.compile(r"borromeanrings_py -[^c].*<<\s*'?(\w+)'?")


def _checks_with_a_trusted_program() -> set[str]:
    """Check scripts (repo-relative) that start a heredoc program importing meta_harness."""
    found: set[str] = set()
    for lane in LANES:
        for script in sorted((BORROMEANRINGS_HOME / "checks" / lane).glob("[0-9]*.sh")):
            text = script.read_text(encoding="utf-8")
            lines = text.splitlines()
            for i, line in enumerate(lines):
                joined = line
                j = i
                while joined.rstrip().endswith("\\") and j + 1 < len(lines):
                    j += 1
                    joined = joined.rstrip()[:-1] + lines[j]
                m = _PROGRAM.search(joined) if "borromeanrings_py -" in line else None
                if not m:
                    continue
                end = next(
                    (k for k in range(j + 1, len(lines)) if lines[k].strip() == m.group(1)), None
                )
                body = "\n".join(lines[j + 1 : end])
                if re.search(r"^(from|import) meta_harness", body, re.M):
                    found.add(script.relative_to(BORROMEANRINGS_HOME).as_posix())
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
        'tests_dir = "tests"\n\n[checks]\nrequired = ['
        + ", ".join(f'"{c}"' for c in required)
        + "]\n",
        encoding="utf-8",
    )
    (project / "src" / "pkg" / "__init__.py").write_text(
        '"""pkg."""\n\n\ndef double(x: int) -> int:\n    """Double x."""\n    return 2 * x\n'
    )
    (project / "tests" / "test_pkg.py").write_text(
        "from pkg import double\n\n\ndef test_double() -> None:\n    assert double(2) == 4\n"
    )
    (project / "README.md").write_text("# proj\n")
    for argv in (
        ["git", "init", "-q", "-b", "feat/fixture"],
        ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "feat: init"],
    ):
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
    proc = subprocess.run(
        ["bash", str(VERIFY)], cwd=project, env=env, capture_output=True, text=True, timeout=900
    )
    output = f"{proc.stdout}{proc.stderr}"

    runs: dict[str, set[str]] = {}
    for line in log.read_text(encoding="utf-8").splitlines() if log.exists() else []:
        cwd, script, mods = line.split("\t")
        if script != "-" and "meta_harness" in mods:
            runs.setdefault(script, set()).add(cwd)

    expected = _checks_with_a_trusted_program()
    assert len(expected) > 20, f"found only {sorted(expected)} — the derivation is broken"

    not_run = sorted(expected - set(runs) - set(UNREACHABLE_HERE))
    assert not not_run, f"these checks never ran their trusted program here: {not_run}\n{output}"
    stale = sorted(set(UNREACHABLE_HERE) & set(runs))
    assert not stale, f"listed as unreachable but ran — remove the excuse: {stale}"

    from_project = sorted(s for s, cwds in runs.items() if cwds != {"/"})
    assert not from_project, f"trusted programs started outside /: {from_project}"
    assert not marker.exists(), f"the decoy was imported:\n{marker.read_text()}\n{output}"
