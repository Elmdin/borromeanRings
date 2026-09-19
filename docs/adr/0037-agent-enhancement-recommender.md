# ADR-0037 — Agent-enhancement recommender (advisory)

**Status:** Accepted

## Context
borromeanRings's founding stance is "enhance the wrapped agent; the agent
performs." So far that meant prompt-rewriting and steered research. A governed
project also benefits from a curated **capability layer** of open-source tooling
that improves the *wrapped AI itself* — model routers (e.g. the user's OmniRoute
example), MCP servers, observability, semantic caching — distinct from the
quality gates, which govern the *code the agent writes*. This is a new matrix
dimension the user asked for.

## Decision
Add `meta_harness.enhancements`: a **curated catalog** of open-source
agent-enhancement tools plus a recommender (`recommend(interests)` →
`render_recommendation`), mirroring the project **profiler** (identify interests →
recommend → hint at integration). Declared via `[enhancements].interests`.
**Advisory only** — it proposes; the human verifies and wires. It never gates.

Each `EnhancementTool` carries a `verified` flag: entries the maintainer has
confirmed are `True`; user-suggested / unconfirmed ones are `False` and rendered
with a "verify" marker, so a recommendation never asserts more certainty than it
has.

**Amended 2026-09-08 (#133):** the 2026-09-02 tooling survey found the catalog
recommending a dead router (RouteLLM, last commit 2024-08-10), a search-query URL
(OmniRoute), and four tools that act only on API-key traffic and so cannot affect a
subscription agent CLI at all. Entries now carry `maintained_as_of`, `needs_api_key`
and `applies_to`; `recommend()` filters by substrate (default `claude-code`); dead
entries are removed and the phantom dropped. Correctness-first was the module's
stated contract and this is what honouring it costs: evidence per entry.

## Alternatives considered
- **A fail-closed gate that *requires* certain tools** — rejected hard: it would
  dictate the agent's toolchain, violating the red line ("enforce invariants on
  outcomes, never dictate the agent's setup"). Recommendation, not mandate.
- **An auto-updating live index (scrape awesome-lists / GitHub)** — rejected:
  network + non-determinism + supply-chain risk in a tool that suggests what to
  *install*. A curated, PR-reviewed catalog is auditable and honest; freshness is
  a maintainer PR, not a runtime fetch.
- **Assert full details for every trendy tool** — rejected on correctness: the
  seed is limited to projects known to be real OSS, each with a source URL to
  verify, and the `verified` flag keeps unconfirmed entries honestly marked.
- **Fold it into the profiler** — rejected: the profiler selects *enforcement*
  (which checks a project needs); this selects *agent capabilities*. Different
  concern, same advisory shape — a sibling module keeps each cohesive.

## Consequences
- (+) borromeanRings now has an advisory home for the agent-enhancement layer; a
  project declares interests and gets targeted, source-linked suggestions —
  including observability tools that answer the recurring "what did the agent
  actually do?" concern.
- (+) Pure catalog + recommender, 100% covered; adding a tool is a one-line PR
  (data), and unverified entries can't masquerade as vetted.
- (+) Stays inside the red line: advisory, never a gate.
- (−) The catalog is curated and *will* drift; it is explicitly not authoritative
  or exhaustive (freshness is ongoing maintenance).
- (−) "Recommend by interest category" is coarse; richer signals (archetype,
  current stack) can layer on later, like the profiler's classifier.
