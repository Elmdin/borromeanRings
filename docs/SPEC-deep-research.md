# SPEC — Deep Research tool (Layer 2)

> Status: spec, derived from [`research/deep-research-landscape.md`](research/deep-research-landscape.md).
> Awaiting sign-off before implementation. This is the first tool borromeo builds *through* the
> harness and then **adopts** (self-extension). It is the "best way to find & synthesize information."

## 1. Thesis
Existing deep-research is non-deterministic, opaque, and citation-unreliable (~40% of references
erroneous/fabricated). borromeo's version wins on **trust**: a **deterministic, fully-visible,
citation-verified** pipeline. You can see every step and *know* it looked everywhere and that every
claim is backed by its real source.

## 2. Differentiators (each answers a measured gap — see the landscape doc)
| Property | How borromeo delivers it |
|---|---|
| **Deterministic** | Orchestrated, inspectable **pipeline** (not an end-to-end black box); the plan, queries, and sources are logged so the same query reproduces the same path |
| **Visualized step-by-step** | Every query, every source found, what was fetched and extracted → emitted as **receipts** (reuse borromeo's audit plumbing); rendered so the user can confirm coverage |
| **Citation-verified** | Every claim in the report is checked against the **actually-fetched source text**, not model memory — kills statement- and citation-hallucination (borromeo's "verify claims" + adversarial verification) |
| **Synthesizing** | Explicit synthesis stage over verified snippets; outline-first (STORM-style) |
| **Clean & safe** | Source-quality filter (ads/SEO-spam/low-quality) + sandboxed fetches (virus-safe) + prefer primary sources |
| **Substrate-agnostic** | Search/fetch are tools; the LLM is swappable (Adapter seam) — any agent or bare LLM, any browser/engine |

## 3. Pipeline (the inspectable stages)
```
plan → search → fetch(sandboxed) → read/extract → VERIFY-claims → synthesize → cited report
        └────────── every stage emits a receipt (query, source, extract, verdict) ──────────┘
```
- **plan**: decompose into sub-questions + queries (visible, editable — Gemini's one good idea).
- **search**: run queries on a pluggable engine; record results.
- **fetch**: sandboxed retrieval; filter ads/spam/unsafe.
- **read/extract**: pull candidate claims + the exact supporting passage.
- **verify**: for each claim, confirm the fetched source text actually supports it (adversarial; majority-vote skeptics). Unverifiable claim ⇒ dropped or flagged. **Fail-closed: no verified source ⇒ claim does not appear.**
- **synthesize**: outline → cited report from verified claims only.

## 4. Built through borromeo, then adopted
- Spec'd here → built on a branch → passes borromeo's own gate → human-approved merge.
- It is a **trust-root capability** (borromeo will rely on it), so it faces the **same-or-stricter**
  gate (full checks + the verification critic) — per ADR/self-extension principle.
- Once merged, it registers as a capability borromeo itself can use (the registry pattern v0 kept clean).

## 5. Phased build (each phase a gated PR; don't build past what's directed)
1. **Skeleton + contracts**: the pipeline stages as typed, tested interfaces; receipts per stage; one pluggable search backend and one fetcher behind adapters. No fancy synthesis yet.
2. **Citation verification**: the claim→source verifier (the differentiator) with adversarial checks.
3. **Synthesis**: outline-first cited report from verified claims.
4. **Clean & safe sourcing**: ad/spam/quality filter + sandboxed fetch.
5. **Visualization**: render the step-by-step trail from receipts.
6. **Substrate-agnostic polish**: swappable LLM + engine; runnable with a bare LLM.

## 6. Open design decisions (for sign-off)
- **Repo placement**: build in-repo first as a `meta_harness` capability/plugin (recommended — uses the existing registry/receipt patterns), or a separate package? 
- **Search backend for phase 1**: which engine/API (e.g., a pluggable adapter starting with one provider)? Must stay swappable.
- **Determinism boundary**: the *pipeline* is deterministic/inspectable; the LLM steps (plan/extract/synthesize) are inherently non-deterministic — we make them *reproducible-by-logging* and *verifiable*, not bit-identical. Confirm that's the right interpretation of "deterministic."
