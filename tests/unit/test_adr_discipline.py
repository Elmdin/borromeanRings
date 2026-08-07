"""Unit tests for the ADR-discipline gate (meta_harness.adr_discipline)."""

from __future__ import annotations

from meta_harness.adr_discipline import adr_violation


def test_feature_touching_src_without_adr_is_a_violation() -> None:
    v = adr_violation("feat/new-thing", ["src/meta_harness/new_thing.py"])
    assert v is not None
    assert "record" in v.lower() or "adr" in v.lower()


def test_feature_touching_src_with_an_adr_passes() -> None:
    v = adr_violation(
        "feat/new-thing",
        ["src/meta_harness/new_thing.py", "docs/adr/0099-new-thing.md"],
    )
    assert v is None


def test_non_feature_branch_is_never_required() -> None:
    assert adr_violation("fix/bug", ["src/meta_harness/x.py"]) is None
    assert adr_violation("dev", ["src/meta_harness/x.py"]) is None
    assert adr_violation("docs/tidy", ["src/meta_harness/x.py"]) is None


def test_feature_touching_only_docs_or_tests_passes() -> None:
    assert adr_violation("feat/x", ["docs/README.md", "tests/unit/test_x.py"]) is None


def test_empty_changeset_passes() -> None:
    assert adr_violation("feat/x", []) is None


def test_custom_prefixes_and_dirs() -> None:
    # A project may declare its own feature prefix and layout.
    v = adr_violation(
        "feature/y",
        ["app/y.py"],
        src_dir="app",
        adr_dir="decisions",
        require_prefixes=("feature/",),
    )
    assert v is not None
    ok = adr_violation(
        "feature/y",
        ["app/y.py", "decisions/0001-y.md"],
        src_dir="app",
        adr_dir="decisions",
        require_prefixes=("feature/",),
    )
    assert ok is None


def test_src_prefix_is_boundary_safe() -> None:
    # A path like "src_generated/x.py" must not match the "src" tree.
    assert adr_violation("feat/x", ["src_generated/x.py"]) is None
