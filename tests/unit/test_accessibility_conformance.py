"""Conformance: the a11y parser's namespace model vs a real HTML5 tree builder.

``meta_harness.accessibility`` has to decide, for every tag it reacts to, whether the
element is an **HTML** element — an ``<svg><title>`` names an icon, an ``<svg><h1>`` is
hoisted out into a genuine heading, an ``<svg><input>`` is not a form control. Those
rules come from the HTML parsing spec, and three rounds of review showed that *reciting*
them gets them wrong: the breakout list was first missed entirely, then filled in
backwards, then filled in partially.

So this suite does not restate the rules — it **derives** them. Each case is parsed
twice: once by html5lib (a spec-conformant tree builder, dev-only, never a runtime
dependency), which says what namespace each element really lands in, and once by the
module under test, whose *observable findings* reveal the same decision. The two must
agree. If a future Python or html5lib disagrees with the module, this fails.
"""

from __future__ import annotations

from typing import Any

import html5lib
import pytest

from meta_harness.accessibility import ALL_RULES, a11y_findings

HTML_NS = "{http://www.w3.org/1999/xhtml}"

#: Every tag worth asking about: the whole HTML element vocabulary the module could meet
#: inside a foreign subtree, so the breakout list is *derived* here, not copied.
CANDIDATE_TAGS: list[str] = [
    "a",
    "abbr",
    "address",
    "area",
    "article",
    "aside",
    "audio",
    "b",
    "base",
    "basefont",
    "bgsound",
    "big",
    "blockquote",
    "body",
    "br",
    "button",
    "canvas",
    "caption",
    "center",
    "code",
    "col",
    "colgroup",
    "dd",
    "desc",
    "details",
    "dir",
    "div",
    "dl",
    "dt",
    "em",
    "embed",
    "fieldset",
    "figcaption",
    "figure",
    "font",
    "footer",
    "form",
    "frame",
    "frameset",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "head",
    "header",
    "hgroup",
    "hr",
    "html",
    "i",
    "iframe",
    "image",
    "img",
    "input",
    "keygen",
    "label",
    "li",
    "link",
    "listing",
    "main",
    "mark",
    "marquee",
    "menu",
    "meta",
    "nav",
    "nobr",
    "noembed",
    "noframes",
    "noscript",
    "object",
    "ol",
    "p",
    "param",
    "plaintext",
    "pre",
    "ruby",
    "s",
    "samp",
    "script",
    "section",
    "select",
    "small",
    "source",
    "span",
    "strike",
    "strong",
    "style",
    "sub",
    "summary",
    "sup",
    "table",
    "tbody",
    "td",
    "template",
    "textarea",
    "tfoot",
    "th",
    "thead",
    "time",
    "title",
    "tr",
    "track",
    "tt",
    "u",
    "ul",
    "var",
    "video",
    "wbr",
    "xmp",
    "basefont",
    "bgsound",
    "keygen",
]

#: A tag that is in no HTML vocabulary, so a probe can drop it inside a candidate
#: without ever colliding with the candidate itself. html5lib treats an unknown element
#: as an ordinary HTML one, which is exactly what a marker needs to be.
MARKER = "<x-marker>M</x-marker>"
MARKER_TAG = f"{HTML_NS}x-marker"


def _parse(source: str) -> Any:
    """The spec-conformant tree, with namespaces kept."""
    return html5lib.parse(source, treebuilder="etree", namespaceHTMLElements=True)


def _has_html_element(source: str, tag: str) -> bool:
    """Did html5lib put a ``tag`` element in the **HTML** namespace anywhere?"""
    return any(el.tag == f"{HTML_NS}{tag}" for el in _parse(source).iter())


def _breakout_source(tag: str, attrs: str = "") -> str:
    """A document whose `<title>` is written *after* ``tag`` inside an `<svg>`.

    If ``tag`` breaks out, the browser closes the `<svg>`, so that `<title>` is the
    document's title — which both the tree builder and the `page_title` rule can see.
    """
    return (
        f'<html lang="en"><body><svg><{tag}{attrs}></{tag}><title>Home</title></svg></body></html>'
    )


def _module_saw_a_document_title(source: str) -> bool:
    """The module's observable: a document title it counted raises no `page_title`."""
    return not any(f.rule == "page_title" for f in a11y_findings(source))


def _module_saw_a_form_control(source: str) -> bool:
    """The module's observable: an HTML control with no name raises `control_label`."""
    return any(f.rule == "control_label" for f in a11y_findings(source, require=("control_label",)))


@pytest.mark.parametrize("tag", CANDIDATE_TAGS)
def test_breakout_decision_matches_a_real_tree_builder(tag: str) -> None:
    """For every tag: the module breaks out of `<svg>` exactly when a browser does."""
    source = _breakout_source(tag)
    assert _module_saw_a_document_title(source) == _has_html_element(source, "title"), tag


def test_the_derived_breakout_list_is_the_one_the_module_implements() -> None:
    """The set of tags that break out is exactly what html5lib says it is.

    Spelled out as a set comparison so a regression names the tags that moved, rather
    than only failing one parametrised case.
    """
    from meta_harness.accessibility import _BREAKOUT_TAGS

    oracle = {tag for tag in CANDIDATE_TAGS if _has_html_element(_breakout_source(tag), "title")}
    assert oracle == _BREAKOUT_TAGS


@pytest.mark.parametrize("attrs", ["", ' color="red"', ' face="x"', ' size="2"', ' id="x"'])
def test_font_breaks_out_only_with_a_presentational_attribute(attrs: str) -> None:
    """`<font>` is the one conditional entry in the breakout list."""
    source = _breakout_source("font", attrs)
    assert _module_saw_a_document_title(source) == _has_html_element(source, "title"), attrs


#: Foreign contexts that do or do not resume HTML for their children — including the
#: **cross pairs**, where the integration point is real but the wrong language is open.
#: An integration point belongs to one namespace: `<desc>` resumes HTML inside an
#: `<svg>`, `<mtext>` inside a `<math>`, and neither does anything in the other's
#: subtree. The module's `<input>` and `<title>` decisions must agree with where the
#: tree builder actually puts the element.
INTEGRATION_CASES = [
    ("<svg>{}</svg>", "svg, directly"),
    ("<svg><g>{}</g></svg>", "svg, nested"),
    ("<svg><desc>{}</desc></svg>", "svg desc"),
    ("<svg><title>{}</title></svg>", "svg title"),
    ("<svg><foreignObject>{}</foreignObject></svg>", "svg foreignObject"),
    ("<math>{}</math>", "math, directly"),
    ("<math><mtext>{}</mtext></math>", "mathml mtext"),
    ("<math><mi>{}</mi></math>", "mathml mi"),
    ("<math><ms>{}</ms></math>", "mathml ms"),
    ('<math><annotation-xml encoding="text/html">{}</annotation-xml></math>', "annotation html"),
    (
        '<math><annotation-xml encoding="application/xhtml+xml">{}</annotation-xml></math>',
        "annotation xhtml",
    ),
    ("<math><annotation-xml>{}</annotation-xml></math>", "annotation, no encoding"),
    (
        '<math><annotation-xml encoding="image/svg+xml">{}</annotation-xml></math>',
        "annotation, other encoding",
    ),
    # The cross pairs: each point offered to the language it does *not* belong to.
    ("<svg><mtext>{}</mtext></svg>", "svg + mathml mtext"),
    ("<svg><mi>{}</mi></svg>", "svg + mathml mi"),
    ("<math><desc>{}</desc></math>", "math + svg desc"),
    ("<math><title>{}</title></math>", "math + svg title"),
    ("<math><foreignObject>{}</foreignObject></math>", "math + svg foreignObject"),
    (
        '<svg><annotation-xml encoding="text/html">{}</annotation-xml></svg>',
        "svg + annotation-xml",
    ),
    # A foreign subtree keeps its language rather than re-reading it off the tag name:
    # the <svg> in <math><svg> is a MathML element, so the <desc> in it is MathML's.
    ("<math><svg><desc>{}</desc></svg></math>", "the svg in math is mathml"),
    ("<svg><math><mtext>{}</mtext></math></svg>", "the math in svg is svg"),
    (
        "<svg><foreignObject><math><mtext>{}</mtext></math></foreignObject></svg>",
        "html resumes, then a real math",
    ),
    # <annotation-xml>'s encoding is matched whole and untrimmed, as the spec's ASCII
    # case-insensitive compare requires.
    (
        '<math><annotation-xml encoding=" text/html ">{}</annotation-xml></math>',
        "annotation, padded encoding",
    ),
    (
        '<math><annotation-xml encoding="TEXT/HTML">{}</annotation-xml></math>',
        "annotation, upper-case encoding",
    ),
]


@pytest.mark.parametrize("wrapper,label", INTEGRATION_CASES)
def test_form_controls_are_html_exactly_where_the_tree_builder_says(
    wrapper: str, label: str
) -> None:
    """`<input>` does not break out, so only an integration point makes it a control."""
    body = wrapper.format("<input>")
    source = f'<html lang="en"><head><title>t</title></head><body>{body}</body></html>'
    assert _module_saw_a_form_control(source) == _has_html_element(source, "input"), label


@pytest.mark.parametrize("wrapper,label", INTEGRATION_CASES)
def test_a_title_is_the_pages_title_exactly_where_the_tree_builder_says(
    wrapper: str, label: str
) -> None:
    """The same decision read through the **default-gated** rule, in both directions.

    A `<title>` past an integration point is the document's title; one that is still
    foreign names an icon. Getting the namespace wrong here does not merely invent a
    finding — it *silences* `page_title` on a document that has no title at all.
    """
    body = wrapper.format("<title>Icon</title>")
    source = f'<html lang="en"><body><h1>H</h1>{body}'
    assert _module_saw_a_document_title(source) == _has_html_element(source, "title"), label


def test_an_svg_anchor_stays_in_the_svg_namespace_and_is_still_checked() -> None:
    """The one place the module deliberately departs from namespace classification.

    html5lib confirms an `<svg><a href>` is an SVG element, not an HTML one. It is still
    a link a user clicks and a screen reader announces, so `link_text` checks it anyway
    — a judgement about user-facing links, recorded in the SPEC, not a parsing claim.
    """
    source = '<svg><a href="/x"></a></svg>'
    assert not _has_html_element(source, "a")  # the parsing fact
    assert [f.rule for f in a11y_findings(source, require=("link_text",))] == ["link_text"]


# --------------------------------------------------------------------------
# The other two recited lists, derived the same way (PR #211 review)
# --------------------------------------------------------------------------


def _probe(tag: str) -> Any:
    """``<body><tag>MARKER</tag>``, parsed by the oracle."""
    return _parse(f"<body><{tag}>{MARKER}</{tag}>")


def _is_void(tag: str) -> bool:
    """Does html5lib refuse to put anything *inside* this element?

    A void element cannot take the marker, so the tree builder makes it the element's
    **following sibling**. Every other outcome means something else happened and is not
    voidness: the marker nested (an ordinary container), was read as text (a raw-text
    element), was foster-parented *before* the tag (a `<table>`), or the tag was ignored
    where it stood (`<tr>` in a body). Only the sibling-after case is a void element.
    """
    root = _probe(tag)
    parents = {child: parent for parent in root.iter() for child in parent}
    elements = [el for el in root.iter() if el.tag == f"{HTML_NS}{tag}"]
    markers = [el for el in root.iter() if el.tag == MARKER_TAG]
    if not elements or not markers:
        return False
    parent = parents.get(elements[0])
    if parent is None or parents.get(markers[0]) is not parent:
        return False
    children = list(parent)
    return children.index(markers[0]) > children.index(elements[0])


def _is_text_only(tag: str) -> bool:
    """Does the tokenizer read this element's content as **text** rather than markup?

    Two facts together, because either alone lies: the marker must not survive as an
    element, *and* the element's text must be the marker's literal source. A `<select>`
    passes the first (it discards the element) and fails the second (it keeps the text),
    which is the difference between an insertion-mode quirk and a raw-text element.
    """
    root = _probe(tag)
    if any(el.tag == MARKER_TAG for el in root.iter()):
        return False
    elements = [el for el in root.iter() if el.tag == f"{HTML_NS}{tag}"]
    return bool(elements) and (elements[0].text or "").startswith(MARKER)


def test_the_derived_void_list_is_the_one_the_module_implements() -> None:
    """Void elements, computed from html5lib rather than recited.

    Nothing guarded this list before: the reviewer showed that adding `iframe` to it
    passed the whole suite. `<col>` is the one entry the probe cannot reach (see below).
    """
    from meta_harness.accessibility import _VOID_TAGS

    oracle = {tag for tag in CANDIDATE_TAGS if _is_void(tag)}
    assert oracle == _VOID_TAGS - {"col"}


def test_col_is_void_where_a_browser_will_actually_keep_one() -> None:
    """`<col>`'s voidness needs a `<colgroup>`: a browser drops it anywhere else.

    So it cannot be probed in a body the way every other tag can, and is asserted here
    instead — in a table, where html5lib keeps it and gives it neither text nor children.
    """
    from meta_harness.accessibility import _VOID_TAGS

    assert "col" in _VOID_TAGS
    assert not _has_html_element(f"<body><col>{MARKER}</col>", "col")  # dropped in a body
    tree = _parse(f"<table><colgroup><col>{MARKER}")
    columns = [el for el in tree.iter() if el.tag == f"{HTML_NS}col"]
    assert len(columns) == 1
    assert list(columns[0]) == [] and columns[0].text is None


def test_the_derived_text_only_list_is_the_one_the_module_implements() -> None:
    """Raw-text and RCDATA elements, computed from html5lib rather than recited.

    This is the list that was actually wrong: `html.parser` knows only `script`/`style`,
    so a `<textarea>` showing example markup used to be read as real elements and failed
    correct pages on the default-gated `img_alt`.
    """
    from meta_harness.accessibility import _TEXT_ONLY_TAGS

    oracle = {tag for tag in CANDIDATE_TAGS if _is_text_only(tag)}
    assert oracle == _TEXT_ONLY_TAGS


def test_only_plaintext_outlives_its_own_end_tag() -> None:
    """`</plaintext>` is text, not a tag: the element runs to end of file."""
    from meta_harness.accessibility import _TEXT_ONLY_TAGS, _UNCLOSABLE_TEXT_TAGS

    oracle = {
        tag
        for tag in _TEXT_ONLY_TAGS
        if not any(el.tag == MARKER_TAG for el in _parse(f"<body><{tag}></{tag}>{MARKER}").iter())
    }
    assert oracle == _UNCLOSABLE_TEXT_TAGS


def test_the_raw_text_list_is_the_parsers_own_and_the_oracle_agrees() -> None:
    """`_RAW_TEXT_TAGS` is read off `html.parser`, and html5lib confirms it is text."""
    from html.parser import HTMLParser

    from meta_harness.accessibility import _RAW_TEXT_TAGS, _TEXT_ONLY_TAGS

    assert frozenset(HTMLParser.CDATA_CONTENT_ELEMENTS) == _RAW_TEXT_TAGS
    assert _RAW_TEXT_TAGS < _TEXT_ONLY_TAGS


@pytest.mark.parametrize(
    "tag", ["textarea", "title", "iframe", "xmp", "noembed", "noframes", "plaintext"]
)
def test_markup_written_inside_a_text_only_element_is_a_string_to_both(tag: str) -> None:
    """The F2 regression, one tag at a time: no `<img>` there, so no `img_alt`.

    A "paste your markup here" `<textarea>` is correct markup that renders correctly, and
    the gate used to fail it — the one direction the SPEC's "better of the two errors"
    argument never covered, because it is a false *positive*.
    """
    body = f"<{tag}><img src='cat.png'><h1>Example</h1></{tag}>"
    source = f'<html lang="en"><head><title>T</title></head><body><h1>Demo</h1>{body}</body></html>'
    assert not _has_html_element(source, "img")
    assert a11y_findings(source, require=("img_alt", "heading_structure")) == []


def test_noscript_content_stays_markup_because_that_is_when_it_is_rendered() -> None:
    """Not a text-only element here, and deliberately so.

    A browser with scripting *on* reads `<noscript>` as raw text — but then it renders
    none of it. The reader who sees this content is the one with scripting off, for whom
    it is ordinary markup, which is also how the oracle parses it. So an `<img>` in there
    is a real image that needs an `alt`.
    """
    source = '<noscript><img src="x"></noscript>'
    assert _has_html_element(source, "img")
    assert [f.rule for f in a11y_findings(source, require=("img_alt",))] == ["img_alt"]


def test_markup_inside_a_foreign_script_is_parsed_the_way_a_browser_parses_it() -> None:
    """`<script>` is raw text only in HTML — and the module now follows that.

    html5lib parses the *content* of an `<svg><script>` as markup, so an `<h1>` written
    there is hoisted into a real heading. `html.parser` switches to CDATA on any
    `script`/`style`, which lost the heading and, with no `</script>` to come back at,
    swallowed the rest of the document — inventing "document has no `<h1>`" on a page
    that has one. The module now clears `CDATA_CONTENT_ELEMENTS` for a foreign element,
    and the two agree.
    """
    page = '<html lang="en"><head><title>T</title></head><body><h1>Real</h1>{}</body></html>'
    svg_script = page.format("<svg><script><h1>Hoisted</h1></script></svg>")
    assert sum(1 for el in _parse(svg_script).iter() if el.tag == f"{HTML_NS}h1") == 2
    assert [f.rule for f in a11y_findings(svg_script, require=("heading_structure",))] == [
        "heading_structure"
    ]
    # The unterminated case is the one that invented a violation, not merely missed one.
    unterminated = page.format("<math><style><h1>Hoisted</h1>")
    assert sum(1 for el in _parse(unterminated).iter() if el.tag == f"{HTML_NS}h1") == 2
    assert [f.rule for f in a11y_findings(unterminated, require=("heading_structure",))] == [
        "heading_structure"
    ]
    # An HTML <script> is raw text for both, so there is no disagreement there.
    html_script = page.format("<script><h1>Not markup</h1></script>")
    assert sum(1 for el in _parse(html_script).iter() if el.tag == f"{HTML_NS}h1") == 1
    assert a11y_findings(html_script, require=("heading_structure",)) == []


#: Adversarial documents that cross every seam at once: foreign roots, integration
#: points of both languages, breakout tags, text-only elements and self-closing syntax.
#: The module's findings must match what the tree builder actually built.
DIFFERENTIAL_CASES = [
    "<svg><mtext><input></mtext><img src='x'></svg>",
    "<math><desc><input></desc><h1>H</h1></math>",
    "<math><svg><desc><input><img src='x'></desc></svg></math>",
    "<svg><math><mtext><input></mtext></math></svg>",
    "<svg><foreignObject><math><mtext><input><img src='x'></mtext></math></foreignObject></svg>",
    "<textarea><svg><img src='x'></svg><input></textarea>",
    "<title><input><img src='x'></title>",
    "<svg><title><input></title></svg>",
    "<iframe><h1>H</h1><img src='x'></iframe><h1>Real</h1>",
    "<xmp><input></xmp><h1>Real</h1>",
    "<plaintext><h1>H</h1><img src='x'>",
    "<svg><style><h1>Hoisted</h1><img src='x'>",
    "<svg><script><input></script></svg>",
    "<h1>Real</h1><svg><font color='red'><img src='x'></font></svg>",
    "<h1>Real</h1><svg><foreignObject><textarea><img src='x'></textarea></foreignObject></svg>",
    "<a href='/x' />text</a><h1>Real</h1><img src='y'>",
    "<math><annotation-xml encoding=' text/html '><input></annotation-xml></math><h1>Real</h1>",
    "<svg><desc><svg><mtext><input></mtext></svg></desc></svg><h1>Real</h1>",
    # Found by the #211 verification: html.parser skips its raw-text switch on `/>`.
    "<script src='a.js'/><a href='/x'>Home</a><img src='y'>",
    "<style/><h1>Swallowed</h1><input>",
    "<script src='a.js'/>x</script><h1>Real</h1><a href='/x'>Docs</a>",
    "<h1>Real</h1><title><b></b></title>",
    "<h1>Real</h1><math><a href='/x'></a></math>",
]


@pytest.mark.parametrize("body", DIFFERENTIAL_CASES)
def test_the_module_and_the_tree_builder_find_the_same_elements(body: str) -> None:
    """One differential over the three element-counting rules, on adversarial markup."""
    source = f'<html lang="en"><head><title>T</title></head><body>{body}</body></html>'
    tree = list(_parse(source).iter())
    controls = {f"{HTML_NS}{tag}" for tag in ("input", "select", "textarea")}
    expected = set()
    if any(el.tag == f"{HTML_NS}img" and "alt" not in el.attrib for el in tree):
        expected.add("img_alt")
    if any(el.tag in controls for el in tree):
        expected.add("control_label")
    headings = [el for el in tree if el.tag in {f"{HTML_NS}h{level}" for level in range(1, 7)}]
    tops = [el for el in headings if el.tag == f"{HTML_NS}h1"]
    skips = any(
        int(later.tag[-1]) > int(earlier.tag[-1]) + 1
        for earlier, later in zip(headings, headings[1:], strict=False)
    )
    if len(tops) != 1 or skips:
        expected.add("heading_structure")
    rules = {f.rule for f in a11y_findings(source, require=ALL_RULES)}
    assert rules == expected, source
