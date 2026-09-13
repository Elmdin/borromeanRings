"""Quote fidelity: marked quotations verified verbatim against saved sources. ADR-0065."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from meta_harness.quotes import (
    STATUSES,
    Marker,
    OutsideProject,
    Quotation,
    QuoteReport,
    QuoteResult,
    extract,
    normalise,
    normalise_lines,
    parse_marker,
    render,
    verify,
)

SOURCE = "# Title\n\nRecall is the unsolved problem:\nthe best agent misses most sources.\nDone.\n"


def _sources(**files: str):  # type: ignore[no-untyped-def]
    def resolve(path: str) -> str | None:
        return files.get(path)

    return resolve


# --- normalise ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("plain", "plain"),
        ("  a \t b\n\nc  ", "a b c"),
        ("‘it’s’ “quoted”", "'it's' \"quoted\""),
        ('"wrapped"', "wrapped"),
        ('"only leading', '"only leading'),
        ('trailing only"', 'trailing only"'),
        ("end.", "end"),
        ("end?!…", "end"),
        ("end, ", "end"),
        ('"wrapped."', "wrapped"),
        ('"wrapped".', "wrapped"),
        ("mid. sentence", "mid. sentence"),
        ("", ""),
        ('"', '"'),
        ("...", ""),
    ],
)
def test_normalise_rules(raw: str, expected: str) -> None:
    assert normalise(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("a\nb", ("a", "b")),
        ("  a  b \n\n\t c \n", ("a b", "c")),
        ("“a\nb.”", ("a", "b")),
        ('"a\nb".', ("a", "b")),
        ("a:\nb", ("a:", "b")),
        ("", ()),
        (">\n", (">",)),
    ],
)
def test_normalise_lines_applies_the_whole_text_rules_then_per_line_whitespace(
    raw: str, expected: tuple[str, ...]
) -> None:
    assert normalise_lines(raw) == expected


# --- parse_marker ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("— source: docs/a.md#L3-L5", Marker("docs/a.md", 3, 5)),
        ("-- source: docs/a.md#L3-L5", Marker("docs/a.md", 3, 5)),
        ("— Source: docs/a.md#L7", Marker("docs/a.md", 7, 7)),
        ("  — source:   docs/a.md#L1-L1  ", Marker("docs/a.md", 1, 1)),
        ("<!-- quote: docs/a.md#L2-L4 -->", Marker("docs/a.md", 2, 4)),
        ("<!--quote:docs/a.md#L2-->", Marker("docs/a.md", 2, 2)),
        ("— source: docs/a.md#L0", Marker("docs/a.md", 0, 0)),
    ],
)
def test_parse_marker_accepts_both_forms(line: str, expected: Marker) -> None:
    assert parse_marker(line) == expected


@pytest.mark.parametrize(
    "line",
    [
        "— source: docs/a.md",
        "— source: docs/a.md#3-5",
        "— source: docs/a.md#L3-5",
        "source: docs/a.md#L3",
        "— source: docs/a.md#L3-L5 trailing",
        "> — source: docs/a.md#L3",
        "<!-- quote: docs/a.md#L3",
        "",
    ],
)
def test_parse_marker_rejects_other_lines(line: str) -> None:
    assert parse_marker(line) is None


# --- extract ---------------------------------------------------------------------------


def test_extract_blockquote_then_marker() -> None:
    doc = "intro\n\n> one\n>two\n> \n\n— source: s.md#L1-L2\n\nafter\n"
    assert extract(doc) == (Quotation(line=3, text="one\ntwo\n", marker=Marker("s.md", 1, 2)),)


def test_extract_marker_directly_after_blockquote_and_comment_form() -> None:
    doc = "> a\n<!-- quote: s.md#L4 -->\n"
    assert extract(doc) == (Quotation(line=1, text="a", marker=Marker("s.md", 4, 4)),)


def test_extract_unmarked_blockquotes_are_ignored() -> None:
    assert extract("> scope note\n\nprose\n\n> another\n") == ()


def test_extract_orphan_marker_is_reported_with_no_text() -> None:
    doc = "prose\n— source: s.md#L1\n"
    assert extract(doc) == (Quotation(line=2, text=None, marker=Marker("s.md", 1, 1)),)


def test_extract_second_marker_after_one_blockquote_is_orphan() -> None:
    doc = "> a\n— source: s.md#L1\n— source: s.md#L2\n"
    assert extract(doc) == (
        Quotation(line=1, text="a", marker=Marker("s.md", 1, 1)),
        Quotation(line=3, text=None, marker=Marker("s.md", 2, 2)),
    )


def test_extract_blockquote_followed_by_prose_then_marker_is_orphan() -> None:
    doc = "> a\n\nprose\n— source: s.md#L1\n"
    assert extract(doc) == (Quotation(line=4, text=None, marker=Marker("s.md", 1, 1)),)


def test_extract_two_quotations_and_trailing_blockquote() -> None:
    doc = "> a\n\n— source: s.md#L1\n> b\n> c\n\n\n<!-- quote: t.md#L2-L3 -->\n> tail\n"
    assert extract(doc) == (
        Quotation(line=1, text="a", marker=Marker("s.md", 1, 1)),
        Quotation(line=4, text="b\nc", marker=Marker("t.md", 2, 3)),
    )


def test_extract_empty_document() -> None:
    assert extract("") == ()


# --- verify ----------------------------------------------------------------------------


def test_verify_no_markers_is_empty_and_ok() -> None:
    report = verify("no quotes here\n> unmarked\n", _sources())
    assert report == QuoteReport(results=())
    assert report.is_empty
    assert report.ok
    assert report.counts == {status: 0 for status in STATUSES}


def test_verify_verbatim_multi_line_with_curly_quotes_and_punctuation() -> None:
    doc = (
        "> “Recall is the unsolved problem:\n"
        "> the best agent misses most sources.”\n\n"
        "— source: src.md#L3-L4\n"
    )
    report = verify(doc, _sources(**{"src.md": SOURCE}), document="d.md")
    assert report.results == (
        QuoteResult(document="d.md", line=1, marker=Marker("src.md", 3, 4), status="verbatim"),
    )
    assert report.ok
    assert not report.is_empty
    assert report.counts["verbatim"] == 1


def test_verify_multi_line_quote_wrapped_differently_from_the_source_is_drifted() -> None:
    doc = (
        "> Recall is the unsolved problem: the best agent\n"
        "> misses most sources.\n\n"
        "— source: src.md#L3-L4\n"
    )
    (result,) = verify(doc, _sources(**{"src.md": SOURCE})).results
    assert result.status == "drifted"


def test_verify_single_line_quote_may_be_a_substring_of_one_span_line() -> None:
    doc = "> the best agent misses most sources\n— source: src.md#L1-L5\n"
    report = verify(doc, _sources(**{"src.md": SOURCE}))
    assert report.results[0].status == "verbatim"


REVIEW_SOURCE = "The result is not conclusive.\nThe result is conclusive in later trials.\n"


def test_verify_a_word_dropped_at_a_line_boundary_is_drifted_not_verbatim() -> None:
    """PR #182 review: joining the span hid a dropped "not" — line-for-line is required."""
    doc = "> The result is\n> conclusive\n— source: r.md#L1-L2\n"
    (result,) = verify(doc, _sources(**{"r.md": REVIEW_SOURCE}), document="d.md").results
    assert result.status == "drifted"
    assert result.detail == (
        "--- quote (d.md:1)\n"
        "+++ r.md#L1-L2\n"
        "@@ -1,2 +1,2 @@\n"
        "-The result is\n"
        "-conclusive\n"
        "+The result is not conclusive.\n"
        "+The result is conclusive in later trials.\n"
    )


def test_verify_single_line_quote_spanning_a_line_break_is_drifted() -> None:
    source = "The trials were not conclusive; the result is\nconclusive in later trials.\n"
    (result,) = verify(
        "> the result is conclusive\n— source: r.md#L1-L2\n", _sources(**{"r.md": source})
    ).results
    assert result.status == "drifted"


def test_verify_single_line_quote_inside_one_line_is_verbatim() -> None:
    doc = "> The result is conclusive\n— source: r.md#L1-L2\n"
    (result,) = verify(doc, _sources(**{"r.md": REVIEW_SOURCE})).results
    assert result.status == "verbatim"


def test_verify_multi_line_quote_may_start_and_end_mid_line_at_word_boundaries() -> None:
    source = (
        "The trials were not conclusive; the result is\nconclusive in later trials, they said.\n"
    )
    doc = "> the result is\n> conclusive in later trials\n— source: r.md#L1-L2\n"
    (result,) = verify(doc, _sources(**{"r.md": source})).results
    assert result.status == "verbatim"


def test_verify_multi_line_quote_equal_to_a_run_inside_a_longer_span() -> None:
    source = "zero\none\ntwo\nthree\nfour\n"
    doc = "> one\n> two\n> three\n— source: r.md#L1-L5\n"
    (result,) = verify(doc, _sources(**{"r.md": source})).results
    assert result.status == "verbatim"
    doc = "> one\n> three\n— source: r.md#L1-L5\n"
    (result,) = verify(doc, _sources(**{"r.md": source})).results
    assert result.status == "drifted"


@pytest.mark.parametrize(
    ("quote", "status"),
    [
        ("conclusive in later", "verbatim"),
        ("sult is conclusive", "drifted"),
        ("The result is con", "drifted"),
        ("conclusive", "verbatim"),
        ("(in later trials)", "drifted"),
    ],
)
def test_verify_single_line_match_must_not_start_or_end_inside_a_word(
    quote: str, status: str
) -> None:
    (result,) = verify(
        f"> {quote}\n— source: r.md#L2\n", _sources(**{"r.md": REVIEW_SOURCE})
    ).results
    assert result.status == status


def test_verify_inconclusive_does_not_contain_conclusive() -> None:
    (result,) = verify(
        "> conclusive\n— source: r.md#L1\n", _sources(**{"r.md": "inconclusive\n"})
    ).results
    assert result.status == "drifted"


def test_verify_boundary_next_to_punctuation_counts_as_a_word_boundary() -> None:
    (result,) = verify("> result\n— source: r.md#L1\n", _sources(**{"r.md": "(result).\n"})).results
    assert result.status == "verbatim"


def test_verify_empty_blockquote_is_drifted() -> None:
    (result,) = verify(">\n— source: r.md#L1\n", _sources(**{"r.md": REVIEW_SOURCE})).results
    assert result.status == "drifted"


def test_verify_multi_line_quote_longer_than_the_span_is_drifted() -> None:
    doc = (
        "> The result is not conclusive.\n> The result is conclusive in later trials.\n"
        "> more\n— source: r.md#L1-L2\n"
    )
    (result,) = verify(doc, _sources(**{"r.md": REVIEW_SOURCE})).results
    assert result.status == "drifted"


def test_verify_blank_blockquote_lines_are_ignored_when_matching() -> None:
    doc = (
        "> The result is not conclusive.\n>\n> The result is conclusive in later trials.\n"
        "— source: r.md#L1-L2\n"
    )
    (result,) = verify(doc, _sources(**{"r.md": REVIEW_SOURCE})).results
    assert result.status == "verbatim"


def test_verify_resolver_may_refuse_a_path_outside_the_project() -> None:
    def resolve(_: str) -> str | None:
        raise OutsideProject("docs/link.md")

    (result,) = verify("> a\n— source: docs/link.md#L1\n", resolve, document="d.md").results
    assert result == QuoteResult(
        document="d.md",
        line=1,
        marker=Marker("docs/link.md", 1, 1),
        status="missing",
        detail="outside the project",
    )


def test_verify_drifted_carries_a_unified_diff() -> None:
    doc = (
        "> Recall is the solved problem:\n> the best agent misses most sources.\n"
        "— source: src.md#L3-L4\n"
    )
    report = verify(doc, _sources(**{"src.md": SOURCE}), document="d.md")
    (result,) = report.results
    assert result.status == "drifted"
    assert result.document == "d.md"
    assert result.line == 1
    assert result.detail == (
        "--- quote (d.md:1)\n"
        "+++ src.md#L3-L4\n"
        "@@ -1,2 +1,2 @@\n"
        "-Recall is the solved problem:\n"
        "+Recall is the unsolved problem:\n"
        " the best agent misses most sources.\n"
    )
    assert not report.ok
    assert report.counts["drifted"] == 1


def test_verify_missing_source() -> None:
    report = verify("> a\n— source: nope.md#L1\n", _sources(**{"src.md": SOURCE}))
    assert report.results == (
        QuoteResult(
            document="",
            line=1,
            marker=Marker("nope.md", 1, 1),
            status="missing",
            detail="no such file",
        ),
    )


@pytest.mark.parametrize("path", ["/etc/passwd", "../x.md", "a/../b.md", "a/..", "../"])
def test_verify_path_escaping_the_root_is_missing_not_resolved(path: str) -> None:
    calls: list[str] = []

    def resolve(requested: str) -> str | None:
        calls.append(requested)
        return SOURCE

    (result,) = verify(f"> a\n— source: {path}#L1\n", resolve).results
    assert result.status == "missing"
    assert result.detail == "path must be repo-relative (no leading '/', no '..')"
    assert calls == []


def test_verify_dots_inside_a_name_are_fine() -> None:
    (result,) = verify(
        "> Done\n— source: a..b/x.md#L5\n", _sources(**{"a..b/x.md": SOURCE})
    ).results
    assert result.status == "verbatim"


@pytest.mark.parametrize(
    ("span", "detail"),
    [
        ("L0", "span L0-L0 is outside 1-5"),
        ("L0-L2", "span L0-L2 is outside 1-5"),
        ("L4-L3", "span L4-L3 is outside 1-5"),
        ("L6", "span L6-L6 is outside 1-5"),
        ("L5-L6", "span L5-L6 is outside 1-5"),
    ],
)
def test_verify_out_of_range(span: str, detail: str) -> None:
    (result,) = verify(f"> a\n— source: src.md#{span}\n", _sources(**{"src.md": SOURCE})).results
    assert result.status == "out_of_range"
    assert result.detail == detail


def test_verify_last_line_is_in_range_with_and_without_trailing_newline() -> None:
    for text in ("x\ny", "x\ny\n"):
        (result,) = verify("> y\n— source: s.md#L2\n", _sources(**{"s.md": text})).results
        assert result.status == "verbatim", text
        (result,) = verify("> y\n— source: s.md#L3\n", _sources(**{"s.md": text})).results
        assert result.status == "out_of_range", text


def test_verify_empty_source_file_has_no_lines() -> None:
    (result,) = verify("> y\n— source: s.md#L1\n", _sources(**{"s.md": ""})).results
    assert result == QuoteResult(
        document="",
        line=1,
        marker=Marker("s.md", 1, 1),
        status="out_of_range",
        detail="span L1-L1 is outside 1-0",
    )


def test_verify_orphan_marker_never_touches_the_resolver() -> None:
    def resolve(_: str) -> str | None:
        raise AssertionError("must not resolve an orphan")

    (result,) = verify("prose\n— source: s.md#L1\n", resolve, document="d.md").results
    assert result == QuoteResult(
        document="d.md",
        line=2,
        marker=Marker("s.md", 1, 1),
        status="orphan",
        detail="marker has no blockquote in front of it",
    )


def test_verify_resolver_errors_propagate_for_fail_closed_callers() -> None:
    def resolve(_: str) -> str | None:
        raise OSError("unreadable")

    with pytest.raises(OSError, match="unreadable"):
        verify("> a\n— source: s.md#L1\n", resolve)


def test_verify_resolves_each_source_once_per_document() -> None:
    calls: list[str] = []

    def resolve(path: str) -> str | None:
        calls.append(path)
        return SOURCE

    doc = "> Done\n— source: s.md#L5\n\n> Title\n— source: s.md#L1\n\n> Done\n— source: t.md#L5\n"
    report = verify(doc, resolve)
    assert [r.status for r in report.results] == ["verbatim", "verbatim", "verbatim"]
    assert calls == ["s.md", "t.md"]


def test_verify_mixed_statuses_count_and_are_not_ok() -> None:
    doc = (
        "> Done\n— source: s.md#L5\n\n"
        "> gone\n— source: s.md#L5\n\n"
        "> x\n— source: none.md#L1\n\n"
        "> x\n— source: s.md#L9\n\n"
        "— source: s.md#L1\n"
    )
    report = verify(doc, _sources(**{"s.md": SOURCE}))
    assert [r.status for r in report.results] == [
        "verbatim",
        "drifted",
        "missing",
        "out_of_range",
        "orphan",
    ]
    assert report.counts == {
        "verbatim": 1,
        "drifted": 1,
        "missing": 1,
        "out_of_range": 1,
        "orphan": 1,
    }
    assert not report.ok
    assert not report.is_empty


def test_results_are_immutable() -> None:
    result = QuoteResult(document="d", line=1, marker=Marker("s", 1, 1), status="verbatim")
    with pytest.raises(FrozenInstanceError):
        result.status = "drifted"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        QuoteReport(results=()).results = (result,)  # type: ignore[misc]


def test_statuses_are_the_documented_five_in_report_order() -> None:
    assert STATUSES == ("verbatim", "drifted", "missing", "out_of_range", "orphan")


# --- render ----------------------------------------------------------------------------


def test_render_empty_report() -> None:
    assert render(QuoteReport(results=())) == "no marked quotations"


def test_render_lists_each_result_then_counts() -> None:
    doc = (
        "> Done\n— source: s.md#L5\n\n"
        "> gone\n— source: s.md#L5\n\n"
        "> x\n— source: none.md#L1\n\n"
        "> x\n— source: s.md#L9-L10\n\n"
        "<!-- quote: s.md#L1 -->\n"
    )
    report = verify(doc, _sources(**{"s.md": SOURCE}), document="docs/r.md")
    assert render(report) == (
        "docs/r.md:1: VERBATIM s.md#L5-L5\n"
        "docs/r.md:4: DRIFTED s.md#L5-L5\n"
        "    --- quote (docs/r.md:4)\n"
        "    +++ s.md#L5-L5\n"
        "    @@ -1 +1 @@\n"
        "    -gone\n"
        "    +Done.\n"
        "docs/r.md:7: MISSING none.md#L1-L1 (no such file)\n"
        "docs/r.md:10: OUT_OF_RANGE s.md#L9-L10 (span L9-L10 is outside 1-5)\n"
        "docs/r.md:13: ORPHAN s.md#L1-L1 (marker has no blockquote in front of it)\n"
        "quotes: 1 verbatim, 1 drifted, 1 missing, 1 out of range, 1 orphan"
    )


def test_render_all_verbatim_is_rows_plus_counts() -> None:
    report = verify("> Done\n— source: s.md#L5\n", _sources(**{"s.md": SOURCE}), document="a.md")
    assert render(report) == (
        "a.md:1: VERBATIM s.md#L5-L5\n"
        "quotes: 1 verbatim, 0 drifted, 0 missing, 0 out of range, 0 orphan"
    )


# --- fenced code blocks are examples, not claims ----------------------------------------


@pytest.mark.parametrize(
    "doc",
    [
        "```markdown\n> a\n— source: s.md#L1\n```\n",
        "~~~\n— source: s.md#L1\n~~~\n",
        "   ```\n<!-- quote: s.md#L1 -->\n   ```\n",
        "````md\n> a\n\n— source: s.md#L1\n````\n",
    ],
)
def test_extract_skips_fenced_code_blocks(doc: str) -> None:
    assert extract(doc) == ()


def test_extract_fence_ends_a_blockquote_so_a_later_marker_is_orphan() -> None:
    doc = "> a\n```\n```\n— source: s.md#L1\n"
    assert extract(doc) == (Quotation(line=4, text=None, marker=Marker("s.md", 1, 1)),)


def test_extract_resumes_after_a_fence() -> None:
    doc = "> a\n— source: s.md#L1\n```\n> b\n— source: s.md#L9\n```\n> c\n— source: s.md#L2\n"
    assert extract(doc) == (
        Quotation(line=1, text="a", marker=Marker("s.md", 1, 1)),
        Quotation(line=7, text="c", marker=Marker("s.md", 2, 2)),
    )


def test_extract_unclosed_fence_swallows_the_rest() -> None:
    assert extract("> a\n— source: s.md#L1\n```\n> b\n— source: s.md#L2\n") == (
        Quotation(line=1, text="a", marker=Marker("s.md", 1, 1)),
    )
