"""Tests for the application-archetype catalog and evaluator (SPEC-archetypes.md)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from meta_harness.archetypes import (
    CATALOG,
    CATALOG_VERSION,
    MAX_FILE_BYTES,
    SKIP_DIRS,
    Feature,
    FeatureResult,
    Report,
    _glob_regex,
    evaluate,
    non_noop_checks,
    non_noop_violations,
    render_report,
    required_features,
)
from meta_harness.spine import ARCHETYPES

# --- catalog integrity ----------------------------------------------------------------


def test_catalog_keys_are_exactly_the_spine_vocabulary() -> None:
    assert set(CATALOG) == set(ARCHETYPES)
    assert CATALOG_VERSION == "1"
    for name, archetype in CATALOG.items():
        assert archetype.name == name


def test_every_feature_has_a_deterministic_predicate_and_a_justification() -> None:
    for archetype in CATALOG.values():
        assert archetype.features, archetype.name
        assert archetype.summary and archetype.playbook.strip()
        for feature in archetype.features:
            assert feature.paths or (feature.content and feature.pattern), feature.id
            assert bool(feature.content) == bool(feature.pattern), feature.id
            assert feature.title and feature.why, feature.id
            re.compile(feature.pattern)  # "" compiles too — presence-only predicate
            assert re.fullmatch(r"[a-z][a-z0-9_]+", feature.id), feature.id


def test_shared_feature_ids_are_identical_objects_across_archetypes() -> None:
    """A feature id means one predicate everywhere — two archetypes must not disagree."""
    seen: dict[str, Feature] = {}
    for archetype in CATALOG.values():
        for feature in archetype.features:
            assert seen.setdefault(feature.id, feature) == feature, feature.id


def test_must_be_non_noop_entries_look_like_check_ids() -> None:
    for archetype in CATALOG.values():
        for check in archetype.must_be_non_noop:
            assert re.fullmatch(r"\d\d_[a-z0-9_]+", check), (archetype.name, check)
    assert CATALOG["web-app"].must_be_non_noop == ("15_a11y", "40_test")
    assert CATALOG["embedded"].must_be_non_noop == ()


# --- required_features / non_noop_checks -----------------------------------------------


def test_required_features_unions_by_id_in_first_appearance_order() -> None:
    both = required_features(("cli", "library"))
    ids = [f.id for f in both]
    assert len(ids) == len(set(ids))
    assert ids[0] == CATALOG["cli"].features[0].id
    # shared ids (license, changelog) appear once, at their cli position
    assert "license_present" in ids and ids.count("license_present") == 1
    assert required_features(()) == ()
    assert required_features(("library", "library")) == required_features(("library",))


def test_required_features_fails_closed_on_unknown() -> None:
    with pytest.raises(ValueError, match="firmware"):
        required_features(("cli", "firmware"))


def test_non_noop_checks_is_sorted_pairs() -> None:
    assert non_noop_checks(("web-app", "cli")) == (
        ("00_build", "cli"),
        ("15_a11y", "web-app"),
        ("40_test", "cli"),
        ("40_test", "web-app"),
    )
    assert non_noop_checks(()) == ()


# --- evaluate ----------------------------------------------------------------------------


def _lib_tree(root: Path) -> None:
    (root / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "1.0"\n')
    (root / "LICENSE").write_text("MIT\n")
    (root / "CHANGELOG.md").write_text("# Changelog\n")


def test_evaluate_reports_presence_with_evidence(tmp_path: Path) -> None:
    _lib_tree(tmp_path)
    report = evaluate(tmp_path, ("library",))
    assert isinstance(report, Report) and report.archetypes == ("library",)
    by_id = {r.feature_id: r for r in report.results}
    assert by_id["package_manifest"] == FeatureResult(
        "package_manifest", CATALOG["library"].features[0].title, True, "pyproject.toml"
    )
    # content match cites path:line
    assert by_id["version_declared"].present
    assert by_id["version_declared"].evidence == "pyproject.toml:3"
    assert all(r.present for r in report.results)
    assert report.must_be_non_noop == (("00_build", "library"), ("40_test", "library"))


def test_evaluate_reports_absence_with_empty_evidence(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    report = evaluate(tmp_path, ("library",))
    by_id = {r.feature_id: r for r in report.results}
    assert by_id["version_declared"] == FeatureResult(
        "version_declared", by_id["version_declared"].title, False, ""
    )
    assert not by_id["license_present"].present


def test_evaluate_ignores_skipped_dirs_huge_and_unreadable_files(tmp_path: Path) -> None:
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "LICENSE").write_text("vendored\n")
    (tmp_path / "vendor" / "deep").mkdir(parents=True)
    (tmp_path / "vendor" / "deep" / "pyproject.toml").write_text("version = 1\n")
    (tmp_path / "pyproject.toml").write_bytes(b"version = 1\n" + b"#" * MAX_FILE_BYTES)
    unreadable = tmp_path / "CHANGELOG.md"
    unreadable.mkdir()  # a directory named like the file is not a file
    report = evaluate(tmp_path, ("library",))
    by_id = {r.feature_id: r for r in report.results}
    assert not by_id["license_present"].present  # only under node_modules
    assert not by_id["version_declared"].present  # only in vendor/ or an oversized file
    assert not by_id["changelog_present"].present
    assert by_id["package_manifest"].present  # presence-only ignores size
    assert "node_modules" in SKIP_DIRS


def test_evaluate_skips_a_file_it_cannot_read_and_keeps_looking(tmp_path: Path) -> None:
    bad = tmp_path / "pyproject.toml"
    bad.write_text("version = 2\n")
    bad.chmod(0)
    (tmp_path / "setup.cfg").write_text("[metadata]\nversion = 2\n")
    try:
        by_id = {r.feature_id: r for r in evaluate(tmp_path, ("library",)).results}
    finally:
        bad.chmod(0o644)
    assert by_id["version_declared"].present
    assert by_id["version_declared"].evidence == "setup.cfg:2"


def test_evaluate_content_match_at_any_depth(tmp_path: Path) -> None:
    (tmp_path / "src" / "api").mkdir(parents=True)
    (tmp_path / "src" / "api" / "routes.py").write_text('@app.get("/healthz")\ndef h(): ...\n')
    by_id = {r.feature_id: r for r in evaluate(tmp_path, ("web-api",)).results}
    assert by_id["health_endpoint_declared"].evidence == "src/api/routes.py:1"
    assert not by_id["rate_limiter_declared"].present


def test_glob_translation_is_anchored_and_single_segment_for_star() -> None:
    assert _glob_regex("**/*.py").match("a/b/c.py")
    assert _glob_regex("**/*.py").match("c.py")
    assert not _glob_regex("*.py").match("a/c.py")
    assert _glob_regex("a?.md").match("ab.md") and not _glob_regex("a?.md").match("a/.md")


def test_evaluate_fails_closed_on_unknown_archetype(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        evaluate(tmp_path, ("service",))


def test_evaluate_unions_shared_features_once(tmp_path: Path) -> None:
    ids = [r.feature_id for r in evaluate(tmp_path, ("web-api", "web-app")).results]
    assert ids.count("structured_logging_configured") == 1


# --- render_report -----------------------------------------------------------------------


def test_render_report_is_exact() -> None:
    report = Report(
        archetypes=("cli",),
        results=(
            FeatureResult("entrypoint_declared", "an entry point is declared", True, "cli.py:1"),
            FeatureResult("usage_documented", "usage is documented", False, ""),
        ),
        must_be_non_noop=(("00_build", "cli"), ("40_test", "cli")),
    )
    assert render_report(report) == (
        "archetypes: cli (catalog v1)\n"
        "  ok       entrypoint_declared — an entry point is declared  [cli.py:1]\n"
        "  MISSING  usage_documented — usage is documented\n"
        "1 of 2 required feature(s) MISSING for archetypes cli.\n"
        "must be non-noop: 00_build (cli), 40_test (cli)\n"
    )


def test_render_report_all_present_and_no_non_noop() -> None:
    report = Report(
        archetypes=("embedded",),
        results=(FeatureResult("watchdog_configured", "a watchdog is configured", True, "m.c:9"),),
        must_be_non_noop=(),
    )
    assert render_report(report) == (
        "archetypes: embedded (catalog v1)\n"
        "  ok       watchdog_configured — a watchdog is configured  [m.c:9]\n"
        "all 1 required feature(s) present for archetypes embedded.\n"
        "must be non-noop: (none)\n"
    )


# --- non_noop_violations -------------------------------------------------------------------


def test_non_noop_violations_flags_noop_and_absent_checks() -> None:
    statuses = {"15_a11y": "noop", "40_test": "pass"}
    assert non_noop_violations(("web-app",), statuses) == (
        "15_a11y: NOOP but required to inspect something by archetype web-app",
    )
    assert non_noop_violations(("cli",), statuses) == (
        "00_build: not in [checks].required but required to inspect something by archetype cli",
    )
    assert non_noop_violations((), {}) == ()
    assert non_noop_violations(("ml",), {"40_test": "fail"}) == ()
