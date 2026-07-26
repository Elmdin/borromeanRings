"""Tests for repository-layout enforcement logic (docs/specs/SPEC-layout.md)."""

from meta_harness.layout import disallowed_root_docs, excess_flat_tests, misplaced_specs


def test_misplaced_specs_flags_paths_outside_specs_dir() -> None:
    specs = [
        "docs/specs/SPEC-a.md",  # ok
        "docs/SPEC-b.md",  # misplaced
        "SPEC-c.md",  # misplaced (root)
    ]
    assert misplaced_specs(specs, "docs/specs") == ["SPEC-c.md", "docs/SPEC-b.md"]


def test_misplaced_specs_all_ok() -> None:
    assert misplaced_specs(["docs/specs/SPEC-a.md"], "docs/specs") == []


def test_misplaced_specs_disabled_when_no_dir() -> None:
    assert misplaced_specs(["SPEC-anywhere.md"], "") == []


def test_misplaced_specs_trailing_slash_tolerant() -> None:
    assert misplaced_specs(["docs/specs/SPEC-a.md"], "docs/specs/") == []


def test_disallowed_root_docs_flags_unlisted() -> None:
    root = ["README.md", "AGENTS.md", "SPEC.md", "NOTES.md"]
    allow = ["README.md", "AGENTS.md"]
    assert disallowed_root_docs(root, allow) == ["NOTES.md", "SPEC.md"]


def test_disallowed_root_docs_all_allowed() -> None:
    assert disallowed_root_docs(["README.md"], ["README.md", "AGENTS.md"]) == []


def test_disallowed_root_docs_disabled_when_allowlist_empty() -> None:
    assert disallowed_root_docs(["SPEC.md", "WHATEVER.md"], []) == []


def test_excess_flat_tests_threshold() -> None:
    assert excess_flat_tests(9, 15) is False
    assert excess_flat_tests(15, 15) is False  # at the limit is fine
    assert excess_flat_tests(16, 15) is True


def test_excess_flat_tests_disabled_when_threshold_nonpositive() -> None:
    assert excess_flat_tests(1000, 0) is False
    assert excess_flat_tests(1000, -1) is False
