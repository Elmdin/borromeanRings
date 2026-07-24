# ADR-0023 — T2 external rubric critic as a substrate-agnostic, injected-judge seam

**Status:** Accepted

## Context
borromeanRings's gate is entirely **mechanical** — build, format, lint, typecheck, test, security,
layout, collaboration. All check *form*; none check *intent* (does the change do the right thing? is
it well-named/designed? does it match its requirements?). The enforcement coverage map
(`docs/ENFORCEMENT-COVERAGE.md`) calls this the **T2** tier and shows it empty — the "quality
ceiling" that mechanical gates structurally cannot reach. An adversarial probe already showed
deliberately-wrong code passing every mechanical check.

Adding semantic judgment raises a tension with two founding constraints: borromeanRings is
**model-agnostic** (ADR-0002 frontier API, ADR-0003 no local model on WSL2) and must **enforce
outcomes, never dictate the agent's decisions** (VISION §6). A critic hard-wired to a specific model,
or one that fails open on an unclear answer, would violate both the portability and the trust root.

## Decision
Build the T2 critic as a **seam**, not a specific integration — the reusable mechanism
`meta_harness.critic`, shaped exactly like the deep-research verifier:

- **Injected judge.** `CriticJudge = (question, artifact) -> (passed, rationale)` is injected. The
  volatile decision — *which model, how many, prompt wording* — is a module secret behind that type.
  borromeanRings owns the rubric and the aggregation; the model performs the judgment.
- **Fail-closed, deterministic aggregation.** `evaluate_rubric` passes iff **every required**
  criterion passes; advisory criteria are reported only. A judge that returns unsure/non-affirmative
  **or raises** yields a *failed* criterion — never a silent pass. This policy is pure, tested code;
  only the per-criterion judgment is probabilistic.
- **Rubric = data.** Criteria are declared values, so intent / naming / requirements-traceability /
  doc-drift are different rubrics over one mechanism (Single Choice), not new code.
- **Not on the deterministic gate yet.** The seam is not wired as a required check. A model-backed
  rubric check lands later and **advisory-first** (recorded, non-blocking, because it is
  non-deterministic), promoted to a blocking heavy-lane check (ADR-0022 lane) only once it earns
  trust. borromeanRings's own gate stays deterministic and reproducible.

## Alternatives considered
- **Hard-wire a specific model + blocking check now.** Fastest to "intent enforcement", but breaks
  model-agnosticism, puts a non-deterministic call on the fail-closed gate, and makes the mechanism
  untestable offline. Rejected.
- **A rules/heuristics "critic" (no model).** Deterministic, but cannot judge intent — it would just
  be another mechanical check wearing a T2 label. Rejected (doesn't fill the tier).
- **Adversarial panel from day one.** Stronger (independent, diverse judges), but more surface than a
  seam needs. Deferred to a follow-up (`evaluate_rubric_adversarial`), mirroring
  `deep_research.verify_claim_adversarial`.

## Consequences
- (+) The "verifier external to the generator" principle now extends to semantic judgment; the
  mechanism is fully unit-tested with stub judges (no network); intent/naming/traceability/doc-drift
  become rubrics, not bespoke code; model-agnosticism and the red line are preserved.
- (−) No intent is *enforced* until a model-backed rubric check is wired (a later, opt-in PR); the
  seam's real-world value depends on judge quality, which must be earned into a blocking role, not
  assumed.
