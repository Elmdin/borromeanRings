"""Changelog discipline rules (Keep a Changelog). See meta_harness/changelog.py."""

from meta_harness.changelog import presence_violation, src_change_violation


def test_presence_missing_file() -> None:
    v = presence_violation(None, "CHANGELOG.md")
    assert v is not None
    assert "missing CHANGELOG.md" in v


def test_presence_no_unreleased_section() -> None:
    v = presence_violation("# Changelog\n\n## [1.0.0]\n", "CHANGELOG.md")
    assert v is not None
    assert "Unreleased" in v


def test_presence_ok() -> None:
    text = "# Changelog\n\n## [Unreleased]\n### Added\n- a thing\n"
    assert presence_violation(text, "CHANGELOG.md") is None


def test_presence_unreleased_is_case_insensitive() -> None:
    assert presence_violation("## [UNRELEASED]\n", "CHANGELOG.md") is None


def test_src_change_requires_changelog() -> None:
    changed = ["src/meta_harness/foo.py", "tests/test_foo.py"]
    v = src_change_violation(changed, "src", "CHANGELOG.md")
    assert v is not None
    assert "1 source file" in v


def test_src_change_satisfied_when_changelog_present() -> None:
    changed = ["src/meta_harness/foo.py", "CHANGELOG.md"]
    assert src_change_violation(changed, "src", "CHANGELOG.md") is None


def test_no_src_change_needs_no_changelog() -> None:
    # docs/tests only — no changelog entry required
    changed = ["docs/x.md", "tests/test_y.py"]
    assert src_change_violation(changed, "src", "CHANGELOG.md") is None


def test_src_prefix_not_confused_by_similar_dir() -> None:
    # 'source_notes/' must not count as the 'src/' tree
    changed = ["source_notes/x.py"]
    assert src_change_violation(changed, "src", "CHANGELOG.md") is None
