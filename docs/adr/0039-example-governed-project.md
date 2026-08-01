# ADR-0039 — An example governed project (textkit) to prove portability

**Status:** Accepted

## Context
borromeanRings claims to "enforce best practices for **any** project," but it had
only ever been dogfooded on **itself** — a Python meta-harness. Two problems:
(1) the portability claim was unproven; (2) per the Build Brief's "no premature
building" rule, several matrix rows (API breaking-change, flaky-test detection,
perf) can't be *justified* against the meta-harness, because its own need for them
is nil. Without a second, different project there is no real need to point at.

## Decision
Add `examples/textkit` — a small, real **library** (a different archetype) with
its **own** `borromeanrings.toml` declaring a library-appropriate gate, governed
by borromeanRings via `BORROMEANRINGS_PROJECT=examples/textkit bash verify.sh`. A
permanent integration test asserts its gate passes, making portability a
regression check, not a claim.

The example is kept cleanly separate from borromeanRings's own governance:
`examples/` is excluded from the repo's own `ruff`; borromeanRings's `bandit`/`mypy`
already scope to `src/`; its `pytest` `testpaths` is `tests/`. So textkit is
governed *by* borromeanRings, not folded *into* it.

## Alternatives considered
- **A separate repo for the example** — cleaner isolation, but rejected for now:
  an in-repo example is discoverable, version-locked to the governing code, and
  runs in the same CI. A separate repo is the option once there are several
  examples/archetypes.
- **Only fixture projects (like the adversarial corpus)** — rejected as
  insufficient: minimal tmp fixtures prove a *check* fires, not that a *real* multi-
  file project of another archetype passes the whole gate with its own config.
- **A web-API example (Flask/FastAPI)** — deferred: it needs a web framework
  dependency and would justify DAST/load checks. A dependency-free **library** is
  the smallest thing that proves portability *and* justifies the next real need
  (public-API breaking-change detection — a library has an API that matters).

## Consequences
- (+) Portability is proven and regression-tested: a genuinely different archetype
  passes borromeanRings's gate under its own policy spine.
- (+) It creates the **real need** that justifies archetype-specific checks
  (API-diff against textkit's public surface) — turning "premature building" into
  "justified building". Those become the honest next increments.
- (+) It's a worked template for anyone governing their own project with
  borromeanRings.
- (−) One more thing to keep green; kept tiny and separated so its maintenance cost
  is low. A second archetype (web API) is a future example, likely its own repo.
