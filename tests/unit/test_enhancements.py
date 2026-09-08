"""Agent-enhancement recommender (advisory). ADR-0037; health-audited catalog, #133."""

import re
from pathlib import Path

import pytest

from meta_harness.enhancements import (
    CATALOG,
    CATEGORIES,
    EnhancementTool,
    catalog_categories,
    main,
    recommend,
    render_recommendation,
)


def test_catalog_entries_are_well_formed() -> None:
    assert CATALOG
    for tool in CATALOG:
        assert tool.name and tool.purpose and tool.when
        assert tool.category in CATEGORIES  # every category is in the vocabulary
        assert tool.url.startswith("https://")


def test_catalog_categories_subset_of_vocabulary() -> None:
    assert set(catalog_categories()) <= set(CATEGORIES)
    assert catalog_categories() == tuple(sorted(catalog_categories()))  # sorted, deduped


def test_recommend_empty_returns_every_tool_that_serves_the_substrate() -> None:
    # Every catalog entry is reachable from some substrate (no orphaned entries) ...
    assert set(recommend(substrate="api-key")) | set(recommend()) == set(CATALOG)
    # ... and neither substrate sees the whole catalog: each filters something out.
    assert set(recommend()) < set(CATALOG)
    assert set(recommend(substrate="api-key")) < set(CATALOG)


def test_recommend_filters_by_interest() -> None:
    routing = recommend(("model-routing",), substrate="api-key")
    assert routing
    assert all(t.category == "model-routing" for t in routing)


def test_recommend_unknown_interest_matches_nothing() -> None:
    assert recommend(("not-a-category",)) == []


def test_recommend_multiple_interests() -> None:
    tools = recommend(("caching", "observability"), substrate="api-key")
    assert {t.category for t in tools} == {"caching", "observability"}


def test_render_groups_and_flags_unverified() -> None:
    tools = [
        EnhancementTool("A", "caching", "does a", "when a", "https://x", verified=True),
        EnhancementTool("B", "caching", "does b", "when b", "https://y", verified=False),
    ]
    out = render_recommendation(tools)
    assert "[caching]" in out
    assert "A: does a" in out
    assert "user-suggested — verify" in out  # B flagged
    assert "https://x" in out


def test_render_empty() -> None:
    assert "no matching tools" in render_recommendation([])


def test_render_multiple_categories_grouped() -> None:
    tools = [
        EnhancementTool("A", "caching", "a", "wa", "https://a"),
        EnhancementTool("B", "observability", "b", "wb", "https://b"),
    ]
    out = render_recommendation(tools)
    # both category headers present; each tool under its own header only
    assert "[caching]" in out and "[observability]" in out
    assert out.index("A: a") < out.index("[observability]") or "B: b" in out


def test_main_renders_declared_interests(tmp_path: Path) -> None:
    cfg = tmp_path / "borromeanrings.toml"
    cfg.write_text('[checks]\nrequired = ["00_build"]\n[enhancements]\ninterests = ["caching"]\n')
    out = main(cfg, substrate="api-key")
    assert "[caching]" in out
    assert "[model-routing]" not in out  # filtered to declared interest


ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def test_every_entry_carries_maintenance_evidence() -> None:
    for tool in CATALOG:
        assert ISO.match(tool.maintained_as_of), f"{tool.name}: maintained_as_of not ISO"
        assert tool.applies_to, f"{tool.name}: applies_to must name at least one substrate"


def test_no_entry_points_at_a_search_query() -> None:
    """A search URL is not a source; it was how a phantom tool stayed in the catalog."""
    for tool in CATALOG:
        assert "github.com/search" not in tool.url, f"{tool.name}: url is a search query"
        assert tool.url.startswith("https://"), tool.name


def test_known_dead_tools_are_gone() -> None:
    """RouteLLM: no commits since 2024-08-10 (verified 2026-09-02)."""
    assert "RouteLLM" not in {t.name for t in CATALOG}


def test_stale_tools_are_marked_not_hidden() -> None:
    """GPTCache: last push 2025-07-11. Kept, but its date is on the record."""
    gpt = next(t for t in CATALOG if t.name == "GPTCache")
    assert gpt.maintained_as_of == "2025-07-11"


def test_api_key_tools_are_not_recommended_for_claude_code() -> None:
    """LiteLLM/Helicone/GPTCache act on API-key traffic that subscription Claude Code
    does not expose. Recommending them there sends the user somewhere they cannot go."""
    names = {t.name for t in recommend(substrate="claude-code")}
    for absent in ("LiteLLM", "Helicone", "GPTCache", "Langfuse"):
        assert absent not in names, f"{absent} offered for a substrate it cannot serve"


def test_api_key_tools_still_recommended_where_they_apply() -> None:
    names = {t.name for t in recommend(substrate="api-key")}
    assert {"LiteLLM", "Helicone", "Langfuse"} <= names


def test_every_key_needing_tool_is_confined_to_api_key_substrate() -> None:
    """The invariant behind the substrate filter: needs_api_key ⇒ not offered to claude-code."""
    for tool in CATALOG:
        if tool.needs_api_key:
            assert tool.applies_to == ("api-key",), f"{tool.name} needs a key yet serves more"


def test_unknown_substrate_is_an_error_not_an_empty_answer() -> None:
    """A typo must not read as 'nothing applies to you'."""
    with pytest.raises(ValueError, match="unknown substrate"):
        recommend(substrate="clode-code")


def test_survey_additions_are_present_and_keyless() -> None:
    """Serena, Repomix, ast-grep, pyright-lsp: maintained, MIT/Apache, no key (2026-09-02)."""
    by = {t.name: t for t in CATALOG}
    for name in ("Serena", "Repomix", "ast-grep", "pyright-lsp"):
        assert name in by, f"{name} missing"
        assert by[name].needs_api_key is False
        assert "claude-code" in by[name].applies_to


def test_interest_filter_still_works_with_substrate() -> None:
    ctx = recommend(interests=("context",), substrate="claude-code")
    assert ctx and all(t.category == "context" for t in ctx)


def test_render_states_key_requirement_and_maintenance_date() -> None:
    text = render_recommendation(list(CATALOG))
    assert "needs API key" in text
    assert "2025-07-11" in text  # a stale date is shown, not hidden


def test_entry_is_immutable() -> None:
    t = CATALOG[0]
    assert isinstance(t, EnhancementTool)
    try:
        t.name = "x"  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("EnhancementTool must be frozen")
