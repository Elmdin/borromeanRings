# ADR-0025 — Adversarial self-test: a known-bad corpus the gate must reject

**Status:** Accepted

## Context
borromeanRings asserts that a green gate means the work is sound. Yet until now
every test proved a *check module* in isolation; nothing exercised the assembled
`verify.sh` against deliberately bad code. An empirical probe (wrong discount +
off-by-one + vacuous 100%-coverage tests) once passed the gate — proof that
"green" did not yet entail "known-bad is caught". This is matrix row **K**: *is
the enforcement itself real?* An enforcement mechanism that is never adversarially
tested is a promise, not a guarantee — and this project's whole thesis is the
difference between the two.

## Decision
Add a permanent **adversarial corpus** (`tests/test_gate_adversarial.py`,
SPEC-adversarial-selftest.md) that runs the real gate against minimal fixture
projects and asserts the end-to-end verdict: planted defects in a *required*
dimension are **rejected** (and caught by the owning check), and a clean control
project is **accepted**.

Realized as a `pytest` corpus enforced by the already-required `40_test` gate —
**not** as a new check that runs `verify.sh` recursively on every gate run.

Fixtures are **generated in tmp, never committed** (a committed lint/security
defect would poison this repo's own `ruff`/`bandit`), and each declares exactly
one `required` check so the verdict is attributable to the planted defect.

Increment 1 covers `20_lint`, `50_security`, `05_hygiene`, `07_layout`, plus the
known-good control. The table is append-only; further dimensions land as their
tooling does.

## Alternatives considered
- **A new gate check that re-runs `verify.sh` on known-bad fixtures every run** —
  rejected: per-run cost on every gate, and a real infinite-recursion hazard if a
  fixture ever pointed at the repo root. The test lane gives the same T0
  guarantee without either downside.
- **Commit the known-bad fixtures as files under `tests/corpus/`** — rejected: a
  committed unused import / `shell=True` would fail this repo's own `20_lint` /
  `50_security`, so the corpus would break the gate it is meant to validate.
  Generating in tmp keeps the repo clean and the corpus hermetic.
- **Assert only on the exit code** — rejected: an exit-code-only check can't tell
  "the right check caught it" from "something unrelated failed". Asserting on the
  required check's receipt makes each case attributable; the known-good control
  rules out a gate that trivially rejects everything.
- **Leave it to manual probing** — rejected: a one-off probe rots; a permanent,
  gate-enforced corpus turns "we checked once" into "regressions are caught".

## Consequences
- (+) The claim "the gate catches known-bad" is now continuously verified; a
  regression that weakens any covered dimension fails CI.
- (+) The corpus is the executable, extensible home for "does enforcement work?"
  — new dimensions (mutation strength, dead-code, CVEs, secrets) plug into the
  same table as their tooling arrives.
- (+) Doubles as living documentation: each fixture is a worked example of what a
  given check rejects.
- (−) Each fixture spawns a full `verify.sh` subprocess (~2–5s); the corpus is
  kept tight and dimensions requiring heavy tooling are deferred to the CI lane.
- (−) Subprocess-executed gate runs don't add to this repo's coverage number
  (execution happens in a child), so the corpus's value is regression safety,
  not a coverage bump — an accepted, understood trade.
