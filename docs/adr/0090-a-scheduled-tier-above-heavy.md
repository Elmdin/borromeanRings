# ADR-0090 — A scheduled tier above heavy: what a pull request should not pay for

**Status:** Accepted · 2026-09-25 · audit of 2026-09-20 ·
**Relates to:** ADR-0033 (the heavy CI tier), ADR-0081 (the fast interactive lane),
ADR-0022 (the mutation ratchet), ADR-0085 (checks record their own duration), #253

## Context

Every pull request here costs a full CI round, and branch protection makes those rounds
strictly serial — a PR cannot merge until it is up to date, so *N* changes cost *N*
rounds. Measured on `dev` with the per-check durations ADR-0085 added:

```
slowest: 60_mutation 13m 54s · 40_test 7m 11s · 16_shellcheck 6.6s
```

**Mutation testing is 14 minutes of a ~25-minute round.** What it buys per round, from
the audit:

- the baseline is `0.80`, set in a single commit on 2026-07-25, and has never moved;
- `setup.cfg` excludes 61 of 62 integration files from the sandbox, so it scores the unit
  suite — the part of the suite least likely to regress silently;
- its real guarantee, the fail-closed refusal of a vacuous `1.0` score (ADR-0022), is
  worth keeping and does not need to run on every pull request to keep it.

ADR-0033 already made this distinction once: some checks are too expensive for the inner
loop, so they run in CI instead of on every Stop. The same argument has simply moved up a
level — some checks are too expensive for *every pull request*, and belong on a schedule.

## Decision

1. **A third tier: `scheduled`.** `checks/scheduled/` holds checks that run only under
   `verify.sh --scheduled`; `[checks].scheduled` is the set graded in that lane. Declared
   in config like every other set, never hardcoded.
2. **`--scheduled` implies `--heavy`,** which implies the full lane. The tier that costs
   the most must never become a way to run *less* than a pre-merge round.
3. **`60_mutation` moves into it.** Pull requests stop paying 14 minutes each; the trunk
   pays it once a day (`.github/workflows/scheduled.yml`, 04:00 UTC, plus
   `workflow_dispatch`), where a regression is found within a day rather than at release.
4. **A run says which tiers it verified.** `tiers verified: required + heavy`, and when a
   project declares a scheduled set that this run did not cover, the verdict says so in
   words. This is ADR-0081's rule — a partial run must never read as a complete one —
   applied to tiers instead of lanes.

## Alternatives considered

- **Leave it and accept 25-minute rounds.** The status quo, and the reason a fifteen-PR
  day costs six hours of waiting. The cost is real and recurring; the benefit per round
  is a score that has not moved in two months.
- **Delete the mutation lane.** Rejected. Its fail-closed guard against a vacuous `1.0`
  is a genuine protection (ADR-0022), and mutation score is the only thing here that
  measures whether the tests *assert* anything. Running it less often is not the same as
  not running it.
- **Skip it with an environment variable in the CI workflow** (`BORROMEANRINGS_SKIP=…`).
  Cheapest to build and the worst to live with: a general "turn a check off" knob is a
  fail-open mechanism looking for a caller, and it would sit in the one place nobody
  reads — a workflow file.
- **Keep it in `[checks].heavy` and let the workflow run a narrower command.** Same
  problem in a different spelling: the config would say the check gates every PR while
  CI quietly did something else, which is exactly the run-dir-and-verdict disagreement
  #229 was about.
- **Run mutation only on the release branch.** Considered. A day is a better feedback
  interval than a release, and `workflow_dispatch` covers the "before I tag" case.

## Consequences

- (+) A pull-request round drops from ~25 minutes to ~11. Serial merges mean that saving
  multiplies by every PR in a queue.
- (+) The tier is a place for the next expensive check (a DAST lane, a real-Hypothesis
  run — #220) that would otherwise be argued about one PR at a time.
- (−) A mutation regression is now found within a day instead of within a PR. That is the
  trade this ADR is: the check that catches it has caught nothing in two months, and the
  work that would introduce one is still gated by everything else.
- (−) A green PR no longer means "mutation passed". The verdict says so on every run that
  did not include the tier, which is the only way that trade stays honest.
- (−) One more tier to explain, and one more workflow file. Both are named in
  `docs/CHECKS.md` beside the lanes they extend.
