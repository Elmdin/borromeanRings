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

from meta_harness.accessibility import a11y_findings

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
]


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


#: Foreign contexts that do or do not resume HTML for their children. The module's
#: `<input>` decision must agree with where the tree builder actually puts the element.
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
]


@pytest.mark.parametrize("wrapper,label", INTEGRATION_CASES)
def test_form_controls_are_html_exactly_where_the_tree_builder_says(
    wrapper: str, label: str
) -> None:
    """`<input>` does not break out, so only an integration point makes it a control."""
    body = wrapper.format("<input>")
    source = f'<html lang="en"><head><title>t</title></head><body>{body}</body></html>'
    assert _module_saw_a_form_control(source) == _has_html_element(source, "input"), label


def test_an_svg_anchor_stays_in_the_svg_namespace_and_is_still_checked() -> None:
    """The one place the module deliberately departs from namespace classification.

    html5lib confirms an `<svg><a href>` is an SVG element, not an HTML one. It is still
    a link a user clicks and a screen reader announces, so `link_text` checks it anyway
    — a judgement about user-facing links, recorded in the SPEC, not a parsing claim.
    """
    source = '<svg><a href="/x"></a></svg>'
    assert not _has_html_element(source, "a")  # the parsing fact
    assert [f.rule for f in a11y_findings(source, require=("link_text",))] == ["link_text"]


def test_markup_inside_a_foreign_script_is_invisible_to_the_stdlib_tokenizer() -> None:
    """A known, deliberate departure — recorded here rather than left to be rediscovered.

    A `<script>`/`<style>` is a raw-text element only in the HTML namespace. html5lib
    therefore parses the *content* of an `<svg><script>` as markup, and an `<h1>` written
    there becomes a real heading. Python's `html.parser` switches to CDATA on any
    `script`/`style` start tag, namespace or not, so the module never receives that tag
    at all — it cannot see the heading, and no tree-level rule can recover it.

    Suppressing the text anyway is the better of the two errors: crediting raw JS/CSS
    source as an accessible name would be a false *positive* (a browser renders none of
    it), while this is a false negative confined to markup written inside an SVG script.
    """
    source = '<html lang="en"><head><title>T</title></head><body><h1>Real</h1>{}</body></html>'
    svg_script = source.format("<svg><script><h1>Hoisted</h1></script></svg>")
    # The tree builder sees two headings; one is hoisted out of the <svg>.
    assert sum(1 for el in _parse(svg_script).iter() if el.tag == f"{HTML_NS}h1") == 2
    # The module sees one, and so reports no duplicate. Documented in SPEC-accessibility.
    assert a11y_findings(svg_script, require=("heading_structure",)) == []
    # An HTML <script> is raw text for both, so there is no disagreement there.
    html_script = source.format("<script><h1>Not markup</h1></script>")
    assert sum(1 for el in _parse(html_script).iter() if el.tag == f"{HTML_NS}h1") == 1
    assert a11y_findings(html_script, require=("heading_structure",)) == []
