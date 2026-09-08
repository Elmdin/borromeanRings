"""Unit tests for the prior-art gate's pure core (meta_harness.prior_art).

The gate answers one question deterministically: *does this feature branch introduce
new public surface without a recorded survey of what already existed?* It is the
``13_adr`` pattern applied to reuse. See docs/specs/SPEC-prior-art.md and ADR-0051.
"""

from __future__ import annotations

from meta_harness.prior_art import new_public_symbols, survey_violation

# --- new_public_symbols: what this change adds to the public surface ------------------


def test_added_function_is_reported_per_file() -> None:
    old = {"pkg/m.py": "def a():\n    pass\n"}
    new = {"pkg/m.py": "def a():\n    pass\n\ndef b():\n    pass\n"}
    assert new_public_symbols(old, new) == {"pkg/m.py": ["b"]}


def test_unchanged_surface_reports_nothing() -> None:
    src = {"pkg/m.py": "def a():\n    pass\n"}
    assert new_public_symbols(src, src) == {}


def test_private_symbols_do_not_count() -> None:
    old = {"pkg/m.py": ""}
    new = {"pkg/m.py": "def _helper():\n    pass\n\nclass _Internal:\n    pass\n"}
    assert new_public_symbols(old, new) == {}


def test_brand_new_file_counts_every_public_symbol() -> None:
    new = {"pkg/fresh.py": "def a():\n    pass\n\nclass B:\n    pass\n"}
    assert new_public_symbols({}, new) == {"pkg/fresh.py": ["B", "a"]}


def test_removed_symbols_are_not_new() -> None:
    old = {"pkg/m.py": "def a():\n    pass\n\ndef b():\n    pass\n"}
    new = {"pkg/m.py": "def a():\n    pass\n"}
    assert new_public_symbols(old, new) == {}


def test_unparseable_new_source_is_skipped_not_fatal() -> None:
    """A syntax error is 20_lint's job; this gate must not crash on it."""
    assert new_public_symbols({}, {"pkg/bad.py": "def (:\n"}) == {}


# --- survey_violation: the gate decision ---------------------------------------------

NEW = {"src/pkg/m.py": ["hash_bytes"]}


def test_new_surface_on_feature_branch_without_survey_is_a_violation() -> None:
    v = survey_violation("feat/hashing", NEW, ["src/pkg/m.py"])
    assert v is not None
    assert "hash_bytes" in v
    assert "docs/surveys" in v


def test_new_surface_with_a_survey_record_passes() -> None:
    changed = ["src/pkg/m.py", "docs/surveys/0001-hashing.md"]
    assert survey_violation("feat/hashing", NEW, changed) is None


def test_no_new_surface_is_never_a_violation() -> None:
    """Nothing new ⇒ nothing to survey. The caller reports this as noop, not pass."""
    assert survey_violation("feat/refactor", {}, ["src/pkg/m.py"]) is None


def test_non_feature_branch_is_never_required() -> None:
    for branch in ("fix/bug", "docs/notes", "dev", "main", "HEAD"):
        assert survey_violation(branch, NEW, ["src/pkg/m.py"]) is None


def test_custom_prefixes_and_survey_dir() -> None:
    changed = ["src/pkg/m.py", "research/notes.md"]
    assert (
        survey_violation(
            "feature/x", NEW, changed, survey_dir="research", require_prefixes=("feature/",)
        )
        is None
    )
    assert survey_violation("feature/x", NEW, ["src/pkg/m.py"], require_prefixes=("feature/",))


def test_survey_dir_prefix_is_boundary_safe() -> None:
    """`docs/surveys_old/` must not satisfy a `docs/surveys/` requirement."""
    changed = ["src/pkg/m.py", "docs/surveys_old/stale.md"]
    assert survey_violation("feat/x", NEW, changed) is not None


def test_violation_names_every_new_symbol_and_its_file() -> None:
    many = {"src/a.py": ["one", "two"], "src/b.py": ["three"]}
    v = survey_violation("feat/x", many, ["src/a.py", "src/b.py"])
    assert v is not None
    for name in ("one", "two", "three", "src/a.py", "src/b.py"):
        assert name in v
