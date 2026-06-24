# Architecture Decision Records

> CS130 (Part 1 L4 / Part 4): an ADR is the organizational memory of a load-bearing decision —
> context, the alternatives considered, the choice, and its consequences — so the decision can be
> revisited later instead of silently re-litigated. borromeo records these because its own thesis
> is auditable, evidence-backed engineering: it would be hypocritical to make these choices without
> a trail.

Format per record: **Status · Context · Decision · Alternatives considered · Consequences.**

| ADR | Title | Status |
|---|---|---|
| [0001](0001-substrate-claude-code.md) | Substrate = Claude Code (hook-based gate) | Accepted |
| [0002](0002-model-hosting-frontier-api.md) | Model hosting = frontier API | Accepted |
| [0003](0003-no-local-model-wsl2.md) | No local model (WSL2, no GPU) | Accepted |
| [0004](0004-first-stack-python.md) | First governed stack = Python | Accepted |
| [0005](0005-checks-registry-and-adapter-seam.md) | Checks as a uniform-contract registry; substrate Adapter seam | Accepted |
| 0006 | Coverage = ratchet, no absolute % | **Proposed** (pending DD-1) |
| [0007](0007-gated-explicit-merge.md) | Gated, explicitly-requested merge (no autonomous self-merge) | Accepted |
| [0008](0008-ci-runs-the-gate.md) | CI runs the gate as the required status check | Accepted |
| [0009](0009-command-orchestrated-auto-merge.md) | Command-orchestrated auto-merge (free private repo) | Accepted |
| [0010](0010-config-policy-spine.md) | Config/policy spine (`borromeo.toml`) | Accepted |
| [0011](0011-prompt-rewriting.md) | Prompt rewriting: enforced by borromeo, performed by the agent | Accepted |
| [0012](0012-engineering-process.md) | Engineering process = risk-driven + TDD | Accepted |
| [0013](0013-portability-reference-model.md) | Portability: govern any project by reference | Accepted |
| [0014](0014-research-enhances-agent-not-searches.md) | Research enhancement steers the agent's own search | Accepted |
| [0015](0015-per-language-check-sets.md) | Per-language check sets (gate adjusts to the project) | Accepted |
| [0016](0016-no-op-stop-gate-skip.md) | Skip the Stop gate when the governed state is unchanged | Accepted |
| [0017](0017-git-identity-enforcement.md) | Enforce the declared git commit identity (guard + gate) | Accepted |

Open items live in [`../DELAYED-DECISIONS.md`](../DELAYED-DECISIONS.md); a delayed decision
graduates to an ADR once the Maintainer resolves it.
