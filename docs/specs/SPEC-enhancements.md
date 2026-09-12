# SPEC — Agent-enhancement recommender

**Status:** Implemented (advisory) · **Realized by:**
`src/meta_harness/enhancements.py`, `[enhancements]` · ADR-0037

## Purpose

Surface open-source tools that improve the **wrapped AI itself** (not the code it
writes): model routing, MCP servers, observability, caching, evaluation. A
profiler-style advisory recommender — proposes, never gates.

## Contract

| Piece | Behavior |
|---|---|
| `CATALOG` | curated, maintainer-verified `EnhancementTool`s (name, category, purpose, when, url, `verified`) |
| `recommend(interests)` | catalog tools whose category ∈ interests (empty ⇒ all; unknown category ⇒ nothing) |
| `render_recommendation(tools)` | advisory report grouped by category; unverified entries flagged "verify" |
| `main(config_path)` | render for `[enhancements].interests` — `python3 -c "from meta_harness.enhancements import main; print(main())"` |

- **Advisory only** — no gate, no pass/fail; it never dictates the agent's setup
  (red line).
- **Honest certainty** — `verified=False` entries render with a "verify before
  wiring" marker; every entry carries a real source URL (never a search query).
- **Health-audited** (#133) — every entry records `maintained_as_of` (the ISO date its
  upstream activity was last checked; a stale date is shown, never hidden),
  `needs_api_key`, and `applies_to` (substrates: `claude-code`, `api-key`).
  `recommend(substrate=...)` never offers a tool to a substrate it cannot serve: a
  proxy, router, or cache on API-key traffic is invisible to a subscription agent
  CLI. Dead upstreams are removed, not flagged (RouteLLM, no commits since
  2024-08-10). Audit source: `docs/research/AGENT-TOOLING-SURVEY.md`.
- **Curated, not authoritative** — a new tool is a one-line catalog PR (data).
- **Verified by** `tests/unit/test_enhancements.py` (catalog integrity, filtering, rendering).

## borromeanRings config

```toml
[enhancements]
interests = ["model-routing", "observability"]
```

Pure catalog + recommender, 100% covered. Categories: model-routing, mcp-server,
observability, caching, evaluation, context.
