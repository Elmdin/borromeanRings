# SPEC — ADR-discipline gate

**Status:** Implemented · **Realized by:** `src/meta_harness/adr_discipline.py`,
`checks/shared/13_adr.sh` · ADR-0043

## Problem

borromeanRings documents load-bearing decisions as ADRs by convention only. A new
capability can land with no recorded rationale and nothing catches it (coverage-map
rows D/H). This is the deterministic, no-telemetry slice of the delivery/process
matrix — decision traceability as a gate.

## Contract

`13_adr` fails closed when feature work changes source without recording a decision:

1. **Trigger** — only when the current branch name starts with one of
   `[adr].require_prefixes` (default `["feat/"]`). Non-feature branches (`fix/`,
   `docs/`, protected `dev`/`main`, detached HEAD) pass.
2. **Diff** — changed paths are `git diff --relative --name-only <merge-base>...HEAD`
   against the integration branch (`origin/dev` → `dev` → `origin/main` → `main`).
   `--relative` keeps prefixes correct for a git-root *or* subdirectory project. No
   base (first commit / detached) ⇒ pass. Committed changes only (a merge/PR-time gate).
3. **Rule** — `adr_violation(branch, changed, src_dir, adr_dir, require_prefixes)`:
   if any changed path is under `src_dir/` and **none** is under `adr_dir/` (default
   `docs/adr/`), it's a violation; otherwise pass. Prefix matching is boundary-safe
   (`src_generated/` does not match `src/`).

Config `[adr]`: `dir` (default `docs/adr`), `require_prefixes` (default `["feat/"]`).
Off unless `13_adr` is in `[checks].required`.

## Guarantees

- **Threshold-free** — a yes/no decision-traceability check, no arbitrary size target.
- **Deterministic & native** — git diff + a pure function; unit-tested and
  adversarially verified (feat+src+no-ADR fails; +ADR passes; `fix/` passes).
- **Portable** — `--relative` diffing works for git-root and subdirectory projects.
- **Right-scoped** — merge/PR-time (committed changes); fixes and doc/test-only
  changes never trigger it.
