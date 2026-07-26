"""Tests for the T3 project profiler (docs/specs/SPEC-profiler.md, ADR-0024).

Deterministic core (archetype→profile→config) is tested with no model; only the
description→archetype step is injected. The emitted config round-trips through the
spine loader (P-2) so the recommendation is a gate-able artifact, not prose.
"""

import tomllib

from meta_harness.profiler import (
    EnforcementProfile,
    classify,
    known_archetypes,
    profile_for,
    recommend,
    render_config,
    render_recommendation,
)
from meta_harness.spine import load_config

_CORE = {"library", "cli", "web_api", "data_pipeline", "ml_service"}


def test_known_archetypes_cover_the_core_set() -> None:
    assert set(known_archetypes()) >= _CORE


def test_profile_for_web_api_prioritises_security_and_offers_stacks() -> None:
    profile = profile_for("web_api")
    assert profile.archetype == "web_api"
    assert "security" in profile.quality_priorities
    assert profile.stack_options  # 2-3 stack pathways with trade-offs
    assert profile.required_checks  # a non-empty gate


def test_profile_for_unknown_falls_back_to_conservative_default() -> None:
    profile = profile_for("nonsense-archetype")
    assert profile.archetype == "library"  # default, never empty/invalid
    assert profile.required_checks


def test_classify_uses_injected_classifier() -> None:
    assert classify("an HTTP service with endpoints", lambda _d: "web_api") == "web_api"


def test_classify_validates_and_falls_back_on_unknown() -> None:
    # A classifier that returns an unknown key must not produce an invalid gate.
    assert classify("whatever", lambda _d: "not-a-real-archetype") == "library"


def test_recommend_classifies_then_profiles() -> None:
    profile = recommend("a reusable package", lambda _d: "library")
    assert isinstance(profile, EnforcementProfile)
    assert profile.archetype == "library"


def test_render_config_round_trips_required_through_the_spine(tmp_path: object) -> None:
    profile = profile_for("web_api")
    toml_text = render_config(profile, language="python", package="svc")
    cfg_path = tmp_path / "borromeanrings.toml"  # type: ignore[attr-defined]
    cfg_path.write_text(toml_text, encoding="utf-8")

    loaded = load_config(cfg_path)
    assert loaded.required_checks == profile.required_checks  # spine parses the emitted gate
    assert tuple(loaded.context["value_priorities"]) == profile.quality_priorities


def test_render_config_emits_heavy_checks_forward_compatibly() -> None:
    # heavy is read by the post-ADR-0022 spine; here we assert the raw TOML carries it.
    profile = profile_for("library")
    raw = tomllib.loads(render_config(profile, package="lib"))
    assert raw["checks"]["heavy"] == list(profile.heavy_checks)


def test_render_recommendation_shows_priorities_and_stacks() -> None:
    text = render_recommendation(profile_for("cli"))
    assert "cli" in text
    assert any(opt.name in text for opt in profile_for("cli").stack_options)
