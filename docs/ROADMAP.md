# borromeo — Roadmap (every feature, with status)

> The single place to see the **whole feature set** and where each piece stands. Vision/why is in
> [`VISION.md`](VISION.md); v0 detail in `PLAN-v0.md`. Order follows the Build Brief §9 build order:
> prove one gate, then add each capability only when justified by a real need ("no premature
> building"). Nothing past v0 is built until directed.
>
> Legend: ✅ shipped · 🟦 in review (open PR) · 🔜 next · ⏳ deferred (planned, not yet built)

## Phase 0 — v0: the gate (✅ SHIPPED, merged to `main`)
| Feature | Status | Where |
|---|---|---|
| Verifier/check registry (uniform contract, `manifest.json`) | ✅ | `checks/` |
| Outer gate, fail-closed (`verify.sh`) | ✅ | `verify.sh` |
| Six checks: build · format · lint · typecheck · test · security | ✅ | `checks/00..50` |
| Coverage **ratchet** (no absolute % target) | ✅ | `checks/40_test.sh` |
| Receipts / audit plumbing (minimal) | ✅ | `.meta-harness/receipts/` |
| Stop-hook generate→verify→retry loop (bounded + escalation) | ✅ | `.claude/hooks/stop_gate.sh` |
| PostToolUse auto-format · PreToolUse dangerous-command guard | ✅ | `.claude/hooks/` |
| Spec/context layer (`AGENTS.md`) | ✅ | `AGENTS.md` |
| CS130 planning docs (requirements, architecture, ADRs, test plan, process) | ✅ | `docs/` |

## Phase 1 — gated merge + CI (✅ complete)
| Feature | Status | Where |
|---|---|---|
| Gated, explicitly-requested merge command (`merge.sh` + tested policy) | ✅ | `merge.sh`, `meta_harness/merge_policy.py`, ADR-0007 |
| CI: GitHub Action running `verify.sh` on every PR | ✅ | `.github/workflows/verify.yml`, ADR-0008 |
| Auto-merge: `merge.sh --auto` waits for the PR's CI to pass, then merges | 🟦 in review | `merge.sh`, ADR-0009 |
| ~~Server-side branch protection / native `--auto`~~ | ⛔ blocked | needs GitHub Pro/Team or a public repo (private+free can't require checks); command-orchestrated instead (ADR-0009) |

## The three-layer stack
borromeo is built bottom-up as three mutually-reinforcing tools (see [`MANIFESTO.md`](MANIFESTO.md)).
Layer 1 (the harness) is largely built; Layers 2–3 are the larger product.

| Layer | Tool | Status |
|---|---|---|
| **1** | SWE harness — build pristine software | 🟩 core shipped; advanced features ⏳ below |
| **2** | Deep Research tool — find & synthesize information | ⏳ next major product |
| **3** | Borromeo Kernel — organize notes/plans into tasks, roadmaps, visual maps | ⏳ |

## Phase 2 — Layer 1 advanced harness features (⏳ build when directed)
Each is a future self-extension (build → gate → human-approved adopt).

| Capability | What it is | Status |
|---|---|---|
| **Config/policy spine** | Declarative `borromeo.toml`: declare required checks + context → enforced on every run (config-compliance). First iteration: required-check set + `[context]` | 🟦 in review (ADR-0010) |
| **Prompt rewriting** | Improve the **user's** in-the-moment prompt (preserve+improve intent); *performed by the wrapped agent*, borromeo enforces it via a UserPromptSubmit hook using the spine's `[context]`; shows the rewrite; toggle in `borromeo.toml`. Multi-prompting deferred. | 🟦 in review (ADR-0011) |
| **External rubric critic** | A *separate-model* verifier judging changes against a rubric — extends "verifier external to the generator" beyond mechanical checks | ⏳ |
| **Mathematical verification (code & claims)** | Code: Hypothesis → CrossHair (SMT) → mutation → formal (Lean/Dafny, opt-in). Claims: verify factual assertions, distinct from code | ⏳ |
| **Preserve wrapped-agent autonomy** | Enforce invariants on *outcomes*, never dictate the agent's planning/decisions (red line, VISION §6) | ✅ principle locked |
| **Tools + MCP + plug-and-play** | External/internal tools, MCP servers, plug in any skill/tool, compose with other harnesses | ⏳ |
| **Multi-harness substrate** | Adapters for OpenCode / Hermes / others (the Adapter seam already exists) | ⏳ |
| **Multi-language stacks** | TS, Go, etc. behind the same uniform check contract | ⏳ |
| **Generator adapter + Executor interface** | Make the agent and run-environment swappable | ⏳ |
| **Orchestration / parallelism / worktrees** | Run agents in parallel in isolated worktrees | ⏳ |
| **Instrumentation + A/B loop** | Measure whether the harness actually improves outcomes | ⏳ |
| **Cloud-sandbox executor + offline prompt optimization** | Heavier execution + tuning environments | ⏳ |
| **Full self-assurance layer** | Tool-use instrumentation, config-compliance diffing, tamper-evidence, adversarial self-testing | ⏳ (receipts seeded in v0) |

## Phase 3 — Layer 2: the Deep Research tool (🟦 research done; spec in review)
borromeo builds this *through* the harness, then **adopts** it (the harness can then research too).
- ✅ **Research done** — [`research/deep-research-landscape.md`](research/deep-research-landscape.md): how OpenAI/Perplexity/Gemini/GPT-Researcher/STORM work, and the gaps (non-determinism, ~40% bad citations, weak transparency) that become our differentiators.
- 🟦 **Spec in review** — [`SPEC-deep-research.md`](SPEC-deep-research.md): a deterministic, inspectable, **citation-verified** pipeline; phased build.

Target properties (upgrade existing deep-research to be):

| Property | Meaning |
|---|---|
| **Deterministic** | Same query → reproducible, auditable search path |
| **Visualized step-by-step** | Show exactly what it searched, found, and read — so you can trust it looked everywhere |
| **Referencing** | Every claim cited to its source |
| **Synthesizing** | Combine sources into a focused answer, not a link dump |
| **Focusing** | Stay on the question; avoid drift |
| **Clean & safe** | Avoid ads, BS/low-quality content, viruses |
| **Substrate-agnostic** | Works on any browser/search engine, with any AI agent or a bare LLM |

## Phase 4 — Layer 3: the Borromeo Kernel (⏳)
The second brain. Organize **all** notes/thoughts/plans into a visually navigable, modifiable
structure, and turn it into **actionable next steps**.

| Capability | Notes |
|---|---|
| Notes substrate | **Use Obsidian** — do not rebuild an editor; build the intelligence on top |
| Real-time organization | Ingest raw notes/text → cleaned, structured docs + graphs; **never lose original information** (show original → transformed) |
| Life-map | One navigable map of everything: options, current standing, next steps; tasks, roadmaps, visual maps/graphs |
| Actionability | Turn the map into concrete next steps; present options to family/friends/investors |
| Interop | Works with other AI agents |

## How items graduate
A deferred item becomes real only when the Maintainer directs it. It is then: spec'd
(`docs/SPEC-*.md`) → built on a branch → passes borromeo's own gate → human-approved merge (PR).
Capabilities adopted *into* borromeo face a **same-or-stricter** gate (trust root). Open setup
questions live in `DELAYED-DECISIONS.md`.
