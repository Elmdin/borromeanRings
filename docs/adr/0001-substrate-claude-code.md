# ADR-0001 — Substrate = Claude Code (hook-based gate)

**Status:** Accepted

## Context
borromeanRings must express its gate through *some* agent harness. v0 needs one concrete substrate that
can (a) intercept the end of an agent's turn to run the gate, (b) auto-format on edit, and (c)
block dangerous commands — without us building an executor abstraction prematurely.

## Decision
Use **Claude Code** as the v0 substrate. The gate is wired through native hooks: **Stop**
(generate→verify→retry loop), **PostToolUse** (auto-format on Edit/Write), **PreToolUse**
(dangerous-command guard). Hook config is committed to the repo so the gate travels with it.

## Alternatives considered
- **OpenCode / Hermes / other harness** — rejected for v0 only: no reason to pick a second
  substrate before the gate is proven once. Kept reachable via the Adapter seam (ADR-0005).
- **Editor/CI-only gate (no agent hook)** — rejected: misses the core thesis of governing the
  *agent loop* itself; CI invocation is still supported as an alternate caller (QAS-2).

## Consequences
- (+) Fastest path to a working generate→verify→retry loop using verified, documented hooks.
- (+) Author-agnosticism is testable: the hook and a hand-run invoke the *same* `verify.sh`.
- (−) Couples v0 to Claude Code's hook contract — **contained** by keeping hooks as thin
  adapters over a substrate-neutral gate (ADR-0005). Adding another substrate is a new adapter.
