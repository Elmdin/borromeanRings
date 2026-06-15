# SPEC — Deep Research tool

> **Scope note:** this is a **borromeo harness feature** — borromeo *enhances the deep-research
> capability the wrapped agent already has* (it does not build a research product from scratch). The
> features below are the enhancements borromeo adds. See [`MANIFESTO.md`](MANIFESTO.md).
>
> Status: spec, derived from [`research/deep-research-landscape.md`](research/deep-research-landscape.md).
> Awaiting sign-off before implementation. The first tool borromeo builds *through* the harness and
> then **adopts** (self-extension). The "best way to find & synthesize information."
> CS130-structured: requirements → architecture → patterns → phased build.

## 1. Thesis
Existing deep-research is non-deterministic, opaque, citation-unreliable (~40% of references
erroneous/fabricated), and **low-recall (best agent ~21% — misses ~80% of relevant sources)**.
borromeo's version wins on **trust + coverage**: it **augments the wrapped agent's own research
tool**, searches **comprehensively** across many engines, **shows the user everything live**, and
**gates the output** so every surviving claim is fact-checked against its real source — and it
actively works to **not miss anything**.

## 2. Requirements (CS130 Part 1)

### User stories
- **US-D1 (augment, don't replace):** As a user, I want borromeo to *enhance* whatever deep-research
  my agent/harness already has, so I keep its strengths and gain borromeo's coverage + verification.
- **US-D2 (comprehensive coverage):** As a user, I want it to search across multiple engines and read
  *all* relevant sites, so the answer isn't limited to one engine's top results.
- **US-D3 (don't miss anything):** As a user, I want it to tell me when I searched the wrong place,
  used a weak query, or barely missed a crucial detail — and to keep going until coverage is saturated.
- **US-D4 (watch it work):** As a user, I want to *see everything live* — which sites are chosen and
  when, what's being read, and how it ingests and synthesizes — so I can trust it looked everywhere.
- **US-D5 (trustworthy output):** As a user, I want the synthesized result fact-checked and gated, so
  no unverified or fabricated claim survives.

### Quality Attribute Scenarios (meaningful signals, not arbitrary numbers — per project policy)
| QAS | Stimulus | Response measure |
|---|---|---|
| DR-1 Recall/coverage | a query with a known answer set | completeness critic finds **no new relevant sources for K consecutive rounds** (saturation), and recall vs. the known set is *reported* and **ratcheted** (may not regress) — no absolute % target |
| DR-2 Citation integrity | a synthesized claim | claim is dropped/flagged unless its **fetched source text** supports it (adversarial verify) |
| DR-3 Observability | any run | every query, engine, chosen site, read passage, extraction, and verdict is emitted as a **receipt**, streamed live |
| DR-4 Determinism | re-run of the same query | same plan/queries/sources reproduce from the log (reproducible-to-inspect, not bit-identical) |
| DR-5 Safety | a malicious/ad-heavy source | filtered out; fetch sandboxed |
| DR-6 Substrate-agnostic | swap engine or LLM | works with any engine, any agent, or a bare LLM (Adapter) |

## 3. Architecture (CS130 Parts 2 & 4)

### Style — an inspectable pipeline wrapped in a completeness loop
Pipes-&-filters pipeline (each stage independent, emits receipts) inside a **loop-until-dry**
coverage loop (borrowed from borromeo's own multi-agent patterns):

```
        ┌────────────────────────── completeness loop (until K dry rounds) ──────────────────────────┐
plan → mutate/expand queries → federated multi-engine search → site selection → fetch(sandboxed) →
       read/extract claims+passages → VERIFY claims vs source → [completeness critic: gaps? wrong
       query/place? missed detail?] ──(gaps found → new queries/areas)──┘
                                                                         └─(dry) → synthesize → GATE → cited report
every stage streams a receipt (query · engine · chosen site · read passage · extraction · verdict)  ← US-D4 visibility
```

### Stage responsibilities
- **plan** — decompose into sub-questions (visible, editable).
- **mutate/expand** — *Diverse Multi-Query Rewriting* + pseudo-answer (Query2doc) to widen recall;
  mutations are **diversified and verified** (LLM expansion degrades on ambiguous queries → never
  blindly trusted).
- **federated search** — distribute each query to **multiple engines**; aggregate → **dedup + result
  fusion** (no single engine authoritative).
- **site selection** — rank/choose sources; **show which and why** (US-D4).
- **fetch (sandboxed)** — safe retrieval; filter ads/SEO-spam/low-quality/unsafe (DR-5).
- **read/extract** — pull candidate claims **with the exact supporting passage**; show what's read.
- **verify** — for each claim, confirm the *fetched passage* supports it; adversarial majority-vote
  skeptics. Unsupported ⇒ dropped/flagged. (This is borromeo's "verify claims" critic.)
- **completeness critic ("don't miss anything")** — gap detection: are there unexplored angles,
  better queries, or areas the user/agent should have searched? Diagnose wrong-query/wrong-place and
  propose new queries/sources. Loop until **K consecutive dry rounds** (no new relevant material).
- **synthesize** — outline-first cited report from **verified claims only**.
- **GATE** — a deterministic gate on the output (like `verify.sh` for code): fail-closed if any
  surviving claim is unverified, or coverage didn't saturate. No pass-on-trust.

### Patterns (CS130 Part 2)
- **Adapter** — each search engine, the fetcher, the LLM, *and the wrapped agent's existing research
  tool* sit behind adapters → augment-not-replace (US-D1) + substrate-agnostic (DR-6).
- **Strategy** — query-mutation strategies are interchangeable (DMQR's four + pseudo-answer).
- **Façade** — one `deep_research(query)` entry over the whole pipeline.
- **Information hiding / receipts** — reuse borromeo's receipt plumbing as the observability + audit
  layer (DR-3) and the determinism log (DR-4).

## 4. Built through borromeo, then adopted
Spec'd → built on a branch → passes borromeo's own gate → human-approved merge. It is a **trust-root
capability**, so it faces the **same-or-stricter** gate (full checks + the verification critic). Once
merged, it registers as a capability borromeo can use, and it **augments** the agent's own research.

## 5. Phased build (each phase a gated PR; build only what's directed)
1. **Skeleton + contracts** — typed/tested pipeline stages + per-stage receipts; one search adapter +
   one fetch adapter; Façade entry. (No completeness loop or synthesis yet.)
2. **Federated multi-engine search** — multiple engine adapters + dedup/result fusion.
3. **Query mutation** — diverse multi-query + pseudo-answer (Strategy), verified/diversified.
4. **Citation verification** — claim→source verifier (the killer feature), adversarial.
5. **Completeness critic** — gap detection + wrong-query/place diagnosis + loop-until-dry.
6. **Synthesis + output GATE** — outline-first cited report from verified claims; deterministic gate.
7. **Live visibility** — stream receipts as events; render site-selection/reading/synthesis in real time.
8. **Augment + substrate polish** — wrap the agent's existing research tool; swappable engine/LLM.

## 6. Open design decisions (for sign-off)
1. **Repo placement** — build in-repo as a `meta_harness` capability/plugin *(recommended — reuses the
   registry + receipt patterns; it's meant to be adopted)* vs. a separate package.
2. **Phase-1 search adapter** — start with the web tools available here (WebSearch/WebFetch) behind a
   swappable adapter *(recommended)*, adding more engines in Phase 2.
3. **"Deterministic" interpretation** — *reproducible-to-inspect + verified* (plan/queries/sources
   logged; claims verified), **not** bit-identical (LLM steps are nondeterministic). *(recommended)*
4. **Live visibility surface** — for now, stream structured receipt events (a CLI/log view); a rich
   UI is later. Confirm that's an acceptable v1 of "watch it work."
