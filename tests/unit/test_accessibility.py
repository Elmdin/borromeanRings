"""Unit tests for static accessibility invariants (meta_harness.accessibility)."""

from __future__ import annotations

from meta_harness.accessibility import (
    ALL_RULES,
    DEFAULT_RULES,
    A11yFinding,
    a11y_findings,
)


def _rules(findings: list[A11yFinding]) -> set[str]:
    return {f.rule for f in findings}


def _located(findings: list[A11yFinding]) -> list[tuple[str, int | None]]:
    """Exact (rule, line) pairs, in the order reported."""
    return [(f.rule, f.line) for f in findings]


# A well-formed page: <html lang>, a titled head, every <img> carries alt, one <h1>
# with no skipped levels, a labelled control and a link with text — clean under
# *every* rule this module knows, not only the default set.
CLEAN_PAGE = """\
<!DOCTYPE html>
<html lang="en">
  <head><title>Dashboard</title></head>
  <body>
    <h1>Dashboard</h1>
    <h2>Recent</h2>
    <label for="q">Search</label><input id="q">
    <a href="/help">Help</a>
    <img src="logo.svg" alt="Acme logo">
    <img src="divider.svg" alt="">
  </body>
</html>
"""


def test_clean_page_has_no_findings() -> None:
    assert a11y_findings(CLEAN_PAGE) == []


def test_html_without_lang_is_flagged() -> None:
    findings = a11y_findings("<html><head><title>x</title></head></html>")
    assert "html_lang" in _rules(findings)
    assert any("3.1.1" in f.message for f in findings)


def test_empty_or_whitespace_lang_counts_as_missing() -> None:
    assert "html_lang" in _rules(
        a11y_findings('<html lang=""><head><title>x</title></head></html>')
    )
    assert "html_lang" in _rules(
        a11y_findings('<html lang="   "><head><title>x</title></head></html>')
    )


def test_img_without_alt_is_flagged_and_counted() -> None:
    html = '<html lang="en"><head><title>x</title></head><body><img src=a><img src=b></body></html>'
    findings = a11y_findings(html)
    assert "img_alt" in _rules(findings)
    # both bare <img> are counted in the single finding's message (and the count is
    # exactly 2 — "in" alone would also accept a nonsense "-2 <img>")
    assert any(f.message.startswith("2 <img> without an alt") for f in findings)


def test_empty_alt_attribute_is_accepted() -> None:
    # alt="" is the correct marking for a decorative image — present, so not flagged.
    html = '<html lang="en"><head><title>x</title></head><body><img src=a alt=""></body></html>'
    assert "img_alt" not in _rules(a11y_findings(html))


def test_missing_and_whitespace_title_are_flagged() -> None:
    assert "page_title" in _rules(a11y_findings('<html lang="en"><head></head></html>'))
    assert "page_title" in _rules(
        a11y_findings('<html lang="en"><head><title>   </title></head></html>')
    )


def test_fragment_without_html_tag_is_not_flagged_for_document_rules() -> None:
    # A component/partial has no <html> and no <title>; those rules must not fire.
    fragment = "<section><h2>Widget</h2><p>hello</p></section>"
    assert a11y_findings(fragment) == []


def test_fragment_still_flags_missing_img_alt() -> None:
    # img_alt applies anywhere, even in a fragment with no <html>.
    assert "img_alt" in _rules(a11y_findings("<div><img src=hero.png></div>"))


def test_require_narrows_the_enforced_rule_set() -> None:
    # A bare <img> in a full doc missing lang + title: enforce only img_alt.
    bad = "<html><body><img src=a></body></html>"
    findings = a11y_findings(bad, require=("img_alt",))
    assert _rules(findings) == {"img_alt"}


def test_single_rule_on_a_clean_page_yields_nothing() -> None:
    # Exercises the "rule enforced, no violation" path for each rule alone.
    for rule in ALL_RULES:
        assert a11y_findings(CLEAN_PAGE, require=(rule,)) == []


def test_case_insensitive_tags_and_attributes() -> None:
    html = '<HTML LANG="en"><HEAD><TITLE>x</TITLE></HEAD><BODY><IMG SRC=a ALT="y"></BODY></HTML>'
    assert a11y_findings(html) == []


def test_rule_registry_separates_the_default_set_from_the_opt_in_rules() -> None:
    # The three new rules exist but are NOT gated by default: a shipped frontend has a
    # backlog against each, so a project adopts them one at a time (ADR-0075).
    assert DEFAULT_RULES == ("html_lang", "img_alt", "page_title")
    assert ALL_RULES == (
        "html_lang",
        "img_alt",
        "page_title",
        "control_label",
        "link_text",
        "heading_structure",
    )
    # A page violating every opt-in rule is silent under the default require set.
    bad = '<html lang="en"><head><title>x</title></head><body><input><a href="/"></a></body></html>'
    assert a11y_findings(bad) == []


def test_html_lang_finding_carries_the_line_of_the_html_tag() -> None:
    findings = a11y_findings("<!DOCTYPE html>\n<html>\n<head><title>x</title></head>\n</html>")
    assert _located(findings) == [("html_lang", 2)]


def test_absence_findings_have_no_line() -> None:
    # <title> that is missing has no source location — the finding must not invent one.
    findings = a11y_findings('<html lang="en"><head></head></html>')
    assert _located(findings) == [("page_title", None)]


# --------------------------------------------------------------------------
# control_label (U4) — WCAG 2.2 SC 3.3.2, 4.1.2
# --------------------------------------------------------------------------

CONTROL = ("control_label",)


def test_unlabelled_control_is_flagged_with_its_line_and_citation() -> None:
    html = '<form>\n  <input type="email">\n</form>'
    findings = a11y_findings(html, require=CONTROL)
    assert _located(findings) == [("control_label", 2)]
    message = findings[0].message
    assert '<input type="email">' in message
    assert "3.3.2" in message and "4.1.2" in message


def test_select_and_textarea_need_a_name_too() -> None:
    html = "<select></select>\n<textarea></textarea>"
    assert _located(a11y_findings(html, require=CONTROL)) == [
        ("control_label", 1),
        ("control_label", 2),
    ]
    assert "<textarea>" in a11y_findings("<textarea></textarea>", require=CONTROL)[0].message


def test_wrapping_label_names_the_control() -> None:
    assert a11y_findings("<label>Name <input></label>", require=CONTROL) == []


def test_label_association_by_for_works_in_either_document_order() -> None:
    before = '<label for="q">Search</label><input id="q">'
    after = '<input id="q"><label for="q">Search</label>'
    assert a11y_findings(before, require=CONTROL) == []
    assert a11y_findings(after, require=CONTROL) == []


def test_label_for_pointing_at_a_different_control_does_not_name_this_one() -> None:
    html = '<label for="other">Search</label><input id="q">'
    assert _located(a11y_findings(html, require=CONTROL)) == [("control_label", 1)]


def test_control_outside_a_closed_label_is_not_treated_as_wrapped() -> None:
    html = "<label>Name <input id=a></label>\n<input id=b>"
    assert _located(a11y_findings(html, require=CONTROL)) == [("control_label", 2)]


def test_stray_end_label_cannot_mask_a_later_wrapping_label() -> None:
    # An unbalanced </label> must not drive the nesting depth negative — the next
    # genuinely wrapped control would then be reported as unlabelled.
    assert a11y_findings("</label><label>Name <input></label>", require=CONTROL) == []


def test_aria_label_names_the_control_but_whitespace_does_not() -> None:
    assert a11y_findings('<input aria-label="Search">', require=CONTROL) == []
    assert _located(a11y_findings('<input aria-label="  ">', require=CONTROL)) == [
        ("control_label", 1)
    ]


def test_aria_labelledby_must_point_at_an_id_that_exists() -> None:
    resolves = '<span id="lbl">Search</span><input aria-labelledby="lbl">'
    dangling = '<input aria-labelledby="missing">'
    assert a11y_findings(resolves, require=CONTROL) == []
    assert _located(a11y_findings(dangling, require=CONTROL)) == [("control_label", 1)]


def test_aria_labelledby_resolves_if_any_referenced_id_exists() -> None:
    html = '<span id="lbl">Search</span><input aria-labelledby="gone lbl">'
    assert a11y_findings(html, require=CONTROL) == []


def test_input_types_that_carry_their_own_name_are_exempt() -> None:
    exempt = "".join(
        f'<input type="{kind}">' for kind in ("hidden", "submit", "button", "reset", "image")
    )
    assert a11y_findings(exempt, require=CONTROL) == []
    # ...but a text input (explicit or defaulted) is not exempt.
    assert len(a11y_findings('<input type="text"><input>', require=CONTROL)) == 2


def test_input_type_matching_is_case_and_whitespace_insensitive() -> None:
    assert a11y_findings('<input type=" HIDDEN ">', require=CONTROL) == []


# --------------------------------------------------------------------------
# link_text (U5) — WCAG 2.2 SC 2.4.4
# --------------------------------------------------------------------------

LINK = ("link_text",)


def test_empty_link_is_flagged_with_its_line_and_citation() -> None:
    findings = a11y_findings('<p>hi</p>\n<a href="/docs"></a>', require=LINK)
    assert _located(findings) == [("link_text", 2)]
    assert "2.4.4" in findings[0].message


def test_link_text_may_come_from_nested_elements() -> None:
    assert a11y_findings('<a href="/docs"><span>Docs</span></a>', require=LINK) == []


def test_whitespace_only_link_text_is_not_discernible() -> None:
    assert _located(a11y_findings('<a href="/docs">   </a>', require=LINK)) == [("link_text", 1)]


def test_image_inside_a_link_names_it_only_when_alt_is_non_empty() -> None:
    named = '<a href="/"><img src="home.svg" alt="Home"></a>'
    decorative = '<a href="/"><img src="home.svg" alt=""></a>'
    bare = '<a href="/"><img src="home.svg"></a>'
    assert a11y_findings(named, require=LINK) == []
    assert _located(a11y_findings(decorative, require=LINK)) == [("link_text", 1)]
    assert _located(a11y_findings(bare, require=LINK)) == [("link_text", 1)]


def test_image_alt_outside_the_link_does_not_name_it() -> None:
    html = '<img src="home.svg" alt="Home"><a href="/"></a>'
    assert _located(a11y_findings(html, require=LINK)) == [("link_text", 1)]


def test_aria_label_and_aria_labelledby_name_a_link() -> None:
    assert a11y_findings('<a href="/" aria-label="Home"></a>', require=LINK) == []
    resolves = '<span id="t">Home</span><a href="/" aria-labelledby="t"></a>'
    dangling = '<a href="/" aria-labelledby="gone"></a>'
    assert a11y_findings(resolves, require=LINK) == []
    assert _located(a11y_findings(dangling, require=LINK)) == [("link_text", 1)]


def test_anchor_without_href_is_not_a_link() -> None:
    assert a11y_findings('<a name="top"></a>', require=LINK) == []
    # ...and its </a> must not disturb the tracking of a real link that follows.
    assert _located(a11y_findings('<a name="top"></a><a href="/"></a>', require=LINK)) == [
        ("link_text", 1)
    ]


def test_unclosed_link_is_still_evaluated() -> None:
    # A missing </a> must not turn a nameless link into a silent pass.
    assert _located(a11y_findings('<a href="/docs">', require=LINK)) == [("link_text", 1)]
    assert a11y_findings('<a href="/docs">Docs', require=LINK) == []


def test_links_are_reported_in_document_order() -> None:
    html = '<a href="/a"></a>\n<a href="/b">B</a>\n<a href="/c"></a>'
    assert _located(a11y_findings(html, require=LINK)) == [("link_text", 1), ("link_text", 3)]


# --------------------------------------------------------------------------
# heading_structure (U6) — WCAG 2.2 SC 1.3.1
# --------------------------------------------------------------------------

HEADING = ("heading_structure",)

DOC = '<html lang="en"><head><title>x</title></head><body>{}</body></html>'


def test_document_with_no_h1_is_flagged_without_a_line() -> None:
    findings = a11y_findings(DOC.format("<h2>Only</h2>"), require=HEADING)
    assert _located(findings) == [("heading_structure", None)]
    assert "1.3.1" in findings[0].message


def test_document_with_no_headings_at_all_is_flagged() -> None:
    assert _located(a11y_findings(DOC.format("<p>text</p>"), require=HEADING)) == [
        ("heading_structure", None)
    ]


def test_second_h1_is_flagged_at_its_own_line() -> None:
    html = '<html lang="en">\n<h1>One</h1>\n<h1>Two</h1>\n<h1>Three</h1>\n</html>'
    findings = a11y_findings(html, require=HEADING)
    assert _located(findings) == [("heading_structure", 3), ("heading_structure", 4)]


def test_skipped_level_is_flagged_at_the_heading_that_skips() -> None:
    html = '<html lang="en">\n<h1>One</h1>\n<h3>Three</h3>\n</html>'
    findings = a11y_findings(html, require=HEADING)
    assert _located(findings) == [("heading_structure", 3)]
    assert "<h1>" in findings[0].message and "<h3>" in findings[0].message


def test_descending_and_returning_levels_are_legal() -> None:
    body = "<h1>a</h1><h2>b</h2><h3>c</h3><h2>d</h2><h3>e</h3><h6>f</h6>"
    # h3 -> h6 skips; every other transition here is legal.
    assert _located(a11y_findings(DOC.format(body), require=HEADING)) == [("heading_structure", 1)]
    legal = "<h1>a</h1><h2>b</h2><h3>c</h3><h2>d</h2><h3>e</h3>"
    assert a11y_findings(DOC.format(legal), require=HEADING) == []


def test_heading_inside_a_template_does_not_count_as_the_documents_h1() -> None:
    html = DOC.format("<template><h1>Row title</h1></template><h2>Real</h2>")
    assert _located(a11y_findings(html, require=HEADING)) == [("heading_structure", None)]


def test_heading_inside_a_comment_does_not_count() -> None:
    html = DOC.format("<!-- <h1>commented out</h1> --><h2>Real</h2>")
    assert _located(a11y_findings(html, require=HEADING)) == [("heading_structure", None)]


def test_stray_end_template_cannot_hide_a_later_heading() -> None:
    # Unbalanced </template> must not drive the depth negative and swallow real headings.
    html = DOC.format("</template><h1>Real</h1>")
    assert a11y_findings(html, require=HEADING) == []


def test_controls_and_links_inside_a_template_are_still_checked() -> None:
    # Unlike the outline, a control's name and a link's text travel with the element.
    html = '<template><input><a href="/"></a></template>'
    assert _rules(a11y_findings(html, require=("control_label", "link_text"))) == {
        "control_label",
        "link_text",
    }


def test_fragment_heading_rules_check_only_the_deltas() -> None:
    # No <html> ⇒ the "exactly one <h1>" half cannot apply; a partial may start at h3.
    assert a11y_findings("<h3>a</h3><h4>b</h4>", require=HEADING) == []
    assert _located(a11y_findings("<h2>a</h2><h4>b</h4>", require=HEADING)) == [
        ("heading_structure", 1)
    ]
    # Two <h1> in a fragment is still one too many.
    assert _located(a11y_findings("<h1>a</h1><h1>b</h1>", require=HEADING)) == [
        ("heading_structure", 1)
    ]


def test_new_rules_are_case_insensitive() -> None:
    html = '<A HREF="/docs"></A><INPUT TYPE="TEXT"><H1>a</H1><H3>b</H3>'
    assert _rules(a11y_findings(html, require=ALL_RULES)) == {
        "control_label",
        "link_text",
        "heading_structure",
    }


def test_link_text_is_accumulated_across_every_chunk_not_overwritten() -> None:
    # Real markup delivers a link's text in several pieces, the last often whitespace.
    # Keeping only the last piece would report a perfectly good link as nameless.
    html = '<a href="/docs">\n  <span>Docs</span>\n</a>'
    assert a11y_findings(html, require=LINK) == []


def test_title_text_is_accumulated_across_every_chunk() -> None:
    # Same accumulation, for <title>: markup inside the title splits the text.
    html = '<html lang="en"><head><title>Home<span>   </span></title></head></html>'
    assert a11y_findings(html) == []


def test_nested_labels_track_depth_so_the_wrapper_still_names_a_control() -> None:
    # The inner </label> closes the inner label only — a control after it is still
    # wrapped by the outer one. Depth, not a flag.
    html = "<label>Name <label>hint</label><input></label>"
    assert a11y_findings(html, require=CONTROL) == []


def test_nested_templates_track_depth_so_inner_content_stays_out_of_the_outline() -> None:
    # The inner </template> must not re-open the document: the second <h1> is still
    # inside the outer template and is not this document's heading.
    html = DOC.format("<h1>Real</h1><template><template>x</template><h1>Row</h1></template>")
    assert a11y_findings(html, require=HEADING) == []


# --------------------------------------------------------------------------
# Parser fidelity: what the DOM would say, not what the text looks like
# --------------------------------------------------------------------------


def test_duplicate_attributes_resolve_the_way_a_browser_resolves_them() -> None:
    # The HTML parsing spec keeps the FIRST occurrence and drops the rest. Last-wins
    # would both invent violations and miss them:
    assert a11y_findings('<input type="hidden" type="text">', require=CONTROL) == []
    assert _located(a11y_findings('<input type="text" type="hidden">', require=CONTROL)) == [
        ("control_label", 1)
    ]
    named = '<label for="a">Name</label><input id="a" id="b">'
    assert a11y_findings(named, require=CONTROL) == []
    # ...and the same for the document rules that predate them.
    assert _rules(a11y_findings('<html lang="" lang="en"><title>x</title></html>')) == {"html_lang"}


def test_template_content_inside_a_link_does_not_name_it() -> None:
    # <template> children never render in place, so the anchor is visibly empty.
    assert _located(a11y_findings('<a href="/"><template>Home</template></a>', require=LINK)) == [
        ("link_text", 1)
    ]
    with_img = '<a href="/"><template><img src="h.svg" alt="Home"></template></a>'
    assert _located(a11y_findings(with_img, require=LINK)) == [("link_text", 1)]


def test_a_link_inside_a_template_still_collects_its_own_text() -> None:
    # The link and its content sit at the same depth — this one is fine.
    assert a11y_findings('<template><a href="/docs">Docs</a></template>', require=LINK) == []


def test_script_and_style_source_is_not_link_text() -> None:
    # html.parser hands raw <script>/<style> source to handle_data like any text; a
    # link whose only content is code renders empty and must be flagged.
    assert _located(a11y_findings('<a href="/"><script>go();</script></a>', require=LINK)) == [
        ("link_text", 1)
    ]
    assert _located(a11y_findings('<a href="/"><style>.a{}</style></a>', require=LINK)) == [
        ("link_text", 1)
    ]


def test_stray_end_script_cannot_swallow_the_text_that_follows() -> None:
    # An unbalanced </script> must not drive the raw-text depth negative.
    assert a11y_findings('</script><a href="/docs">Docs</a>', require=LINK) == []


def test_title_inside_a_template_is_not_the_documents_title() -> None:
    html = (
        '<html lang="en"><head></head><body><template><title>Ghost</title></template></body></html>'
    )
    assert _located(a11y_findings(html)) == [("page_title", None)]
