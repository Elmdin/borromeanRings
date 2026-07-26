"""Core text utilities: slugify, word_count, truncate."""

from __future__ import annotations

import re

_NON_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Return a lowercase, hyphen-separated slug of ``text``.

    Non-alphanumeric runs collapse to a single hyphen; leading/trailing hyphens
    are stripped. An empty or all-symbol input yields an empty string.
    """
    return _NON_SLUG.sub("-", text.lower()).strip("-")


def word_count(text: str) -> int:
    """Count whitespace-separated words in ``text`` (0 for empty/blank)."""
    return len(text.split())


def truncate(text: str, limit: int, suffix: str = "…") -> str:
    """Truncate ``text`` to at most ``limit`` characters, appending ``suffix``.

    Text at or under the limit is returned unchanged. ``limit`` must be
    non-negative; the result (including ``suffix``) never exceeds ``limit``.
    """
    if limit < 0:
        raise ValueError("limit must be non-negative")
    if len(text) <= limit:
        return text
    if limit < len(suffix):
        return text[:limit]
    return text[: limit - len(suffix)] + suffix
