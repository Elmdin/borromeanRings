# ADR-0024 — Project profiler as an advisory (T3) matrix selector

**Status:** Accepted

## Context
borromeanRings enforces a fixed check set. But enforcing *every* practice on *every* project is wrong
(CS130: right-size to risk) — a throwaway CLI should not carry a fintech API's gate. The enforcement
coverage map (`docs/ENFORCEMENT-COVERAGE.md`) needs a *selector*: something that decides which rows
are active, at which tier, for a given project. That selection depends on the project's **type** and
its **quality-attribute needs** — judgments a fixed config cannot make.

Two constraints bound the design: borromeanRings must **enforce outcomes, never dictate the agent's /
maintainer's decisions** (VISION §6), and it must stay **model-agnostic** (ADR-0002/0003). A
profiler that silently rewrote a project's gate, or hard-wired a model, would break both.

## Decision
Build the profiler as an **advisory (T3) selector** with a deterministic core and an injected
classifier:

- **Proposes, does not decide.** `meta_harness.profiler` maps a project archetype to an
  `EnforcementProfile` (quality priorities, required + heavy checks, stack pathways with trade-offs)
  and **emits a candidate `borromeanrings.toml`**. The maintainer edits and adopts it; borromeanRings
  then enforces the adopted config. The profiler never mutates the live config.
- **Deterministic core, injected judgment.** archetype→profile and profile→config are pure data +
  rendering — model-free and unit-tested. Only description→archetype is probabilistic, behind an
  injected `Classifier` (the same seam pattern as `critic` and `deep_research`). The model is a
  module secret.
- **Runnable, falsifiable output.** The emitted config must **parse via
  `meta_harness.spine.load_config`** (round-trip tested) — the recommendation is a gate-able artifact,
  not prose. This is the discipline that stops an advisory feature from becoming astrology.
- **Fail-safe, never fail-open.** An unknown/garbled archetype falls back to a conservative default
  profile — never an empty or invalid gate. borromeanRings never treats "unsure" as "no enforcement".
- **It selects the matrix; the T1/T2 build deepens it.** The profile is literally "which
  coverage-map rows at which tier", so the profiler and the tier-filling work compose.

## Alternatives considered
- **Auto-apply the recommended config.** Removes a manual step, but crosses from advising into
  deciding for the maintainer (red line) and could silently weaken a gate. Rejected.
- **A general "what should I build" product advisor.** Out of scope and identity-breaking —
  borromeanRings configures *enforcement*, not product strategy. Rejected.
- **Pure-LLM profiler (classification + config generation both by model).** Simple, but
  non-deterministic config generation is untestable and un-auditable. Rejected in favor of a
  deterministic core with only classification injected.

## Consequences
- (+) borromeanRings becomes right-sizable for any project type while preserving maintainer autonomy;
  the core is fully testable offline; the output is immediately gate-runnable; consistent seam
  pattern across critic/deep-research/profiler.
- (−) Real classification quality depends on the (later, opt-in) injected classifier; the seeded
  archetype registry is a starting set that will need extension as new project types appear.
