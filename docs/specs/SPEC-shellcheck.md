# SPEC — Shell lint gate (`16_shellcheck`)

**Status:** Accepted · **ADR:** 0050 · **Closes:** #52

## 1. Problem

Core borromeanRings logic lives in shell — `verify.sh`, every `checks/*.sh`, the four
Claude hooks, `merge.sh`, `init.sh`, `adopt.sh`, `status.sh`, `ledger.sh`. That is
**trust-root code**: it decides whether other people's projects pass. It was ungated while
the Python beside it faced twenty checks.

## 2. Contract

| Situation | Status |
|---|---|
| shellcheck absent from PATH | `error` (127) — a missing tool is never a skip (ADR-0049) |
| No shell scripts in the project | `noop` — legitimate for pure Python; never a hollow `pass` |
| One or more findings, any severity | `fail` |
| Clean | `pass` (log states how many scripts were scanned) |

Fail-closed on **any** severity. No threshold, no ratchet: a lint finding is binary.

## 3. File selection

- **Git repo:** `git ls-files '*.sh'` — tracked only, so an untracked scratch script can
  never fail someone's gate.
- **Non-git:** bounded walk via `source_coherence.walk_sources(root, ".sh")`, pruning
  vendored/cache directories.

Scanning is a **single** shellcheck invocation. `xargs` is deliberately avoided: it splits
long lists across invocations and yields only the last exit code, dropping earlier
findings — a fail-open hole in gate plumbing.

## 4. Configuration (`[shell]`)

| Key | Default | Purpose |
|---|---|---|
| `source_paths` | `["SCRIPTDIR", "SCRIPTDIR/.."]` | `-P` entries so `source`d libraries resolve statically |
| `exclude` | `[]` | `-e` per-code escape hatch; each entry needs a written justification |

**Why `source_paths` rather than excluding SC1091.** Scripts source a sibling library via
a runtime-computed path shellcheck cannot follow, producing 33 SC1091 notes in this repo.
`-e SC1091` would silence them *and* every genuine unreadable-source bug. `-x` plus
`SCRIPTDIR` resolves all 33 correctly, so the escape hatch stays empty.

## 5. Edge cases

| Case | Behaviour |
|---|---|
| Script sourced, no shebang | Author adds `# shellcheck shell=bash` (SC2148) |
| Untracked `.sh` in a git repo | Not scanned — never fails a gate |
| Project not a git repo | Filesystem walk, vendored dirs pruned |
| A rule genuinely inapplicable | `[shell].exclude` with justification — not a blanket mute |

## 6. Verification

- Integration: a planted shell defect is **rejected**; clean shell **passes** (negative
  control); a project with no shell reports **`noop`** and the gate prints
  `inspected NOTHING`.
- borromeanRings's own 43 scripts pass at zero findings.
