# SPEC — Adversarial self-test (the gate must catch known-bad)

**Status:** Implemented (increment 1 of the enforcement-coverage program)
**Realized by:** `tests/test_gate_adversarial.py` · ADR-0025

## Problem

Every check has unit tests proving *its module* behaves. Nothing proved the
**assembled gate** actually rejects bad code. An empirical probe (a project with
a wrong discount, an off-by-one, and vacuous 100%-coverage tests) once sailed
through lint/type/security/coverage — evidence that "green gate" did not yet
mean "known-bad is caught". Enforcement that is never adversarially tested is a
claim, not a guarantee (matrix row **K — is the enforcement itself real?**).

## Contract

A permanent, gate-enforced corpus asserts the **end-to-end verdict** of the real
`verify.sh`:

1. **Reject known-bad.** For each fixture with a planted defect in a *required*
   dimension, the gate exits non-zero (`RESULT: FAIL`) **and** the required
   check's receipt is `fail`/`error` — i.e. the defect is caught by the check
   that owns that dimension, not incidentally.
2. **Accept known-good.** A clean fixture exits zero (`RESULT: PASS`). This is
   the negative control: without it, a gate that failed *everything* would pass
   the corpus for the wrong reason.

### Dimensions covered (increment 1)

| Fixture | Planted defect | Required check that must catch it |
|---|---|---|
| `lint-violation` | unused import (ruff F401) | `20_lint` |
| `security-finding` | `subprocess(…, shell=True)` (bandit B602) | `50_security` |
| `missing-hygiene-artifact` | declared `[hygiene].requires` path absent | `05_hygiene` |
| `disallowed-root-doc` | root `.md` outside the allowlist | `07_layout` |
| `known-good` (control) | none | gate must PASS |

## Design constraints

- **Hermetic.** Fixtures are generated in a tmp dir at test time and **never
  committed** — a committed file with a deliberate lint/security defect would
  poison this repo's own `ruff check .` / `bandit`. Each fixture is a minimal
  governed project; the gate runs against it via `BORROMEANRINGS_PROJECT`.
- **No environment mutation.** `00_build` uses `compileall` + import (never
  `pip install`), so running the full gate against fixtures is side-effect-free.
- **No recursion.** Fixtures are separate minimal projects, so the corpus (run
  under this repo's `40_test`) never re-gates this repo.
- **Attributable.** Each known-bad fixture declares exactly one `required`
  check, so the verdict hinges on the planted defect alone.

## Realization choice (T0 via the test lane)

Implemented as a `pytest` corpus enforced by the already-required `40_test`
gate, **not** as a new gate check that recursively runs `verify.sh` on every
run. This delivers the T0 guarantee ("known-bad is caught, permanently") without
per-run recursion cost or infinite-recursion risk. See ADR-0025.

## Extensibility

New dimensions are added by appending a `(files, required_check)` fixture to the
`KNOWN_BAD` table. Dimensions needing an external tool or the CI heavy-lane
(mutation, dead-code, CVE, secrets) are added when that infrastructure lands.
