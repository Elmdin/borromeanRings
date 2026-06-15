# ADR-0012 — Engineering process = risk-driven + TDD

**Status:** Accepted (Maintainer-confirmed 2026-06-15)

## Context
`PROCESS.md` declared a risk-driven + TDD process, but it was a **default chosen by the agent, never
deliberated with the Maintainer** — a gap the Maintainer rightly flagged (we never explicitly chose
between TDD / XP / Scrum / Lean). CS130 Part 3 says pick a process by context; CS130 Part 1 L4 says
generate alternatives and decide rationally. This ADR makes the decision real.

## Decision
**Risk-driven design + TDD**, confirmed by the Maintainer:
- **TDD** — write a failing test first, make it pass, refactor (Red→Green→Refactor). The gate already
  enforces the back half: tests must pass and coverage may not regress.
- **Risk-driven** — spend up-front design effort (specs/ADRs) on **hard-to-change / load-bearing**
  decisions; stay lean elsewhere. Scale ceremony to risk (CS130 Part 3, Fairbanks).
- **CI on every change** (already shipped, ADR-0008); small, reviewable, branched PRs.

## Alternatives considered (CS130 Part 3)
- **Strict XP** — test-first + CI + small releases + pair programming. Rejected: the extra ceremony
  (e.g. formal pairing) buys little for a solo, AI-driven project; we already keep its valuable parts
  (TDD, CI, small PRs).
- **Scrum / Agile** — sprints + backlog + Definition of Done. Rejected as primary: sprint cadence is
  overhead for one developer; we *do* keep a lightweight issue backlog and a DoD-as-gate (`verify.sh`).
- **Lean / Kanban** — continuous flow, minimize waste. Adopted in spirit (one work item at a time,
  ship value, avoid extra features) but it under-specifies design discipline, so not the primary frame.

## Consequences
- (+) Matches how we already work and what the gate already enforces; minimal change.
- (+) Risk-driven keeps design effort proportional — avoids both under- and over-engineering.
- (−) TDD's "test first" is a discipline the gate can only partially enforce (it checks tests pass +
  coverage, not authoring order); honored by convention. Supersedes the implicit default in `PROCESS.md`.