# SPEC — Self-status, honest no-op reporting, and the source-coherence guard

**Status:** Draft (pre-implementation)
**Drives:** ADR-0049
**Supersedes nothing.** Amends the *default* behaviour of `status.sh` (ADR-0046).

## 1. Problem

Three defects, one root cause.

A governed project reported **`ok: true`, 12/12 green** while **seven** of those twelve
checks had inspected *nothing at all*: its `borromeanrings.toml` declared
`src_dir = "src"`, but no `src/` existed — the real code lived in `tools/`. The gate was
honest in each receipt log ("greenfield — nothing to analyze"), but the *verdict* said
`pass`, and nobody reads twelve logs behind a green verdict.

Root cause: `checks/_lib.sh` derives status **solely** from exit code
(`[ "$code" -eq 0 ] && status="pass"`), so **"I inspected nothing" and "I inspected
everything and it is clean" are structurally identical**. borromeanRings already
recognised this hazard once — `12_secrets` was hardened to fail closed on a non-git
directory precisely so "can't scan" could not read as "nothing to scan" (ADR-0042) — but
never generalised it.

The three defects:

- **D1 — invisible vacuity.** A no-op check is indistinguishable from a real pass in the
  verdict, the history, and every downstream view.
- **D2 — undetected misconfiguration.** A `src_dir` that points at nothing while the repo
  demonstrably contains source elsewhere is a *config error*, not a greenfield project,
  and nothing detects it.
- **D3 — no self-report.** To answer "is borromeanRings working here?" a user must read
  raw receipts. The only cross-project view (`status.sh`) defaults to walking **all of
  `$HOME`**, which is both the wrong scope for the question and an unwanted implicit
  portfolio scan.

## 2. Goals

- **G1** Any Claude session, in any governed project, can ask "check my borromeanRings
  status" and get **that project's** status — including whether its greens are real.
- **G2** A no-op check is visibly distinct from a real pass at every level: receipt,
  gate output, persisted verdict, history.
- **G3** A source path that resolves to zero files while tracked source exists elsewhere
  **fails the gate**.
- **G4** Single-project is the **default** scope; the portfolio roster is opt-in.

## 3. Non-goals

- No change to what any check *measures* (only to how "nothing measured" is reported).
- No telemetry, no network, no cross-project state. Every artefact stays inside the
  governed project (unchanged from ADR-0046/0047).
- Not auto-fixing a misconfigured project — the guard reports and fails; the human edits
  the config.

## 4. Contracts

### 4.1 Receipt status vocabulary

| Status | Meaning | Gate effect |
|---|---|---|
| `pass` | ran, inspected ≥1 unit, found no violation | non-failing |
| `noop` | ran, inspected **nothing** (nothing to inspect, or rule off) | **non-failing, but reported** |
| `fail` | ran, found a violation | failing |
| `error` | could not run (missing tool) | failing |

**Fail-closed invariant (critical).** `verify.sh` must treat non-failing status as an
**explicit allowlist**, never a negation:

```python
NON_FAILING = {"pass", "noop"}
if status not in NON_FAILING:
    ok = False
```

A typo'd, unknown, or future status therefore still fails. Replacing the current
`status != "pass"` with `status not in NON_FAILING` is the *only* verdict-logic change.

`_lib.sh` gains one helper, mirroring `emit_receipt`'s signature:

```
emit_noop <id> <command> <log>    # writes a receipt with status "noop", exit_code 0
```

Every vacuous branch calls `emit_noop` instead of `emit_receipt … "pass"`.

### 4.2 Source-coherence guard (new check)

`checks/python/01_source_coherence.sh` + pure core
`src/meta_harness/source_coherence.py`.

It **must** resolve the source path exactly as the checks it protects do — the same
`find "$PROJECT_ROOT/$src_dir" -name '*.py'` semantics used by `00_build`, `30_typecheck`,
`32_complexity`, `33_coupling`, `45_docstrings` — otherwise the guard and the checks could
disagree.

Pure decision function (no I/O):

```python
def assess(*, configured_count: int, tracked_elsewhere: Sequence[str],
           configured_path: str) -> Coherence
```

| configured_count | tracked source elsewhere | Verdict | Rationale |
|---|---|---|---|
| > 0 | any | `pass` | config resolves to real code |
| 0 | none | `noop` | genuinely greenfield — never force scaffolding |
| 0 | ≥ 1 | **`fail`** | **misconfiguration**: code exists, gate is blind to it |

The failure message must name where the source actually lives (top offending
directories, counted) so the fix is a one-line config edit.

**Gathering (thin wrapper, outside the pure core):** "tracked" means `git ls-files`
(untracked scratch files must never fail a gate). `git -C <dir> ls-files` correctly scopes
to a subdirectory project and returns subdir-relative paths (verified against
`examples/textkit`). For a **non-git** project, fall back to a bounded `os.walk` reusing
`status._SKIP_DIRS` for pruning.

**Opt-in.** Like every check, it applies only where listed in `[checks].required`
(per-project opt-in governance). It is added to `adopt.py`'s `RECOMMENDED` set so
`adopt.sh` offers it.

### 4.3 Self-status report

`status.sh` with **no arguments** reports the current project only:

```
borromeanRings status — <project>            (this project only)

  Governed:     yes · N required checks
  Harness:      <version that last ran> · installed <git describe>
  Enforcement:  auto (N/N hooks wired) | MANUAL ONLY (hooks present but disabled)
  Last verdict: PASS · <run_id>
  Reality:      11 inspected · 7 inspected NOTHING → 00_build, 30_typecheck, …
  Adoption:     recommended but not required: 01_source_coherence, …
  Refresh:      <BORROMEANRINGS_HOME>/verify.sh
```

**Enforcement detection.** Read the project's `.claude/settings.json`; classify as
`auto` when a `hooks` key wires hooks pointing at `$BORROMEANRINGS_HOME`, `manual` when
hooks are absent or parked under a disabled key (e.g. `_disabled_hooks_*`). This is
read-only and must never rewrite the file — enabling enforcement is a human decision.

**Reality line.** Derived from the persisted verdict's per-check statuses (§4.1); this is
what makes G1 answerable without reading receipts.

### 4.4 CLI scope (amends ADR-0046)

| Invocation | Scope |
|---|---|
| `status.sh` | **this project only** (new default) |
| `status.sh PATH…` | the named roots |
| `status.sh --all [ROOT…]` | portfolio roster; default root `$HOME` (the old default) |

`--run` and `--list` compose with all three. The roster is preserved, only demoted.

## 5. Edge cases

| Case | Required behaviour |
|---|---|
| Genuinely greenfield (0 source anywhere) | `noop`, gate passes — planning is never forced to scaffold |
| `src_dir` empty, tracked source elsewhere | **fail** with the offending directories named |
| Source present but untracked only | pass — untracked files never fail a gate |
| Non-git project | bounded `os.walk` fallback; still decidable |
| Subdirectory project inside a parent repo | `git -C` scoping (verified: no parent leakage) |
| `status.sh` run outside any governed project | clear "not governed — run init.sh" message, exit 0 (advisory) |
| Old verdict written before `noop` existed | parses unchanged; reality line degrades to "unknown", never crashes |
| Unknown/typo status in a receipt | **fails** (allowlist, not negation) |

## 6. Verification

- Unit tests for `source_coherence.assess` — all three branches + boundaries.
- Unit tests for the enforcement classifier (auto / disabled / absent / foreign-path).
- Unit test: verdict round-trips a `noop` status.
- **Fail-closed regression test: an unknown status string must fail the gate.** This is
  the highest-risk change; it is what stops `noop` from becoming a hole.
- Integration test: a fixture project with a misconfigured `src_dir` gates **red**; a
  genuinely-greenfield fixture gates **green with noop**.
- The adversarial known-bad corpus (ADR-0025) must still be rejected.
- borromeanRings's own gate must stay green (85 tracked `.py`, 38 under `src/` ⇒ guard
  passes).

## 7. Blast radius (measured, not assumed)

Across the maintainer's governed projects, the guard flags exactly the misconfigured
ones and leaves genuinely-greenfield and correctly-configured projects untouched.
`examples/textkit` (package `textkit`, `src_dir` `src`, 3 tracked `.py`) passes.
