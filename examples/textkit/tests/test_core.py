"""Tests for textkit.core — full coverage so borromeanRings's gate passes."""

import pytest

from textkit.core import slugify, truncate, word_count


def test_slugify_basic() -> None:
    assert slugify("Hello, World!") == "hello-world"


def test_slugify_collapses_and_strips() -> None:
    assert slugify("  --Foo__Bar!!  ") == "foo-bar"


def test_slugify_empty_and_symbols() -> None:
    assert slugify("") == ""
    assert slugify("!!!") == ""


def test_word_count() -> None:
    assert word_count("one two three") == 3
    assert word_count("   ") == 0
    assert word_count("") == 0


def test_truncate_under_limit_unchanged() -> None:
    assert truncate("short", 10) == "short"
    assert truncate("exact", 5) == "exact"


def test_truncate_appends_suffix() -> None:
    assert truncate("abcdefgh", 5) == "abcd…"
    assert len(truncate("abcdefgh", 5)) == 5


def test_truncate_limit_smaller_than_suffix() -> None:
    assert truncate("abcdef", 0) == ""
    assert truncate("abcdef", 1, suffix="...") == "a"


def test_truncate_negative_limit_raises() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        truncate("x", -1)
