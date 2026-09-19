# ADR-0060 — Research skill: declared budget, state on disk, extract-not-ingest

**Status:** Accepted (amends ADR-0014's skill; measurement per ADR-0055)

## Context
One invocation of the `borromeanrings-research` skill consumed ~70% of a session's usage
(issue #47). The audit (`docs/research/RESEARCH-SKILL-TOKEN-AUDIT.md`) measured the skill's
static cost at 4176 B (~1K tokens — not the cause) and traced the dynamic cost to the
protocol itself: no budget, no cache, whole pages ingested, and every intermediate result
(page text, result graph, query log, verification pass) kept in the conversation, where each
later turn pays for it again.

## Decision
Keep the skill's contract (plan + steering, many mutations, multi-engine + dorking +
platforms, beyond page one, result graph, citation chains, hostile-page handling,
visibility, synthesis over everything, fail-closed verification, coverage report), and
change *how* it is executed:

1. **Declared budget, never silent.** The plan states rounds, queries/round, sources/round
   and extracted lines/source (defaults in the skill; the user edits them; a project may set
   its own). These are knobs the user approves, **not gates** — no numeric enforcement.
2. **Working state on disk.** `docs/research/<slug>/{plan,log,graph,report}.md` and
   `sources/<n>.md`; the conversation receives one line per query and per source.
3. **Extract, never ingest.** Fetch with a prompt for the relevant passages; save passages.
   Never re-fetch a saved URL; never repeat a logged query.
4. **Verify against the saved passage.** The fail-closed entailment gate is unchanged; it
   reads the passage on disk and re-fetches only when the passage is missing.
5. **Delegate fetch+extract to a sub-agent where available**; read symbols, not files, on
   code hosts (pyright-lsp / Serena are catalogued, not installed).
6. **Saturation is a stop rule**, not a tip: a round with no new relevant source ends it.

The static cost went down (3692 B), so `.borromeanrings-context-baseline` is re-seeded to the
new lower total (31690): a ratchet tightens downward on purpose and is never raised here.

## Alternatives considered
- **Hard-coded caps enforced by a check** — rejected: an arbitrary number to game, and the
  harness cannot observe the agent's tool traffic without API keys (agent-only rule).
- **A Python pipeline that budgets for the agent** — rejected by ADR-0014; the agent's own
  tools must do the searching.
- **Leave the protocol, shrink the prose** — rejected: the prose is ~1% of the incident.

## Consequences
- (+) Cost scales with the declared budget instead of with the topic; the trust property
  (every claim entailed by fetched source text) is intact and now auditable on disk.
- (+) Research artefacts under `docs/research/` are reusable by later sessions.
- (−) The before/after token measurement on a benchmark query (issue #47 AC) is still open;
  it requires a real session and is recorded in the audit as not done.
- (−) The user-level copy installed by `install-global.sh` must be re-installed to pick this up.
