# ADR-0041 — Adoption helper for existing governed projects

**Status:** Accepted

## Context
The enforcement-coverage program (ADR-0022…0040) added many new checks, but a
project only *runs* the checks its own `borromeanrings.toml` lists. Every
existing governed project was bootstrapped by `init.sh` before those checks
existed, so they sit at the founding 7-check baseline and silently miss the new
quality/security gates — even though the check *code* is already on disk (the
reference model, ADR-0013). `init.sh` bootstraps a **new** project; there was no
supported path to migrate an **existing** one.

The migration is not a flat "require everything": several new checks are
*ratchets* (docstring / complexity / coupling) that are vacuous without a
baseline and would need one seeded from current state, `11_changelog` needs a
`CHANGELOG.md`, and bulk-adding all 19 would turn a healthy project red on first
run.

## Decision
Add `adopt.sh` + `meta_harness.adopt`: plan which of a curated **recommended
set** an existing project is missing, seed each newly-added ratchet's baseline
from the project's *current* value, create a `CHANGELOG.md` if needed, and
rewrite `[checks].required` in place (preserving comments). Idempotent, native,
no installs. The recommended set is the safe-after-seeding quality/security core
(`12_secrets`, `11_changelog`, `32_complexity`, `33_coupling`, `45_docstrings`).

## Alternatives considered
- **Require the full 19-check set** — rejected: `34_api_diff` is library-only,
  `35_architecture` is a no-op until contracts are declared, the heavy CI lane is
  expensive, and the collaboration gates are riskier on an existing history.
  Adoption should be safe-by-default, then opt into more.
- **A fixed absolute baseline (e.g. docstrings ≥ 0.8)** — rejected per the
  no-absolute-target principle: seed from the project's current value so the
  ratchet holds the line and can only improve, never imposing an arbitrary number.
- **Style-preserving TOML writer (`tomlkit`)** — rejected: adds a dependency for
  a one-array rewrite. A scoped, unit-tested text transform keeps it stdlib-only.
- **Auto-run the gate + auto-commit the migration** — rejected: the migration is
  left for a human to review (and may surface a *real* secret finding), and each
  project owns its own commit/branch policy.

## Consequences
- (+) One command migrates a project onto the new gates with a green first run;
  the pilot (reliefq) went 7 → 12 checks, all passing.
- (+) Ratchet baselines are honest — seeded from what the project actually is.
- (+) A genuine `12_secrets` finding during adoption surfaces as a real (good)
  failure rather than being masked.
- (−) The recommended set is deliberately conservative; collaboration gates and
  the heavy CI lane remain a follow-up wave, adopted per project when wanted.
