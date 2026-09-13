"""Rules for giving a governed project the ignore entry borromeanRings assumes (#219)."""

from __future__ import annotations

from pathlib import Path

from meta_harness.gitignore import (
    ARTEFACTS,
    COMMENT,
    ensure_ignored,
    entry_to_append,
    is_ignored,
)


def test_every_spelling_git_honours_counts_as_ignored() -> None:
    """Idempotent by path, not by exact line — a hand-edited file must not double up."""
    for spelling in (".meta-harness", ".meta-harness/", "/.meta-harness", "/.meta-harness/"):
        assert is_ignored(f"build/\n{spelling}\n*.pyc\n"), spelling
    assert is_ignored(".meta-harness/   # the gate's output")  # trailing comment
    assert not is_ignored("build/\n*.pyc\n")
    assert not is_ignored("# .meta-harness/\n")  # commented out is not ignored
    assert not is_ignored(".meta-harness-notes/\n")  # a different path


def test_a_negation_is_not_ignoring_it() -> None:
    """``!.meta-harness`` says the opposite; appending is right, not a duplicate."""
    assert is_ignored("!.meta-harness/\n") is False


def test_a_missing_file_is_created_with_every_artefact_and_the_reason() -> None:
    text = entry_to_append(None)
    assert text is not None
    assert text.startswith("#")  # the comment says what writes there
    for artefact in ARTEFACTS:
        assert artefact in text, artefact


def test_only_the_missing_artefacts_are_appended() -> None:
    """A file that already ignores one of them must not have it added again."""
    text = entry_to_append("build/\n.meta-harness/\n")
    assert text is not None
    assert ".meta-harness/" not in text.replace(COMMENT, "")
    assert ".coverage" in text


def test_nothing_to_append_when_all_are_ignored() -> None:
    assert entry_to_append("build/\n.meta-harness/\n.coverage\n") is None


def test_an_unterminated_last_line_is_not_joined() -> None:
    """A file not ending in a newline must not have the entry welded to its last line."""
    appended = entry_to_append("build/\n*.pyc")
    assert appended is not None
    assert appended.startswith("\n")
    combined = "build/\n*.pyc" + appended
    assert "*.pyc#" not in combined
    assert is_ignored(combined)


def test_ensure_is_idempotent(tmp_path: Path) -> None:
    first = ensure_ignored(tmp_path)
    assert first is not None and "created" in first
    after_first = (tmp_path / ".gitignore").read_text(encoding="utf-8")

    assert ensure_ignored(tmp_path) is None  # nothing to say the second time
    assert (tmp_path / ".gitignore").read_text(encoding="utf-8") == after_first


def test_an_existing_file_is_appended_to_never_replaced(tmp_path: Path) -> None:
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("# my project\nbuild/\n*.pyc\n", encoding="utf-8")

    said = ensure_ignored(tmp_path)

    text = gitignore.read_text(encoding="utf-8")
    assert said is not None and "added" in said
    assert "# my project" in text and "build/" in text and "*.pyc" in text
    assert is_ignored(text)


def test_an_unwritable_gitignore_is_not_an_error(tmp_path: Path) -> None:
    """Adoption must not fail over this; the worst case is the status quo."""
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("build/\n", encoding="utf-8")
    gitignore.chmod(0o444)
    try:
        assert ensure_ignored(tmp_path) is None
    finally:
        gitignore.chmod(0o644)
