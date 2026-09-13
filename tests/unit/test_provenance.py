"""Unit tests for the provenance gate's pure core (meta_harness.provenance).

Exact-value tests: the check's whole promise is that its report is a list of facts, so
each test pins the precise shingle, paths and line numbers it expects — never "some
overlap was found". See docs/specs/SPEC-provenance.md and ADR-0070.
"""

from __future__ import annotations

import pytest

from meta_harness.provenance import (
    DEFAULT_N,
    Comparison,
    Overlap,
    Shingle,
    compare,
    is_allowed,
    normalize_words,
    overlaps,
    render,
    shingles,
)

# A "source" ADR (stand-in for the CC-licensed sibling) with one distinctive sentence
# and one generic license phrase; and a changed doc that reproduces both.
SOURCE = (
    "# ADR-0004\n"
    "\n"
    "Stewardship is a cadence, not a fifth competency.\n"
    "Licensed under CC BY-NC-SA 4.0 — see LICENSE.\n"
)
CHANGED = (
    "# Our doc\n"
    "\n"
    "We hold that stewardship is a cadence, not a fifth competency in disguise.\n"
    "\n"
    "The sibling is licensed under CC BY-NC-SA 4.0 and we re-author.\n"
)


# --- normalization ------------------------------------------------------------------


def test_normalize_lowercases_strips_unicode_punctuation_and_collapses_whitespace() -> None:
    line = "  A Charter — is *never* “repaired”,\tdefaulted… →  or_partially accepted!  "
    assert normalize_words(line) == [
        "a",
        "charter",
        "is",
        "never",
        "repaired",
        "defaulted",
        "or",
        "partially",
        "accepted",
    ]


def test_normalize_keeps_digits_and_non_latin_letters() -> None:
    assert normalize_words("CC BY-NC-SA 4.0 — Ünïcode 日本語") == [
        "cc",
        "by",
        "nc",
        "sa",
        "4",
        "0",
        "ünïcode",
        "日本語",
    ]


def test_normalize_of_only_punctuation_is_empty() -> None:
    assert normalize_words("--- *** ---") == []


# --- shingles -------------------------------------------------------------------------


def test_default_shingle_size_is_six() -> None:
    assert DEFAULT_N == 6


def test_shingles_are_located_at_the_line_of_their_first_word() -> None:
    text = "one two three\nfour five six seven\n"
    assert shingles(text) == (
        Shingle(("one", "two", "three", "four", "five", "six"), 1),
        Shingle(("two", "three", "four", "five", "six", "seven"), 1),
    )


def test_shingles_span_lines_and_report_the_starting_line() -> None:
    text = "a\nb\nc d e f g\n"
    # 7 words → 2 shingles; the second starts at word 'b' on line 2.
    assert shingles(text) == (
        Shingle(("a", "b", "c", "d", "e", "f"), 1),
        Shingle(("b", "c", "d", "e", "f", "g"), 2),
    )


def test_fewer_words_than_n_yields_no_shingles() -> None:
    assert shingles("one two three four five") == ()
    assert shingles("") == ()


def test_custom_n_is_honoured() -> None:
    assert shingles("a b c", n=2) == (Shingle(("a", "b"), 1), Shingle(("b", "c"), 1))


def test_code_fences_contribute_no_words() -> None:
    text = (
        "intro words here\n"
        "```python\n"
        "from pathlib import Path  # inside the fence\n"
        "```\n"
        "outro words after the fence end\n"
    )
    got = shingles(text)
    joined = [" ".join(s.words) for s in got]
    assert joined == [
        "intro words here outro words after",
        "words here outro words after the",
        "here outro words after the fence",
        "outro words after the fence end",
    ]
    # The word after the fence keeps its real line number (5), not a renumbered one.
    assert got[-1].line == 5


def test_indented_and_tilde_free_fence_marker_toggles() -> None:
    # Only a stripped line starting with ``` toggles; a tilde fence is not recognised.
    text = "   ```\nhidden a b c d e f\n   ```\nshown a b c d e f\n"
    assert [" ".join(s.words) for s in shingles(text)] == ["shown a b c d e", "a b c d e f"]


# --- allowlist ------------------------------------------------------------------------


def test_short_allow_phrase_covers_any_shingle_containing_it() -> None:
    allow = [("cc", "by", "nc", "sa")]
    assert is_allowed(("licensed", "under", "cc", "by", "nc", "sa"), allow) is True
    assert is_allowed(("cc", "by", "nc", "sa", "4", "0"), allow) is True
    assert is_allowed(("cc", "by", "sa", "nc", "4", "0"), allow) is False


def test_long_allow_phrase_covers_every_shingle_inside_it() -> None:
    allow = [("stewardship", "is", "a", "cadence", "not", "a", "fifth", "competency")]
    assert is_allowed(("stewardship", "is", "a", "cadence", "not", "a"), allow) is True
    assert is_allowed(("a", "cadence", "not", "a", "fifth", "competency"), allow) is True
    assert is_allowed(("cadence", "not", "a", "fifth", "competency", "x"), allow) is False


def test_exact_allow_phrase_matches_itself() -> None:
    six = ("one", "two", "three", "four", "five", "six")
    assert is_allowed(six, [six]) is True


def test_empty_allowlist_allows_nothing() -> None:
    assert is_allowed(("a", "b", "c", "d", "e", "f"), []) is False


def test_allow_match_is_contiguous_not_subset() -> None:
    # Words present but not adjacent must not match.
    assert is_allowed(("a", "x", "b", "c", "d", "e"), [("a", "b")]) is False


# --- overlaps -------------------------------------------------------------------------


def test_planted_sentence_is_reported_with_both_locations_and_generic_phrase_is_allowed() -> None:
    found = overlaps(
        {"docs/ours.md": CHANGED},
        {"/sib/docs/adr/0004.md": SOURCE},
        allow=["CC BY-NC-SA"],
    )
    # Same changed line ⇒ ordered by shingle text (SPEC: path, line, shingle, source).
    assert found == (
        Overlap(
            shingle="a cadence not a fifth competency",
            changed_path="docs/ours.md",
            changed_line=3,
            source_path="/sib/docs/adr/0004.md",
            source_line=3,
        ),
        Overlap(
            shingle="is a cadence not a fifth",
            changed_path="docs/ours.md",
            changed_line=3,
            source_path="/sib/docs/adr/0004.md",
            source_line=3,
        ),
        Overlap(
            shingle="stewardship is a cadence not a",
            changed_path="docs/ours.md",
            changed_line=3,
            source_path="/sib/docs/adr/0004.md",
            source_line=3,
        ),
    )


def test_without_the_allow_entry_the_generic_phrase_is_a_finding_too() -> None:
    found = overlaps({"docs/ours.md": CHANGED}, {"/sib/adr.md": SOURCE}, allow=[])
    generic = [o for o in found if o.shingle == "licensed under cc by nc sa"]
    assert generic == [
        Overlap(
            shingle="licensed under cc by nc sa",
            changed_path="docs/ours.md",
            changed_line=5,
            source_path="/sib/adr.md",
            source_line=4,
        )
    ]
    # "under cc by nc sa 4" and "cc by nc sa 4 0" also overlap; total = 3 distinctive + 3.
    assert len(found) == 6


def test_allowlisting_the_whole_sentence_makes_it_pass() -> None:
    found = overlaps(
        {"docs/ours.md": CHANGED},
        {"/sib/adr.md": SOURCE},
        allow=["Stewardship is a cadence, not a fifth competency.", "cc by-nc-sa"],
    )
    assert found == ()


def test_no_overlap_is_empty() -> None:
    assert overlaps({"a.md": "alpha beta gamma delta epsilon zeta"}, {"s.md": SOURCE}, []) == ()


def test_punctuation_and_case_differences_still_overlap() -> None:
    changed = {"d.md": "A CHARTER — is never *repaired*, defaulted, or partially accepted."}
    source = {"s.py": "# a charter is never repaired defaulted or partially accepted\n"}
    got = overlaps(changed, source, [])
    assert [o.shingle for o in got] == [
        "a charter is never repaired defaulted",
        "charter is never repaired defaulted or",
        "is never repaired defaulted or partially",
        "never repaired defaulted or partially accepted",
    ]


def test_overlap_between_changed_files_is_not_a_finding() -> None:
    same = "the same six words repeated here"
    assert overlaps({"a.md": same, "b.md": same}, {"s.md": "unrelated words only"}, []) == ()


def test_first_line_per_source_file_is_reported_and_results_are_sorted() -> None:
    phrase = "one two three four five six"
    changed = {"z.md": phrase, "a.md": phrase}
    sources = {"s2.md": f"x\n{phrase}\n{phrase}\n", "s1.md": f"{phrase}\n"}
    got = overlaps(changed, sources, [])
    assert got == (
        Overlap(phrase, "a.md", 1, "s1.md", 1),
        Overlap(phrase, "a.md", 1, "s2.md", 2),
        Overlap(phrase, "z.md", 1, "s1.md", 1),
        Overlap(phrase, "z.md", 1, "s2.md", 2),
    )


def test_custom_n_is_threaded_through_overlaps() -> None:
    got = overlaps({"c.md": "alpha beta"}, {"s.md": "alpha beta"}, [], n=2)
    assert got == (Overlap("alpha beta", "c.md", 1, "s.md", 1),)


def test_empty_allow_entry_fails_closed() -> None:
    with pytest.raises(ValueError, match="empty after normalization"):
        overlaps({"c.md": "x"}, {"s.md": "x"}, allow=["— * —"])


def test_shingle_size_below_one_is_rejected() -> None:
    with pytest.raises(ValueError, match="n must be"):
        shingles("a b c", n=0)


def test_compare_partitions_into_findings_and_allowed() -> None:
    result = compare({"docs/ours.md": CHANGED}, {"/sib/adr.md": SOURCE}, allow=["CC BY-NC-SA"])
    assert isinstance(result, Comparison)
    assert [o.shingle for o in result.findings] == [
        "a cadence not a fifth competency",
        "is a cadence not a fifth",
        "stewardship is a cadence not a",
    ]
    assert [o.shingle for o in result.allowed] == [
        "cc by nc sa 4 0",
        "licensed under cc by nc sa",
        "under cc by nc sa 4",
    ]
    assert result.allowed[0] == Overlap("cc by nc sa 4 0", "docs/ours.md", 5, "/sib/adr.md", 4)
    # overlaps() is exactly the findings half.
    assert overlaps({"docs/ours.md": CHANGED}, {"/sib/adr.md": SOURCE}, ["CC BY-NC-SA"]) == (
        result.findings
    )


def test_compare_with_nothing_shared_is_empty_on_both_sides() -> None:
    assert compare({"a.md": "alpha beta gamma delta epsilon zeta"}, {"s.md": SOURCE}, []) == (
        Comparison((), ())
    )


# --- render ---------------------------------------------------------------------------


def test_render_lists_each_finding_with_both_locations_and_the_shingle() -> None:
    found = (
        Overlap("stewardship is a cadence not a", "docs/ours.md", 3, "/sib/adr.md", 3),
        Overlap("is a cadence not a fifth", "docs/ours.md", 3, "/sib/adr.md", 3),
    )
    assert render(found) == (
        'docs/ours.md:3 ↔ /sib/adr.md:3 — "stewardship is a cadence not a"\n'
        'docs/ours.md:3 ↔ /sib/adr.md:3 — "is a cadence not a fifth"'
    )


def test_render_of_nothing_is_empty() -> None:
    assert render(()) == ""
