# ADR-0005 — Checks as a uniform-contract registry; substrate Adapter seam

**Status:** Accepted

## Context
borromeanRings's durable value depends on two anticipated changes being *cheap*: (1) adding/replacing a
check, and (2) targeting a new agent harness. CS130 information hiding (Part 2 L5) says name those
likely-to-change decisions and isolate each behind a stable interface. This ADR records the two
structural seams that deliver QAS-3 and QAS-4.

## Decision
1. **Checks are a registry of independent scripts under a uniform contract.** Each `checks/NN_*.sh`
   runs one tool, exits non-zero on failure, and emits a receipt. `verify.sh` discovers and
   aggregates them fail-closed; `manifest.json` is the single source of the expected-check list
   (Single Choice Principle). The *tool* a check uses is a module secret.
2. **The substrate is hidden behind an Adapter.** `verify.sh` is substrate-neutral; the `.claude/`
   hooks are thin adapters translating Claude Code events into calls on the gate. A new harness is
   a new adapter — zero edits to `checks/` or `verify.sh`.

## Alternatives considered
- **One monolithic `verify` program** — rejected: adding a check would edit core logic (high
  coupling); violates QAS-3.
- **Hooks call tools directly (no `verify.sh` indirection)** — rejected: the verdict would differ
  by caller and couple every check to Claude Code; breaks QAS-2 and QAS-4.
- **Build the full plugin/tool registry now** — rejected: premature (PLAN-v0 §10). v0 only keeps
  the *pattern* clean so a registry is an extension, not a rewrite.

## Consequences
- (+) Add a check = 1 file + 1 manifest line; swap a tool = 1 file; add a substrate = 1 adapter.
- (+) Author-agnosticism falls out for free: every caller routes through the one gate.
- (−) Slight indirection (hook → gate → checks) vs. calling tools inline — accepted; it is exactly
  the indirection that buys harness-agnosticism.
- (−) Per-check process spawn has overhead vs. an in-process runner — acceptable for a gate where
  correctness and isolation dominate latency.
