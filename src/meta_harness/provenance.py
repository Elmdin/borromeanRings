"""Provenance gate: re-authored text must not reproduce its declared source.

ADR-0020 lets this Apache-2.0 repo port *ideas* from a CC BY-NC-SA sibling, never its
*expression*. The mechanical test a reviewer applied by hand — word-shingle overlap
against the source — lives here as a pure function so the gate applies it every time.

The decision is deliberately **binary and about facts**, not a score: a six-word run of
the changed text that also occurs in a source is an overlap; an overlap not covered by
the project's ``[provenance].allow`` list is a finding; any finding fails. The gate never
guesses which overlaps are "generic" (a license name, a stdlib idiom) — that judgement is
the human's, recorded once in the allowlist and reviewed like code. This module holds no
I/O: the check script reads git and the filesystem and hands texts in. See
docs/specs/SPEC-provenance.md and ADR-0070.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

#: Shingle size: the unit of evidence (six consecutive words), not a pass threshold.
DEFAULT_N = 6

Words = tuple[str, ...]


@dataclass(frozen=True)
class Shingle:
    """``n`` consecutive normalized words, located at the line of the first one."""

    words: Words
    line: int


@dataclass(frozen=True)
class Overlap:
    """One shingle found both in a changed file and in a source file."""

    shingle: str
    changed_path: str
    changed_line: int
    source_path: str
    source_line: int


def normalize_words(line: str) -> list[str]:
    """Lowercase, strip every non-alphanumeric character, collapse whitespace.

    Any character that is neither alphanumeric nor whitespace becomes a space, so all
    Unicode punctuation and symbols vanish while letters in any script and digits stay.
    """
    lowered = line.lower()
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in lowered)
    return cleaned.split()


def _is_fence(line: str) -> bool:
    return line.strip().startswith("```")


def _located_words(text: str) -> list[tuple[str, int]]:
    """Every word of ``text`` with its 1-based line, skipping fenced code blocks."""
    located: list[tuple[str, int]] = []
    fenced = False
    for number, line in enumerate(text.splitlines(), start=1):
        if _is_fence(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        located.extend((word, number) for word in normalize_words(line))
    return located


def shingles(text: str, n: int = DEFAULT_N) -> tuple[Shingle, ...]:
    """All ``n``-word shingles of ``text`` in order, each with its starting line."""
    if n < 1:
        raise ValueError(f"n must be at least 1, got {n}")
    located = _located_words(text)
    return tuple(
        Shingle(tuple(word for word, _ in located[i : i + n]), located[i][1])
        for i in range(len(located) - n + 1)
    )


def _contains_run(haystack: Words, needle: Words) -> bool:
    """True if ``needle`` occurs as a contiguous run inside ``haystack``."""
    width = len(needle)
    return any(haystack[i : i + width] == needle for i in range(len(haystack) - width + 1))


def is_allowed(words: Words, allow: Iterable[Words]) -> bool:
    """Is this shingle covered by an allow phrase?

    A phrase covers the shingle when it is a contiguous run of the shingle's words (a
    short generic phrase) or the shingle is a contiguous run of the phrase (a longer
    acknowledged passage). Adjacency is required: a scattered subset never matches.
    """
    return any(_contains_run(words, phrase) or _contains_run(phrase, words) for phrase in allow)


def _normalized_allow(allow: Sequence[str]) -> tuple[Words, ...]:
    phrases: list[Words] = []
    for entry in allow:
        words = tuple(normalize_words(entry))
        if not words:
            raise ValueError(
                f"[provenance].allow entry {entry!r} is empty after normalization "
                "and would match everything — failing closed"
            )
        phrases.append(words)
    return tuple(phrases)


def _source_index(sources: Mapping[str, str], n: int) -> dict[Words, dict[str, int]]:
    """shingle -> {source path: first line it occurs on}."""
    index: dict[Words, dict[str, int]] = {}
    for path, text in sources.items():
        for shingle in shingles(text, n):
            index.setdefault(shingle.words, {}).setdefault(path, shingle.line)
    return index


@dataclass(frozen=True)
class Comparison:
    """The overlaps split by the allowlist: ``findings`` fail, ``allowed`` are reported."""

    findings: tuple[Overlap, ...]
    allowed: tuple[Overlap, ...]


def _sorted(found: Iterable[Overlap]) -> tuple[Overlap, ...]:
    return tuple(
        sorted(found, key=lambda o: (o.changed_path, o.changed_line, o.shingle, o.source_path))
    )


def compare(
    changed: Mapping[str, str],
    sources: Mapping[str, str],
    allow: Sequence[str],
    n: int = DEFAULT_N,
) -> Comparison:
    """Every shingle shared between a changed file and a source file, partitioned.

    One :class:`Overlap` per (changed occurrence, source file), reporting the first line
    of that source file where the shingle occurs; each side sorted by changed path,
    changed line, shingle, source path. Overlap among the changed files themselves is
    never an overlap here. An allow entry that normalizes to nothing raises
    ``ValueError`` — it would match everything.
    """
    phrases = _normalized_allow(allow)
    index = _source_index(sources, n)
    findings: set[Overlap] = set()
    allowed: set[Overlap] = set()
    for changed_path, text in changed.items():
        for shingle in shingles(text, n):
            hits = index.get(shingle.words)
            if not hits:
                continue
            bucket = allowed if is_allowed(shingle.words, phrases) else findings
            joined = " ".join(shingle.words)
            for source_path, source_line in hits.items():
                bucket.add(Overlap(joined, changed_path, shingle.line, source_path, source_line))
    return Comparison(_sorted(findings), _sorted(allowed))


def overlaps(
    changed: Mapping[str, str],
    sources: Mapping[str, str],
    allow: Sequence[str],
    n: int = DEFAULT_N,
) -> tuple[Overlap, ...]:
    """The unlisted overlaps — :func:`compare`'s ``findings``. Any of them is a failure."""
    return compare(changed, sources, allow, n).findings


def render(found: Sequence[Overlap]) -> str:
    """One line per finding: ``changed:line ↔ source:line — "<shingle>"``."""
    return "\n".join(
        f'{o.changed_path}:{o.changed_line} ↔ {o.source_path}:{o.source_line} — "{o.shingle}"'
        for o in found
    )
