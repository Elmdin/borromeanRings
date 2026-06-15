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

Open items live in [`../DELAYED-DECISIONS.md`](../DELAYED-DECISIONS.md); a delayed decision
graduates to an ADR once the Maintainer resolves it.
