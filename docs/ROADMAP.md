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
| No-op Stop guard: skip the gate when the governed state is unchanged (content-hash cache, fail-closed) | ✅ | `.claude/hooks/stop_gate.sh`, `meta_harness/change_detect.py`, ADR-0016 |
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

## Scope: borromeo enhances agent capabilities (incl. deep research)
borromeo's roadmap is **harness features** — including the **deep-research enhancement** (borromeo
improves the agent's *built-in* deep research; it does not build a research product from scratch).

The only thing **out of scope** is an end-user app: the **notes/Kernel** is a separate product built
*with* borromeo (its own repo when built). See [`MANIFESTO.md`](MANIFESTO.md).

## Research enhancement — steer the agent's own search (ADR-0014)
borromeo does **not** search itself — it *steers the wrapped agent's existing search* to be
far more thorough and trustworthy. Delivered as a **user-invoked skill**
(`.claude/skills/borromeo-research/`): the agent shows a steerable search plan, runs many
query mutations across multiple engines + dorking + platforms, goes beyond the top results
(result graph, citation chains, handles ads/paywalls/anti-bot), synthesizes across all, and
**verifies every claim against its source (fail-closed)**, visibly. borromeo enforces; the
agent performs (with its own tools).

The earlier Python search pipeline (`meta_harness/deep_research.py` + runners) is a
**testbed** for the concepts (retrieval/verification/completeness/visibility), not the product.

## Phase 2 — other advanced harness features (⏳ build when directed)
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

## Separate products (built with borromeo — NOT on this roadmap)
These were previously mis-scoped as borromeo "layers." They are **separate products**, each in its
own repo when built. Their specs/research live here only as seeds pending extraction.

- **Deep Research tool** — find & synthesize information (deterministic, visualized, citation-verified,
  multi-engine, completeness-critic). Phase-1 prototype exists in-repo
  (`meta_harness/deep_research.py`, `tools/deep_research_demo.py`); spec + landscape in
  [`SPEC-deep-research.md`](SPEC-deep-research.md) and [`research/`](research/). **To be extracted.**
- **Notes / Kernel** — organize notes/plans into tasks, roadmaps, and visual maps on **Obsidian**
  (never rebuild an editor); turn everything into actionable next steps. Not started.

*(A research-to-build-software capability — a "research front-of-loop" that helps borromeo's wrapped
agent build software better — may remain a harness feature; that is distinct from the standalone
Deep Research product above.)*

## How items graduate
A deferred item becomes real only when the Maintainer directs it. It is then: spec'd
(`docs/SPEC-*.md`) → built on a branch → passes borromeo's own gate → human-approved merge (PR).
Capabilities adopted *into* borromeo face a **same-or-stricter** gate (trust root). Open setup
questions live in `DELAYED-DECISIONS.md`.
