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

## Phase 2+ — the deferred vision (⏳ planned, build only when directed)
From Build Brief §9 / `PLAN-v0.md` §10 — each is a future self-extension (build → gate → human-approved adopt).

| # | Capability | What it is | Status |
|---|---|---|---|
| 2 | **External rubric critic** | A *separate-model* verifier judging changes against a rubric — extends "verifier external to the generator" beyond mechanical checks | ⏳ |
| 3 | **Config/policy spine** | The declarative engine where projects/harnesses declare invariants; v0's manifest+receipts are the seed | ⏳ |
| 4 | **Research + safe prompt-refinement front-of-loop** | Pull in prior art / refine the task safely before the agent starts | ⏳ |
| 5 | **Instrumentation + A/B loop** | Measure whether the harness actually improves outcomes | ⏳ |
| 6 | **Orchestration / parallelism / worktrees** | Run agents in parallel in isolated worktrees | ⏳ |
| 7 | **Generator adapter + Executor interface** | Abstractions that make the agent and the run-environment swappable | ⏳ |
| 8 | **Multi-harness substrate** | Adapters for OpenCode / Hermes / others (the Adapter seam already exists) | ⏳ |
| 9 | **Multi-language stacks** | TS, Go, etc. behind the same uniform check contract | ⏳ |
| 10 | **Cloud-sandbox executor + offline prompt optimization** | Heavier execution + tuning environments | ⏳ |
| 11 | **Full self-assurance layer** | Tool-use instrumentation, config-compliance diffing, tamper-evidence, adversarial self-testing | ⏳ (receipts seeded in v0) |
| 12 | **Self-extension capability: deep-research / synthesis** | First capability borromeo builds, gates, and adopts into itself; needs a tool/plugin registry | ⏳ |
| 13 | **Verification ladder beyond mypy** | Hypothesis → CrossHair (SMT) → mutation testing → formal (Lean/Dafny, opt-in for tagged critical modules) | ⏳ |

## How items graduate
A deferred item becomes real only when the Maintainer directs it. It is then: spec'd
(`docs/SPEC-*.md`) → built on a branch → passes borromeo's own gate → human-approved merge (PR).
Capabilities adopted *into* borromeo face a **same-or-stricter** gate (trust root). Open setup
questions live in `DELAYED-DECISIONS.md`.
