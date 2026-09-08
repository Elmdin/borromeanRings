# SPEC — Portfolio status (roster health) command

**Status:** Implemented · **Realized by:** `src/meta_harness/verdict.py`,
`src/meta_harness/status.py`, `status.sh` · ADR-0046

## Problem
borromeanRings governs invariants *inside* each repo, but a maintainer running it
across many projects has **no portfolio-level view**: which projects are governed, what
each requires, whether its last gate was green, and whether it has drifted behind the
recommended check set. Today that answer requires `cd`-ing into each repo and running
the gate by hand (exactly the ad-hoc sweep this command replaces). The state is
invisible and easy to lose track of.

## Contract
Two pieces:

### 1. Verdict persistence (`verdict.py`)
On every gate run, `verify.sh` writes a compact, best-effort verdict record to
`.meta-harness/last_verdict.json` in the governed project (same evidence area as
receipts; git-ignored). Best-effort: a write failure never turns a real PASS into a
FAIL. Schema:

```json
{ "ok": true, "run_id": "…", "digest": "…", "harness_version": "…",
  "risk": "green",
  "intent": { "branch": "…", "head_sha": "…", "input_digest": "…" },
  "checks": [["00_build","pass"], ["40_test","pass"]],
  "evidence": [ { "check": "00_build", "command": "…", "exit_code": 0, "log": "…",
                  "log_bytes": 812, "content_sha256": "…", "lane": "fast" }, … ] }
```

`harness_version` is ADR-0048; `risk`, `intent` and `evidence` are ADR-0056 (see
`SPEC-verdict-evidence.md`). All are optional on read — older records parse with empty
defaults.

`read_last_verdict(project_root)` returns the parsed record or `None` (absent /
unreadable / malformed → `None`, never raises). This is a **last-known** signal, not a
live re-verification — `status --run` re-gates for freshness.

### 2. Status command (`status.py` + `status.sh`)
`status.sh [--run] [PATH ...]` reports one row per governed project:

- **discovery** — each `PATH` arg is a root to scan (default: `$HOME`); a governed
  project is any directory containing `borromeanrings.toml` (build/vendor/cache dirs
  skipped, depth-bounded). Explicit paths that are themselves governed projects are
  used directly.
- **git** — whether the project is a git repo (a non-repo is a real finding: history
  checks such as `12_secrets` fail closed there).
- **config drift** — whether `borromeanrings.toml` has uncommitted changes (adoption
  that isn't committed isn't real governance yet).
- **required** — the number of required checks the project enforces.
- **verdict** — the last persisted gate verdict (`pass`/`fail`/never-gated), or, with
  `--run`, a fresh gate result.
- **adoption drift** — recommended checks the project does not yet require, via
  `meta_harness.adopt.plan_adoption` (single source of the recommended set).

Output is a rendered table plus a one-line summary (`N governed · G green · …`). Exit
code is `0` for a clean report; `--run` propagates a non-zero exit when any project's
fresh gate fails (so it is CI-usable), while the default read-only report always
exits `0` (it reports state, it does not gate).

## Design (testability)
Pure core, thin impure shell:

- **Pure** — `build_status(facts) -> ProjectStatus` and `render(statuses) -> str` take
  already-gathered facts (git bool, config-dirty bool, required tuple, last verdict,
  changelog bool) and compute the row + table. Fully unit-tested.
- **Impure** — `gather(path)` runs git/fs/json reads and delegates to `build_status`;
  `discover_projects(roots)` walks the filesystem. Thin, exercised via tmp dirs.

`status.py` is a top-level consumer: nothing else imports it (keeps the module graph
acyclic — ARCHITECTURE.md §2). `verdict.py` depends only on stdlib.

## Guarantees
- **Reuses the single sources of truth** — `load_config` (spine) for required checks,
  `plan_adoption`/`RECOMMENDED` (adopt) for drift, the gate's own verdict for health.
  No duplicated policy.
- **Fail-soft reads** — a missing/malformed verdict, a non-repo, or an unreadable
  config degrades that one row to a clear note; it never crashes the roster view.
- **Advisory, not a gate** — the default report reads last-known state and never blocks;
  it is orientation, not enforcement. `--run` is the authoritative (re-gating) mode.

## Dogfood
Run against the maintainer's real portfolio (10 governed projects). It reproduces the
manual sweep: 9/10 green, surfaces spaceThink (not a git repo → `12_secrets` fails
closed) and any config-drift, with zero manual `cd`.
