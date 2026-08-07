# ADR-0043 — ADR-discipline gate

**Status:** Accepted

## Context
borromeanRings records every load-bearing decision as an ADR (`docs/adr/NNNN-*.md`)
— but by **convention**, not enforcement. The coverage map lists this as a standing
gap (rows D/H: *"ADR present for load-bearing decisions — by convention, not gated"*).
A new capability can land with no recorded rationale, and nothing catches it. This is
the buildable, deterministic slice of matrix **#3 (delivery / process)**: true DORA
flow-metrics (deploy frequency, lead time, MTTR, change-fail) need CI/deploy
**telemetry** borromeanRings doesn't collect, and their git-derivable proxies (PR
size) only fit **arbitrary thresholds** the project rejects. Decision-traceability
does not — it's a clean yes/no.

## Decision
Add `13_adr` + `meta_harness.adr_discipline`: on a branch whose name starts with a
declared prefix (default `feat/`), a change that touches `src_dir` must also add or
modify a file under `[adr].dir` (default `docs/adr/`). Git-derivable from the diff vs
the merge-base; no threshold. Off unless `13_adr` is in `[checks].required`.
Evaluated on **committed** changes — a merge/PR-time gate (CI), where the branch's
commits are the unit of review; it deliberately does not try to judge uncommitted
working-tree state.

## Alternatives considered
- **A PR/commit-size ratchet** (the other #3 candidate) — rejected as the first
  build: change size is per-change, not a monotonic metric a ratchet fits, and a
  size *limit* is exactly the arbitrary target the project avoids. Batch-size stays a
  possible advisory (T3) later.
- **Require an ADR for *every* feature change, however small** — rejected as too
  blunt; but scoping the trigger to "touches `src_dir`" is a good proxy for "changes
  behavior / adds capability" without a size heuristic. Fixes (`fix/`), docs, and
  test-only changes are exempt by construction.
- **Real DORA metrics now** — rejected: they require a telemetry integration
  (reading CI/deploy history) that is a separate, larger capability and arguably
  archetype-gated. Documented as telemetry-gated in the coverage map, not forced.
- **Parse commit messages for an `ADR-NNNN` reference** instead of a touched file —
  rejected: a touched `docs/adr/` file is a stronger, harder-to-fake signal that the
  decision was actually *written down*, not just name-dropped.

## Consequences
- (+) A feature can no longer add source without recording why — decision
  traceability becomes a gate, not a hope. Dogfoods perfectly: borromeanRings already
  adds an ADR per feature (this one included).
- (+) Deterministic, threshold-free, native, unit-tested, and adversarially verified
  (feat+src+no-ADR fails; adding an ADR passes; `fix/` passes).
- (−) Merge/PR-time only — the fast Stop-hook gate can't judge it before the work is
  committed. That's the right scope for a decision-traceability gate.
- (−) Opt-in and prefix-based: a project with a different feature-branch convention
  sets `[adr].require_prefixes`; one that doesn't want it omits `13_adr`.
