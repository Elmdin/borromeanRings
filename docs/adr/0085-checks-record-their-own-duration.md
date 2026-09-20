# ADR-0085 — A check records its own duration, in its own receipt

**Status:** Accepted · 2026-09-19 · issue #253 ·
**Relates to:** ADR-0026 (tamper-evident receipts), ADR-0049 (honest `noop`),
ADR-0076 (the `worktree` executor), ADR-0081 (the fast lane)

## Context

On 2026-09-19 `dev`'s gate went red with `40_test TIMED OUT after 900s`, and #252 raised
the per-check bound to 1800s so the merge queue could drain. That was headroom, not a
fix: the suite had grown across a dozen merges and nothing in the run said which check
spent the time, or which part of it. The only way to find out was to re-run the suite
locally under `pytest --durations`, on a different machine than the one that failed.

A bound raised against no measurement stops meaning anything, and the next raise will be
argued the same way. The gate already writes a receipt per check, with a content hash
over every field. The measurement belongs there.

## Decision

1. **Each check records its own wall time** in its receipt as `duration_ms`, measured
   from the moment it sources `checks/_lib.sh` — its first act — to the moment it writes
   the receipt. That brackets the check's own work, not the gate's bookkeeping around it.
2. **The duration is inside `content_sha256`.** A number that can be rewritten after the
   fact is not a measurement anybody can rely on, and the receipt already carries
   everything else under that digest (ADR-0026).
3. **The gate prints the slowest few** (`meta_harness.timings.timings_line`), on green
   runs and red ones alike, so the number is in the CI log of the run that was slow
   rather than in a later local re-run.
4. **It is a report, never a rule.** No budget, no threshold, no effect on the verdict —
   consistent with this project's refusal of arbitrary metric targets. A slow check is a
   fact about a run; what to do about it is a person's decision.
5. **Absent means not measured,** never zero: receipts from an older harness, or copied
   in by the `worktree` executor, are left out of the ranking rather than ranked fastest.
6. **`duration_ms` is volatile for conformance** (`SPEC-executor.md` §5.2). Two honest
   runs of the same snapshot never share a duration; an executor on a busier host has
   not diverged.

## Alternatives considered

- **Time each check from `verify.sh` instead.** The gate runs the check scripts, so it
  could time them from outside with no change to the library. Rejected: the receipt is
  written by the check itself and sealed by its hash, so the gate would have to rewrite
  a sealed receipt to add the field — exactly the edit-after-the-fact that ADR-0026
  exists to detect — or keep the timings in a second, unsealed place where nothing
  guarantees they describe the receipts beside them.
- **Print `pytest --durations` from `40_test` and stop there.** Cheaper, and it would
  have answered this particular question. Rejected as the whole answer: it measures one
  check in one language lane, and the next surprise will be somewhere else. It is still
  worth doing *inside* that check, and is not excluded by this decision.
- **Measure nothing; raise the bound when it fires.** What happened, and the reason this
  ADR exists.
- **Make the duration a gate.** Rejected on the project's own terms: a time budget is an
  arbitrary threshold, and a check that gets slower for a good reason (more tests) would
  fail for it.

## Consequences

- (+) The run that was slow says so itself, in CI, with the check named.
- (+) The number is as trustworthy as the rest of the receipt, and no more: a local
  forger who re-hashes the whole receipt can re-time it, as they can re-state it.
- (+) `.meta-harness/receipts/*/` becomes a history of where the gate's time goes, per
  project, for anyone who wants the trend later.
- (−) The receipt schema grew a field. Older receipts have none, so every reader must
  treat absent as *not measured* — the ranking does, and the spec says so.
- (−) The measurement includes the check's own start-up (one Python process for the
  library's helpers). It is bounded by a few hundred milliseconds and is the same for
  every check, so the ranking is unaffected; the absolute figure for a fast check is
  start-up-dominated and should be read that way.
- (−) `EPOCHREALTIME` is bash 5+; on bash 3.2 (macOS's system bash) the fallback is whole
  seconds. A coarser measurement there, never a wrong one.
