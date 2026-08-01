"""Agent-enhancement recommender (advisory). ADR-0037."""

from pathlib import Path

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


def test_recommend_empty_returns_whole_catalog() -> None:
    assert recommend() == list(CATALOG)


def test_recommend_filters_by_interest() -> None:
    routing = recommend(("model-routing",))
    assert routing
    assert all(t.category == "model-routing" for t in routing)


def test_recommend_unknown_interest_matches_nothing() -> None:
    assert recommend(("not-a-category",)) == []


def test_recommend_multiple_interests() -> None:
    tools = recommend(("caching", "observability"))
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
    out = main(cfg)
    assert "[caching]" in out
    assert "[model-routing]" not in out  # filtered to declared interest


def test_omniroute_is_present_but_flagged_unverified() -> None:
    # The user's motivating example is included but must not assert false certainty.
    omni = next((t for t in CATALOG if t.name == "OmniRoute"), None)
    assert omni is not None
    assert omni.verified is False
