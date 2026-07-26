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
- **Honest certainty** — `verified=False` entries (e.g. user-suggested OmniRoute)
  render with a "verify before wiring" marker; every entry carries a source URL.
- **Curated, not authoritative** — a new tool is a one-line catalog PR (data).

## borromeanRings config

```toml
[enhancements]
interests = ["model-routing", "observability"]
```

Pure catalog + recommender, 100% covered. Categories: model-routing, mcp-server,
observability, caching, evaluation, context.
