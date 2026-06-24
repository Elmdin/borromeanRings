# Research — How existing deep-research systems work (and where they fall short)

> **Scope note:** research informing borromeo's **deep-research enhancement** (a harness feature) —
> how to improve the deep research the wrapped agent already has. Not a separate product.

> Layer 2, step 1 (per the Manifesto): study existing deep-research before building ours. This is
> the input to [`../specs/SPEC-deep-research.md`](../specs/SPEC-deep-research.md). Researched June 2026.

## The common architecture (all systems share a 3-phase loop)
1. **Plan** — decompose the query into sub-questions / objectives + a research plan.
2. **Search & read** — iteratively search, fetch, read sources, decide the next step, backtrack.
3. **Synthesize** — aggregate vetted snippets into a structured, cited report.

Two families differ in *how* they implement this:

| System | Approach | Notable |
|---|---|---|
| **OpenAI Deep Research** | **End-to-end RL-trained agent** (o3) — learns to plan/search/backtrack; clarifies intent first | Flexible, but an opaque black box; non-deterministic |
| **Perplexity Deep Research** | Orchestrated CoT + tool-use: generates objectives + a dozen+ queries, reads hundreds of sources, ~2–4 min | Evaluates source quality; retries on paywall/irrelevant |
| **Gemini Deep Research** | Multi-step plan + search; **shows an editable plan**; browses 100+ pages | Best transparency of the commercial set (plan is visible/editable) |
| **GPT Researcher** (OSS, ~26k★) | **planner → concurrent executors → publisher** pipeline; source-tracking; MCP/retriever-extensible | Inspectable pipeline; ~92% citation accuracy claimed; the closest open prior art |
| **Stanford STORM** (OSS) | **Two-stage**: perspective-guided question-asking → outline → grounded write-up with citations | Strong at outline/synthesis; multi-perspective question generation |

## Where they fall short — and these are borromeo's differentiators
Each gap maps directly to a property the Manifesto demands:

| Manifesto property | Gap in existing systems (evidence) |
|---|---|
| **Deterministic** | LLM-driven planning is non-deterministic; end-to-end agents (OpenAI) are black boxes — same query, different path, no reproducibility. |
| **Visualized step-by-step** | Varies wildly: Gemini shows/edits the plan; OpenAI/Perplexity mostly don't expose the full search trail, so you can't *verify it looked everywhere*. |
| **Referenced (real citations)** | **The big one.** Studies: only **~26.5%** of generated references entirely correct; **~40%** erroneous/fabricated; of fabricated refs with DOIs, **64%** point to real-but-*unrelated* papers. Two failure modes: **statement hallucination** (claim deviates from the cited source) and **citation hallucination** (the reference itself is fabricated). |
| **Synthesizing** | A measured "synthesis gap": agents retrieve well but organize/synthesize imperfectly. |
| **Clean & safe** | No explicit ad / SEO-spam / low-quality / virus filtering; source-quality judgment is ad hoc. |
| **Substrate-agnostic** | Each is locked to its own model/platform; not "any browser/engine, any agent or bare LLM." |

## Additional research — coverage, query mutation, multi-engine (the features we're adding)
- **Recall is the unsolved problem.** The best deep-research agent achieves only **~20.92% recall**
  — it misses ~80% of expert-cited sources. "RAG cannot retrieve what isn't there." This is the
  measured justification for a **completeness critic** ("don't miss anything").
- **Query mutation works (with care).** *Diverse Multi-Query Rewriting* (DMQR-RAG, 4 strategies at
  different granularities) and **pseudo-answer / Query2doc** (generate a hypothetical answer, search
  with it) materially improve recall. *But* LLM query expansion **degrades** on unfamiliar/ambiguous
  queries → mutations must be **verified, diversified, and reversible**, never blindly trusted.
- **Federated / metasearch** is a solved pattern: distribute one query to many engines → aggregate →
  **dedup + result fusion (merge/normalize/rank)**. No single engine is authoritative.

## Implications for borromeo's design
- **Favor an orchestrated, inspectable pipeline** (like GPT Researcher / STORM), **not** an opaque end-to-end agent — determinism and visibility require seams you can observe.
- **Citation verification is the killer feature.** Every claim must be checked against the *actually fetched source text*, not the model's memory. This is exactly borromeo's **"mathematical verification of claims"** (Layer 1 critic) applied to research — and adversarial verification is borromeo's strength.
- **Reuse borromeo's receipt/audit plumbing** to record every query, source, and extraction → that *is* the step-by-step visualization + reproducibility.
- **Keep the LLM swappable** (Adapter seam) so it runs with any agent or a bare LLM.

## Sources
- [How OpenAI's Deep Research Works (PromptLayer)](https://blog.promptlayer.com/how-deep-research-works/) · [Introducing deep research (OpenAI)](https://openai.com/index/introducing-deep-research/)
- [How OpenAI, Gemini, Claude use agents (ByteByteGo)](https://blog.bytebytego.com/p/how-openai-gemini-and-claude-use) · [Deep Research Agents: survey (arXiv 2506.18096)](https://arxiv.org/pdf/2506.18096)
- [GPT Researcher (GitHub)](https://github.com/assafelovic/gpt-researcher) · [GPT Researcher (Tavily docs)](https://docs.tavily.com/examples/open-sources/gpt-researcher)
- [Stanford STORM (GitHub)](https://github.com/stanford-oval/storm) · [STORM project](https://storm-project.stanford.edu/research/storm/)
- [Introducing Perplexity Deep Research](https://www.perplexity.ai/hub/blog/introducing-perplexity-deep-research)
- [AI Hallucinations in Research Citations (Enago)](https://www.enago.com/academy/ai-hallucinations-research-citations/) · [Fabricated references study (StudyFinds)](https://studyfinds.org/chatgpts-hallucination-problem-fabricated-references/) · [Synthesis Gap (arXiv 2601.12369)](https://arxiv.org/pdf/2601.12369)
- [Query Expansion by Prompting LLMs (arXiv 2305.03653)](https://arxiv.org/pdf/2305.03653) · [LLM query expansion fails for ambiguous queries (arXiv 2505.12694)](https://arxiv.org/html/2505.12694v1) · [Query optimization survey (arXiv 2412.17558)](https://arxiv.org/html/2412.17558v3)
- [Federated search (Wikipedia)](https://en.wikipedia.org/wiki/Federated_search) · [Result merging for metasearch (Springer)](https://link.springer.com/chapter/10.1007/11581062_5) · [How LLMs improve precision & recall (Research Solutions)](https://www.researchsolutions.com/blog/how-llms-can-improve-search-precision-and-recall)
