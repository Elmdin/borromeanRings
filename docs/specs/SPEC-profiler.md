# SPEC — Project profiler (matrix selector)

> Status: spec for the T3 advisory profiler. It **selects** which enforcement-coverage-map rows
> are active for a project and emits a runnable `borromeanrings.toml`; it decides nothing. Plan →
> approve → implement; delivered via PR. ADR-0024. See `docs/ENFORCEMENT-COVERAGE.md`.

## 1. Purpose
borromeanRings enforces a fixed check set today. But "any and all best practices" is not "every
practice on every project" — a throwaway CLI must not carry a fintech API's gate (CS130: right-size
to risk). The **profiler** classifies a project's **type**, derives its **quality-attribute needs**,
proposes **stack pathways with trade-offs**, and emits a **candidate `borromeanrings.toml`** that
turns the right coverage-map rows on at the right tier.

Crucially it is **advisory (T3)**: it *proposes* config, the human *chooses*, then borromeanRings
*enforces* the choice. It configures **enforcement**; it does not do product strategy or decide what
to build (VISION §6 red line). The discipline that keeps it honest: its output is a **concrete,
gate-able artifact** (a config the spine can load and the gate can run), not a vibes document.

## 2. Requirements

### User stories
- **US-P1 (right-sized):** As a maintainer starting a project, I want borromeanRings to recommend a
  check set matched to the project *type*, so enforcement fits the risk.
- **US-P2 (needs, then stacks):** I want the project's quality-attribute priorities named, and 2–3
  stack pathways with trade-offs, so I choose rationally (generate alternatives, then decide).
- **US-P3 (runnable output):** I want a `borromeanrings.toml` I can drop in and run the gate against —
  the recommendation must be falsifiable, not prose.
- **US-P4 (advisory, substrate-agnostic):** I want classification to work with any model (or a
  keyword heuristic, or none in tests), and I retain the decision.

### Quality-attribute scenarios
| QAS | Stimulus | Response measure |
|---|---|---|
| P-1 Right-sized | classify a project | returns an `EnforcementProfile` whose active checks/tiers match the archetype (e.g. a library ratchets mutation; a throwaway CLI does not) |
| P-2 Runnable | emit config for a profile | the output **parses via `meta_harness.spine.load_config`** and yields the intended required/heavy set (round-trip) |
| P-3 Fail-safe | an unknown/garbled classification | falls back to a conservative default archetype — never an empty or invalid gate |
| P-4 Substrate-agnostic | classification | performed by an **injected** classifier; deterministic mapping + rendering are model-free and unit-tested |

## 3. Contract (`meta_harness.profiler`)
- `StackOption(name, tradeoffs)` — one candidate stack + its one-line trade-off.
- `EnforcementProfile(archetype, quality_priorities, required_checks, heavy_checks, stack_options,
  notes)` — the recommendation for an archetype.
- `PROFILES: dict[str, EnforcementProfile]` — the seeded registry (data): `library` (default),
  `cli`, `web_api`, `data_pipeline`, `ml_service`.
- `known_archetypes() -> tuple[str, ...]`.
- `profile_for(archetype) -> EnforcementProfile` — lookup; **fails safe** to the default archetype
  for anything unknown.
- `Classifier = Callable[[str], str]` — injected: free-text description → archetype key.
- `classify(description, classifier) -> str` — runs the classifier and validates the result against
  `known_archetypes()`, falling back to the default (fail-safe).
- `recommend(description, classifier) -> EnforcementProfile` — classify, then `profile_for`.
- `render_config(profile, *, language, package, src_dir, tests_dir) -> str` — emit a
  `borromeanrings.toml` with `[project]`, `[context].value_priorities`, `[checks].required` and
  `[checks].heavy`. The **maintainer edits and adopts it**; borromeanRings then enforces it.
- `render_recommendation(profile) -> str` — human-readable: archetype, priorities, stack pathways
  with trade-offs, and the active checks.

## 4. Design rationale
- **Deterministic core, injected judgment.** archetype→profile and profile→config are pure data +
  rendering (testable, model-free); only description→archetype is probabilistic, behind `Classifier`
  (same seam pattern as `critic`/`deep_research`). Information hiding: the model is a secret.
- **Selects the matrix.** The profile is exactly "which coverage-map rows, at which tier" — the
  profiler is the map's *selector*; the T1/T2 build *deepens* the map. The two compose.
- **Fail-safe, never fail-open.** An unknown archetype yields a conservative gate, never none —
  borromeanRings never treats "unsure" as "no enforcement".

## 5. Non-goals
- No model integration here (injected classifier; a keyword/LLM classifier is a later, opt-in wiring).
- Does not mutate the project's `borromeanrings.toml` — it **emits** a candidate for human adoption.
- Not a product-strategy or "what to build" tool — it configures enforcement only.

## 6. Verification
Verified by `tests/unit/test_profiler.py`. Unit tests (no network): profile lookup + fail-safe default; classify valid + invalid→default;
`render_config` **round-trips through `load_config`** (P-2); rendering includes stacks + priorities.
100% coverage of `profiler.py`.
