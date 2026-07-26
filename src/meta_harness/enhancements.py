"""Agent-enhancement recommender — surface open-source tools that improve the
**wrapped AI itself**, not the code it writes.

borromeanRings's founding stance is "enhance the wrapped agent; the agent performs."
Beyond prompt-rewriting and steered research, a governed project benefits from a
curated capability layer: model routers, MCP servers, observability, caching. This
is the advisory selector for that layer — a sibling of the project profiler
(identify interests → recommend tools → hint at integration). **Advisory, never a
gate**: it proposes; the human decides and wires.

The catalog is **curated and maintainer-verified** — it is not an authoritative or
exhaustive index. Entries are seeded with well-known open-source projects; each
carries a source URL to verify, and unverified/user-suggested entries are marked
so a recommendation never asserts more certainty than it has (correctness first).
See docs/specs/SPEC-enhancements.md and ADR-0037.
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


@dataclass(frozen=True)
class EnhancementTool:
    """One open-source agent-enhancement tool in the curated catalog."""

    name: str
    category: str
    purpose: str  # one line: what it does for the wrapped agent
    when: str  # the signal that makes it worth recommending
    url: str  # source, to verify
    verified: bool = True  # False ⇒ maintainer/user-suggested, confirm before wiring


# Seed catalog. Curated, not exhaustive; verify each URL before wiring. Add entries
# via a PR (this is data, and the checker treats it as data — see ADR-0037).
CATALOG: tuple[EnhancementTool, ...] = (
    EnhancementTool(
        "LiteLLM",
        "model-routing",
        "One OpenAI-style API in front of 100+ models, with routing, fallbacks, and budgets.",
        "you call multiple providers/models and want routing, cost caps, or fallbacks.",
        "https://github.com/BerriAI/litellm",
    ),
    EnhancementTool(
        "RouteLLM",
        "model-routing",
        "Route easy requests to a cheap model and hard ones to a strong model to cut cost.",
        "a large share of calls are simple and don't need the top-tier model.",
        "https://github.com/lm-sys/RouteLLM",
    ),
    EnhancementTool(
        "OmniRoute",
        "model-routing",
        "Model routing for Claude Code (user-suggested — confirm scope/URL before wiring).",
        "you want per-task model selection inside Claude Code.",
        "https://github.com/search?q=omniroute",
        verified=False,
    ),
    EnhancementTool(
        "MCP reference servers",
        "mcp-server",
        "Model Context Protocol servers (files, git, memory, sqlite) the agent can call.",
        "the agent needs structured access to files, git, a DB, or persistent memory.",
        "https://github.com/modelcontextprotocol/servers",
    ),
    EnhancementTool(
        "Langfuse",
        "observability",
        "Open-source LLM tracing, sessions, and evals — see what the agent actually did.",
        "you can't tell what the agent did across a run ('it went off building').",
        "https://github.com/langfuse/langfuse",
    ),
    EnhancementTool(
        "Helicone",
        "observability",
        "LLM gateway + observability (latency, cost, logs) via a proxy.",
        "you want per-call cost/latency visibility without app changes.",
        "https://github.com/Helicone/helicone",
    ),
    EnhancementTool(
        "GPTCache",
        "caching",
        "Semantic cache for LLM responses to cut repeat cost and latency.",
        "you re-issue similar prompts and want to avoid paying twice.",
        "https://github.com/zilliztech/GPTCache",
    ),
    EnhancementTool(
        "Promptfoo",
        "evaluation",
        "Test and compare prompts/models with assertions and red-teaming.",
        "you change prompts/models and want regression evals, not vibes.",
        "https://github.com/promptfoo/promptfoo",
    ),
)


def catalog_categories() -> tuple[str, ...]:
    """The categories actually present in the catalog (sorted, deduped)."""
    return tuple(sorted({tool.category for tool in CATALOG}))


def recommend(interests: tuple[str, ...] = ()) -> list[EnhancementTool]:
    """Catalog tools matching ``interests`` (empty ⇒ the whole catalog).

    Unknown interest categories match nothing (they are simply ignored, not an
    error — the caller may declare aspirational interests).
    """
    if not interests:
        return list(CATALOG)
    wanted = set(interests)
    return [tool for tool in CATALOG if tool.category in wanted]


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
            lines.append(f"      {tool.url}")
    return "\n".join(lines)


def main(config_path: str | Path = "borromeanrings.toml") -> str:
    """Render the advisory recommendation for the interests declared in config.

    Invoke with ``python3 -c "from meta_harness.enhancements import main; print(main())"``.
    """
    interests = load_config(config_path).enhancements_interests
    return render_recommendation(recommend(interests))
