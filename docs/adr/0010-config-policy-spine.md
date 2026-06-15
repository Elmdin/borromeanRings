# ADR-0010 — Config/policy spine (`borromeo.toml`)

**Status:** Accepted

## Context
borromeo's differentiator is a config-driven **spine** that enforces declared invariants on every
run (Manifesto / VISION). v0 had only `checks/manifest.json` (a hard-coded check list) + receipts.
We need a real declarative source where a repo declares *what must always hold* — the required
checks and the operating context (account, value priorities, requirements) — enforced consistently
rather than restated ad hoc.

## Decision
Introduce **`borromeo.toml`** as the single declarative source of invariants, loaded by a tested
`meta_harness.spine` module. `verify.sh` reads the required-check set from the spine (replacing
`checks/manifest.json` — Single Choice Principle) and enforces **config-compliance**: every declared
check must produce a pass receipt. A `[context]` section declares operating context that the wrapped
agent consumes (e.g. for prompt rewriting, the next build).

Two principles are baked in:
- **Enforce outcomes, preserve agent autonomy.** The spine governs *what must hold* (invariants on
  results), never *how* the wrapped agent plans/decides — many harnesses plan better than borromeo
  would. (New red line in VISION §6.)
- **Fail-closed config.** Empty/absent `[checks].required` raises — "nothing declared" is a
  misconfiguration, never "nothing to enforce, so pass."

## Alternatives considered
- **Keep `manifest.json`** — rejected: JSON can't carry comments/context cleanly, and it was only a
  check list, not a policy spine. TOML (`borromeo.toml`, alongside `pyproject.toml`, stdlib
  `tomllib`) reads well and extends to richer policy.
- **Put config in `pyproject.toml`** — rejected: conflates Python packaging with borromeo policy;
  a dedicated file keeps the spine substrate/stack-neutral.
- **Enforce the agent's planning/process too** — rejected: violates the autonomy principle above.

## Consequences
- (+) One declarative source of invariants; config-compliance is real (not a hard-coded list).
- (+) `[context]` is the fuel for prompt rewriting (next build) — declared once, applied every run.
- (−) First iteration enforces the required-check set only; richer constraints (forbidden patterns,
  identity, per-harness layering) and config-compliance diffing/tamper-evidence are deferred.
