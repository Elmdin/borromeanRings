# ADR-0004 — First governed stack = Python

**Status:** Accepted

## Context
borromeanRings's first governed project is its own repo. We need one concrete language toolchain to wire
real checks against, chosen for mature, fast, widely-installed deterministic tooling.

## Decision
**Python** is the first stack. `verify.sh` targets: `ruff format` (format) + `ruff check` (lint) +
`mypy` (types) + `pytest` (+ coverage, reported as a ratchet per QAS-7) + `bandit` (security).

## Alternatives considered
- **TypeScript/Node** — viable, strong tooling; rejected for v0 only because Python's check tools
  are lighter to install on WSL2 and the Maintainer's first target is Python.
- **Go** — excellent built-in tooling; deferred — not the first target stack.
- **Multi-language from day one** — rejected: violates "no premature building"; the uniform check
  contract (ADR-0005) lets other stacks be added later without re-architecting.

## Consequences
- (+) Mature, fast, deterministic tools that map cleanly onto one check each (high cohesion).
- (+) `bandit`-only security in v0 keeps install light; `semgrep` is a future check (DD-2).
- (−) Other stacks aren't governed yet — by design; each becomes a new set of checks behind the
  same contract.

## Decision review (2026-06-15, Maintainer-confirmed)
This choice was originally a near-default, not a researched rational decision. On review the
Maintainer **confirmed Python** as a deliberate **low-stakes** choice, with honest rationale rather
than exhaustive alternative-research:
- borromeanRings is **stack-agnostic for the projects it governs** (any language via the check contract,
  ADR-0005), so its *own* implementation language has **low blast radius** — not a load-bearing
  decision in CS130 terms.
- Python's check toolchain (ruff/mypy/pytest/bandit) is mature and already wired and green.
- A full TS/Go/Rust comparison would be effort out of proportion to the low stakes; deliberately
  **not** done (rational decision-making includes deciding when *more* analysis isn't worth it —
  CS130 "bounded rationality / satisficing").
