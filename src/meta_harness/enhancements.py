"""Agent-enhancement recommender — surface open-source tools that improve the
**wrapped AI itself**, not the code it writes.

borromeanRings's founding stance is "enhance the wrapped agent; the agent performs."
Beyond prompt-rewriting and steered research, a governed project benefits from a
curated capability layer: model routers, MCP servers, observability, caching. This
is the advisory selector for that layer — a sibling of the project profiler
(identify interests → recommend tools → hint at integration). **Advisory, never a
gate**: it proposes; the human decides and wires.

The catalog is **curated and health-audited** — it is not an authoritative or
exhaustive index. Every entry carries the evidence a recommendation rests on: the
source URL (never a search query), the date its maintenance was last verified, whether
it needs an API key, and which substrates it can actually serve. A tool that only acts
on API-key traffic is never offered to a subscription agent CLI that exposes none —
that recommendation would send the user somewhere they cannot go. Unverified entries
are marked so a recommendation never asserts more certainty than it has (correctness
first). Audit sources: docs/research/AGENT-TOOLING-SURVEY.md (2026-09-02).
See docs/specs/SPEC-enhancements.md, ADR-0037, and #133.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from meta_harness.spine import load_config

# Stable category vocabulary the recommender filters on.
CATEGORIES: tuple[str, ...] = (
    "model-routing",
    "mcp-server",
    "observability",
    "caching",
    "evaluation",
    "context",
)


#: Where the wrapped AI runs. ``claude-code`` is a subscription agent CLI: the model
#: calls happen inside the vendor's client, so proxies, routers, and caches that sit on
#: API-key traffic cannot touch them. ``api-key`` is code that calls a model API directly.
SUBSTRATES: tuple[str, ...] = ("claude-code", "api-key")

#: Tools that work on every substrate (the default for a new entry).
ALL_SUBSTRATES: tuple[str, ...] = SUBSTRATES


@dataclass(frozen=True)
class EnhancementTool:
    """One open-source agent-enhancement tool in the curated catalog.

    ``maintained_as_of`` is the ISO date the project's activity was last checked, NOT
    a claim it is alive today; a stale date is shown to the reader, never hidden.
    """

    name: str
    category: str
    purpose: str  # one line: what it does for the wrapped agent
    when: str  # the signal that makes it worth recommending
    url: str  # source, to verify — a real repository, never a search query
    verified: bool = True  # False ⇒ maintainer/user-suggested, confirm before wiring
    maintained_as_of: str = ""  # ISO date of the last observed upstream activity
    needs_api_key: bool = False  # True ⇒ useless on a substrate with no key
    applies_to: tuple[str, ...] = ALL_SUBSTRATES


# Seed catalog. Curated, not exhaustive; verify each URL before wiring. Add entries
# via a PR (this is data, and the checker treats it as data — see ADR-0037).
CATALOG: tuple[EnhancementTool, ...] = (
    # --- act on API-key traffic only: never offered to claude-code -------------------
    EnhancementTool(
        "LiteLLM",
        "model-routing",
        "One OpenAI-style API in front of 100+ models, with routing, fallbacks, and budgets.",
        "you call multiple providers/models and want routing, cost caps, or fallbacks.",
        "https://github.com/BerriAI/litellm",
        maintained_as_of="2026-09-02",
        needs_api_key=True,
        applies_to=("api-key",),
    ),
    EnhancementTool(
        "Helicone",
        "observability",
        "LLM gateway + observability (latency, cost, logs) via a proxy.",
        "you want per-call cost/latency visibility without app changes.",
        "https://github.com/Helicone/helicone",
        maintained_as_of="2026-09-02",
        needs_api_key=True,
        applies_to=("api-key",),
    ),
    EnhancementTool(
        "GPTCache",
        "caching",
        "Semantic cache for LLM responses to cut repeat cost and latency. Upstream quiet"
        " since 2025-07 — confirm it is still maintained before wiring.",
        "you re-issue similar prompts and want to avoid paying twice.",
        "https://github.com/zilliztech/GPTCache",
        maintained_as_of="2025-07-11",
        needs_api_key=True,
        applies_to=("api-key",),
    ),
    # --- work on any substrate ---------------------------------------------------------
    EnhancementTool(
        "MCP reference servers",
        "mcp-server",
        "Model Context Protocol servers (files, git, memory, sqlite) the agent can call.",
        "the agent needs structured access to files, git, a DB, or persistent memory.",
        "https://github.com/modelcontextprotocol/servers",
        maintained_as_of="2026-09-02",
    ),
    EnhancementTool(
        "Serena",
        "mcp-server",
        "LSP-backed MCP toolkit: symbol-level find/edit across 40+ languages, so the agent"
        " reads a symbol instead of a whole file.",
        "the agent re-reads whole files to find one function, burning context.",
        "https://github.com/oraios/serena",
        maintained_as_of="2026-09-02",
    ),
    EnhancementTool(
        "pyright-lsp",
        "context",
        "Official Claude Code LSP plugin for Python: go-to-definition, references, and"
        " diagnostics without reading files end to end.",
        "a Python project where the agent spends its context on file reads.",
        "https://github.com/anthropics/claude-plugins-official",
        maintained_as_of="2026-09-02",
        applies_to=("claude-code",),
    ),
    EnhancementTool(
        "Repomix",
        "context",
        "Packs a repo into one AI-friendly file with per-file token counts and a"
        " signatures-only compress mode.",
        "you hand another model the whole repo, or want to measure its context weight.",
        "https://github.com/yamadashy/repomix",
        maintained_as_of="2026-09-02",
    ),
    EnhancementTool(
        "ast-grep",
        "evaluation",
        "Structural (AST) search, lint, and rewrite: deterministic, offline, machine-readable.",
        "you want precise structural invariants over code (API-usage rules) without regex.",
        "https://github.com/ast-grep/ast-grep",
        maintained_as_of="2026-09-02",
    ),
    EnhancementTool(
        "Langfuse",
        "observability",
        "Open-source LLM tracing, sessions, and evals — see what the agent actually did.",
        "you can't tell what the agent did across a run ('it went off building').",
        "https://github.com/langfuse/langfuse",
        maintained_as_of="2026-09-02",
    ),
    EnhancementTool(
        "Promptfoo",
        "evaluation",
        "Test and compare prompts/models with assertions and red-teaming.",
        "you change prompts/models and want regression evals, not vibes.",
        "https://github.com/promptfoo/promptfoo",
        maintained_as_of="2026-09-02",
    ),
)


def catalog_categories() -> tuple[str, ...]:
    """The categories actually present in the catalog (sorted, deduped)."""
    return tuple(sorted({tool.category for tool in CATALOG}))


def recommend(
    interests: tuple[str, ...] = (), *, substrate: str = "claude-code"
) -> list[EnhancementTool]:
    """Catalog tools that serve ``substrate`` and match ``interests`` (empty ⇒ all).

    Unknown interest categories match nothing (they are simply ignored, not an
    error — the caller may declare aspirational interests). A tool that cannot act
    on the substrate is never returned, whatever the interests say.
    """
    usable = [tool for tool in CATALOG if substrate in tool.applies_to]
    if not interests:
        return usable
    wanted = set(interests)
    return [tool for tool in usable if tool.category in wanted]


def render_recommendation(tools: list[EnhancementTool]) -> str:
    """Render tools as an advisory report grouped by category."""
    if not tools:
        return "agent-enhancement recommender: no matching tools in the catalog."
    lines = ["borromeanRings — agent-enhancement suggestions (advisory; verify before wiring):"]
    for category in sorted({tool.category for tool in tools}):
        lines.append(f"\n[{category}]")
        for tool in tools:
            if tool.category != category:
                continue
            flag = "" if tool.verified else "  (!) user-suggested — verify"
            lines.append(f"  - {tool.name}: {tool.purpose}{flag}")
            lines.append(f"      when: {tool.when}")
            facts = [f"activity checked {tool.maintained_as_of or 'never'}"]
            if tool.needs_api_key:
                facts.append("needs API key")
            lines.append(f"      {tool.url}  ({'; '.join(facts)})")
    return "\n".join(lines)


def main(config_path: str | Path = "borromeanrings.toml", *, substrate: str = "claude-code") -> str:
    """Render the advisory recommendation for the interests declared in config.

    Invoke with ``python3 -c "from meta_harness.enhancements import main; print(main())"``.
    The default substrate is the agent CLI borromeanRings wraps; pass ``"api-key"`` for
    code that calls a model API directly.
    """
    interests = load_config(config_path).enhancements_interests
    return render_recommendation(recommend(interests, substrate=substrate))
