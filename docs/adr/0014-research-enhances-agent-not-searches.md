# ADR-0014 — Research enhancement steers the agent's own search (it does not search itself)

**Status:** Accepted (supersedes the implicit approach in ADR-0011's deep-research framing)

## Context
The deep-research work drifted into a **Python pipeline that searches by itself** (urllib →
Wikipedia API). The Maintainer corrected the scope: borromeanRings's job is to **enhance the wrapped
agent's existing search** (e.g. Claude Code's WebSearch/browse) — give the user agency, influence,
and visibility, and make the agent search far more thoroughly — *using the agent's own search
infrastructure*. borromeanRings must not be its own search engine.

## Decision
borromeanRings's research enhancement is a **steering layer**, same pattern as prompt-rewriting (borromeanRings
enforces; the agent performs):
- Delivered as a **user-invoked skill** (`.claude/skills/borromeanrings-research/SKILL.md`) — the user
  invokes it for agency + visibility.
- The skill makes the agent: show a **search plan** the user can steer; run **many query
  mutations** across **multiple engines/platforms** (incl. Google dorking, social/specialized
  sources); **go beyond the top results**, build a **result graph**, follow citation chains, handle
  ads/paywalls/anti-bot gracefully; **synthesize across everything**; **verify each claim against its
  source (fail-closed)**; and **report coverage** — all with its own tools, visibly.
- The existing Python pipeline (`meta_harness/deep_research.py` + runners) is **deprecated to a
  testbed** (kept, not deleted — it exercises the concepts), not the product.

## Alternatives considered
- **borromeanRings runs its own search pipeline** (what was built) — rejected: replaces the agent instead
  of enhancing it, can't reach the agent's real search infra from Python, and isn't agent-agnostic.
- **Always-on hook** (auto-inject on research intent) — deferred: the Maintainer wants explicit
  agency, so a user-invoked skill is primary; an auto hook can be added later.

## Consequences
- (+) Uses the agent's own (capable) search infra; agent-agnostic; the user steers + sees the process.
- (+) Reuses the valuable concepts (verification gate, completeness, visibility) as *enforced
  discipline on the agent*, not Python code.
- (−) The skill is Claude-Code-shaped for now; installing it into governed target repos (via
  `init.sh`) is a follow-up. The testbed module remains but must not be mistaken for the product.
