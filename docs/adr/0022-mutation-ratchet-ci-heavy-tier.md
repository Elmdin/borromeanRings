# ADR-0022 — Mutation-score ratchet on a CI-tier "heavy" check lane

**Status:** Accepted

## Context
The gate's test check (`40_test`) enforces *coverage* non-regression. Coverage measures
*execution*, not *detection*: a deliberately broken function with a vacuous 100%-coverage
test (`assert result is not None`) passes lint, typecheck, security, and the test gate
cleanly (verified by an adversarial probe). That is the coverage-Goodhart trap CS130 warns
about ("coverage has only low-moderate correlation with effectiveness; mutation > coverage").
`DELAYED-DECISIONS.md` DD-1 deferred mutation testing pending Maintainer confirmation, while
prior feedback established the project wants meaningful signals (mutation, ratchets) over
arbitrary % targets. See `docs/ENFORCEMENT-COVERAGE.md` (T1 tier).

Mutation testing is **heavy**: it runs the whole suite once per mutant (borromeanRings's own
package generates ~950 mutants). Running it on the fast inner Stop gate — which fires on
every agent Stop — is untenable as any project grows.

## Decision
Add **mutation-score as a non-regression ratchet**, run on a dedicated **CI-tier "heavy"
lane**, not the inner gate.

- **Heavy lane.** A new `checks/ci/` directory that `verify.sh` scans **only** under
  `--heavy` (or `BORROMEANRINGS_HEAVY=1`). The policy spine gains `[checks].heavy`; those
  checks are required-to-pass only in heavy mode. CI runs `verify.sh --heavy`; the inner
  Stop gate is unchanged and stays fast. This lane generalizes to future heavy checks
  (fuzzing, DAST, perf budgets).
- **The check** (`checks/ci/60_mutation.sh`) runs `mutmut`, parses its result counts, computes
  a score, and ratchets it against `.borromeanrings-mutation-baseline` via the shared T1
  primitive `meta_harness.ratchet.decide_ratchet` (no arbitrary target — non-regression only).
- **Score** = caught / evaluated, where caught = killed + timeout, evaluated = caught +
  survived + suspicious (skipped / no-tests excluded). Parsing + math live in tested Python
  (`meta_harness.mutation`); the shell only orchestrates (the tool is a module secret).
- **Fail closed on zero evaluated.** If mutmut evaluates 0 mutants (a setup/clean-test
  failure), the check FAILS rather than trusting the vacuous 1.0 score — the enforcement
  must not have the same silent hole it exists to remove.
- **Scope.** mutmut mutates `src/meta_harness/` and runs only the pure-logic tests; the three
  shell-integration tests are ignored (they drive bash via repo-relative paths absent from
  mutmut's copied `mutants/` dir, and cover shell, not Python). `hook_dedupe.py` is excluded
  (its only test is shell-based). First recorded baseline: **0.80** (measured 0.8122;
  seeded conservatively against timeout noise — tighten as it proves stable).

This **resolves DD-1**: mutation testing is adopted as a CI-tier ratchet, not an absolute %.

## Alternatives considered
- **Inner-gate mutation** — strongest immediacy, but intolerable runtime as projects grow.
- **Config flag `[checks].heavy` with self-skipping checks in the normal dirs** — one
  mechanism, but more `verify.sh` surface and every heavy check must implement its own skip.
- **Incremental (diff-only) mutation** — mutate only changed files so it fits the inner gate.
  Best long-term; deferred (needs diff-scoping + a "no changes" path). The heavy lane is the
  first, reversible step; incremental can later feed the same ratchet.

## Consequences
- (+) Closes the coverage-Goodhart hole with a meaningful, non-gameable signal; inner gate
  stays fast; a reusable heavy lane + reusable ratchet primitive now exist.
- (−) A second `verify.sh` mode and a heavier CI run; mutmut config is tied to the current
  test layout (documented in `setup.cfg`); the baseline needs occasional review.
- (+) The evaluated-mutant count is surfaced on the gate's verdict row via the receipt's
  `summary` field (`PASS (evaluated N, score S)` / `FAIL (evaluated 0)`), and the fail-closed
  rule is pinned by `tests/integration/test_mutation_guard.py` (issue #187).
