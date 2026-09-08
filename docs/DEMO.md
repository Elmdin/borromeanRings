# Demo — the gate, end to end, on a throwaway project

`./demo.sh` (repo root) is a scripted, reproducible walk-through of borromeanRings
governing a project it has never seen. It is also a test: every step asserts the exact
verdict it expects and the script exits non-zero on the first deviation, so if this
document and the code ever disagree, the demo fails before the document misleads anyone.

```bash
./demo.sh          # build the project in a temp dir, run every step, delete it
./demo.sh --keep   # same, but leave the project on disk (the path is printed)
```

Prerequisites: `python3`, `git`, and the Python check toolchain on `PATH` — `ruff`,
`mypy`, `pytest` (with `pytest-cov`), `bandit`. `pip install -e ".[dev]"` from the
checkout installs them. The demo refuses to start (exit 2) if any is missing, so a
missing tool can never read as a passing step.

Nothing is copied into the demo project: `init.sh` writes a `borromeanrings.toml` and a
`.claude/settings.json` whose hooks point back at *this* checkout (ADR-0013). The
project's `.meta-harness/` directory receives the receipts.

## The steps, and what each one proves

| # | Step | Command | Asserts | Proves |
|---|---|---|---|---|
| 1 | Govern an empty project | `init.sh <dir>` | exit 0; `borromeanrings.toml` and `.claude/settings.json` exist | governance is opt-in and by reference — two files, no copy |
| 2 | Gate the empty project | `verify.sh` | `RESULT: PASS` **and** `inspected NOTHING: 4 of 7` | a **hollow green**: greenfield is not red, but the gate names every check that inspected nothing (ADR-0049) |
| 3 | Add `src/app/core.py`, a test, `pyproject.toml`; set `[project].package` | `verify.sh` | `RESULT: PASS` and **no** `inspected NOTHING` line | a **real green**: every required check inspected something |
| 4 | Change `add()` to `return "oops"` | `verify.sh` | exit 1; `RESULT: FAIL`; `30_typecheck FAIL`; `40_test FAIL` | the gate **fails closed** on a violation, and says which checks caught it |
| 5 | Restore `add()` | `verify.sh` | `RESULT: PASS` | the fix is verified by the same gate, not by the author's word |
| 6 | Adopt the recommended set | `adopt.sh <dir>` then `verify.sh` | `added [`, `seeded`; then `RESULT: PASS` | `adopt.sh` seeds each ratchet baseline from the current state, so the stricter gate is green on its first run and holds the line from there (ADR-0041) |
| 7 | Self-status | `status.sh` from inside the project | exit 0; `Governed: yes`; `Last verdict: PASS`; `Enforcement: AUTO` | the project can report how it is governed, whether enforcement is actually wired, and how hollow its last green was (ADR-0046 / 0049) |

Step 2's hollow set is `00_build`, `30_typecheck`, `40_test`, `50_security` — the
checks that need source to inspect. `05_hygiene` passes because `init.sh`'s starter
config declares no required files; `10_format` and `20_lint` pass because ruff over an
empty tree finds nothing to complain about. Only the first four report `noop`, and
that distinction is the point: *"I inspected nothing"* and *"I inspected everything and
it is clean"* must never look the same.

After step 6 the gate reports `inspected NOTHING: 1 of 14 — 04_self_description`: the
demo project's README states no check count, so that check has nothing to verify and
says so. It is an honest `noop`, not a `pass`.

## Transcript

The transcript below is the output of one run (paths abbreviated: the temp project is
`/tmp/borromeanrings-demo.lvUAFn`, the checkout is `~/borromeanRings`; the `harness-version`
stamp, run ids and run digests differ per run). The README quotes the green, hollow-green, red and status blocks
from it verbatim.

```text
### 1. Govern an empty project (init.sh)
$ bash ~/borromeanRings/init.sh /tmp/borromeanrings-demo.lvUAFn
wrote /tmp/borromeanrings-demo.lvUAFn/borromeanrings.toml  (edit it for your project)
wrote /tmp/borromeanrings-demo.lvUAFn/.claude/settings.json  (hooks reference borromeanRings at ~/borromeanRings)
installed borromeanRings skills into /tmp/borromeanrings-demo.lvUAFn/.claude/skills/ (e.g. borromeanrings-research)

borromeanRings now governs /tmp/borromeanrings-demo.lvUAFn. Run the gate with:
  cd '/tmp/borromeanrings-demo.lvUAFn' && '~/borromeanRings/verify.sh'
  (or: BORROMEANRINGS_PROJECT='/tmp/borromeanrings-demo.lvUAFn' '~/borromeanRings/verify.sh')

### 2. Run the gate on nothing: a HOLLOW green
$ BORROMEANRINGS_PROJECT=/tmp/borromeanrings-demo.lvUAFn ~/borromeanRings/verify.sh

  borromeanRings gate  (project: /tmp/borromeanrings-demo.lvUAFn)
  harness-version: 8daa73e
  --------------------------
  00_build       NOOP
  05_hygiene     PASS
  10_format      PASS
  20_lint        PASS
  30_typecheck   NOOP
  40_test        NOOP
  50_security    NOOP
  --------------------------
  RESULT: PASS
  inspected NOTHING: 4 of 7 — 00_build, 30_typecheck, 40_test, 50_security
  run-digest: 8775e9ace40869d92de2de6db9a1371436048999db295f39f5b16db4683cc39c

### 3. Add real code and tests: a REAL green
(wrote src/app/core.py, tests/test_core.py, pyproject.toml; set [project].package = "app")
$ BORROMEANRINGS_PROJECT=/tmp/borromeanrings-demo.lvUAFn ~/borromeanRings/verify.sh

  borromeanRings gate  (project: /tmp/borromeanrings-demo.lvUAFn)
  harness-version: 8daa73e
  --------------------------
  00_build       PASS
  05_hygiene     PASS
  10_format      PASS
  20_lint        PASS
  30_typecheck   PASS
  40_test        PASS
  50_security    PASS
  --------------------------
  RESULT: PASS
  run-digest: efb83519cf286327865b64ab2cea0c2a53dc3bb21f13d2b49b592c49fb818587

### 4. Introduce a violation (return a str from an int function): RED
$ BORROMEANRINGS_PROJECT=/tmp/borromeanrings-demo.lvUAFn ~/borromeanRings/verify.sh

  borromeanRings gate  (project: /tmp/borromeanrings-demo.lvUAFn)
  harness-version: 8daa73e
  --------------------------
  00_build       PASS
  05_hygiene     PASS
  10_format      PASS
  20_lint        PASS
  30_typecheck   FAIL
  40_test        FAIL
  50_security    PASS
  --------------------------
  RESULT: FAIL
  run-digest: b82f6c4a7189ccc4cbfebd29d84979cf3c244ce13eac2da16ac1fd3c5fa1f384
  One or more checks failed or produced no receipt; see logs in the run dir.

### 5. Fix it: green again
$ BORROMEANRINGS_PROJECT=/tmp/borromeanrings-demo.lvUAFn ~/borromeanRings/verify.sh

  borromeanRings gate  (project: /tmp/borromeanrings-demo.lvUAFn)
  harness-version: 8daa73e
  --------------------------
  00_build       PASS
  05_hygiene     PASS
  10_format      PASS
  20_lint        PASS
  30_typecheck   PASS
  40_test        PASS
  50_security    PASS
  --------------------------
  RESULT: PASS
  run-digest: 63526f0c98050e4d90adde41f77cb9ce7096b696fd41b3e559950c3239f39166

### 6. Adopt the recommended quality/security checks (adopt.sh)
$ bash ~/borromeanRings/adopt.sh /tmp/borromeanrings-demo.lvUAFn
adopt: borromeanrings-demo.lvUAFn: added ['12_secrets', '11_changelog', '32_complexity', '33_coupling', '45_docstrings', '01_source_coherence', '04_self_description']
  seeded .borromeanrings-complexity-baseline = 1
  seeded .borromeanrings-coupling-baseline = 0
  seeded .borromeanrings-docstring-baseline = 0.000000
  created CHANGELOG.md
  [checks].required is now 14 checks.
  next: run the gate to confirm green:
    BORROMEANRINGS_PROJECT="/tmp/borromeanrings-demo.lvUAFn" bash "~/borromeanRings/verify.sh"
  refreshed borromeanRings skills in /tmp/borromeanrings-demo.lvUAFn/.claude/skills/
$ BORROMEANRINGS_PROJECT=/tmp/borromeanrings-demo.lvUAFn ~/borromeanRings/verify.sh

  borromeanRings gate  (project: /tmp/borromeanrings-demo.lvUAFn)
  harness-version: 8daa73e
  ---------------------------------
  00_build              PASS
  05_hygiene            PASS
  10_format             PASS
  20_lint               PASS
  30_typecheck          PASS
  40_test               PASS
  50_security           PASS
  12_secrets            PASS
  11_changelog          PASS
  32_complexity         PASS
  33_coupling           PASS
  45_docstrings         PASS
  01_source_coherence   PASS
  04_self_description   NOOP
  ---------------------------------
  RESULT: PASS
  inspected NOTHING: 1 of 14 — 04_self_description
  run-digest: 8afcc8c933851006a1830237de130cf5ef7337027f7d1eab8ad042f18281bb27

### 7. Ask the project how it is governed (status.sh)
$ cd /tmp/borromeanrings-demo.lvUAFn && ~/borromeanRings/status.sh

  borromeanRings status — borromeanrings-demo.lvUAFn   (this project only)
  ------------------------------------------------------------
  Governed:     yes · 14 required check(s)
  Last verdict: PASS · run 20260908T153759Z-780660 · by borromeanRings 8daa73e
  ⚠ Hollow:     1 of 14 checks inspected NOTHING —
                04_self_description
                a green resting on these proves less than it looks like.
  Enforcement: AUTO — 4/4 hooks wired to this borromeanRings
  Installed:    borromeanRings 8daa73e at ~/borromeanRings
  Re-gate:      ~/borromeanRings/verify.sh

demo: every step matched its expected verdict.
```

## Where to look when a step deviates

The demo prints `demo: DEVIATION at step N — …` and exits 1. The receipts for the
failing run are in the demo project's `.meta-harness/receipts/<run-id>/` — re-run with
`--keep` to retain them — and each check's `<id>.log` carries the underlying tool's
output (for step 4 that is mypy's `Incompatible return value type` and pytest's
`AssertionError: assert 'oops' == 5`). A deviation is a real signal: either the harness
changed behaviour or the environment is missing something, and either way the README's
quoted transcript is stale until it is fixed.

## Beyond the demo

The demo runs the gate by hand. In a live Claude Code session opened in the governed
project, the same gate runs from the **Stop** hook and blocks the agent until it is
green. `docs/TESTING.md` walks through that, plus the prompt-rewrite, dangerous-command
guard, and auto-format hooks, on a fresh project.
