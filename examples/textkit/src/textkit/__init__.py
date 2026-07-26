"""textkit — a tiny text-utility library, governed by borromeanRings.

This exists to prove borromeanRings governs a *different* project archetype (a
plain library, not the meta-harness itself) with its own ``borromeanrings.toml``.
See examples/textkit/README.md.
"""

from textkit.core import slugify, truncate, word_count

__all__ = ["slugify", "truncate", "word_count"]
