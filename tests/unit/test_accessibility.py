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


def test_nothing_inside_a_template_is_judged_by_any_rule() -> None:
    # A <template> is a stamp, not a page: its text, href, alt and ids are supplied by
    # whatever clones it, so the source cannot tell an unfinished stamp from a finished
    # element. Every rule declines to judge it — the outline and the title always did,
    # and since PR #211's review so do the element rules, rather than half of them.
    html = '<template id="row"><input><a href=""><span></span></a><img src="x"></template>'
    assert a11y_findings(html, require=ALL_RULES) == []


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


def test_a_template_does_not_leak_out_of_itself() -> None:
    # Inert inside, but the elements around it are judged normally: an unbalanced
    # </template> must not re-open the document, and a real link after one is checked.
    assert a11y_findings('<template><a href="/docs">Docs</a></template>', require=LINK) == []
    after = '<template><input></template><a href="/x"></a>'
    assert _located(a11y_findings(after, require=LINK)) == [("link_text", 1)]


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


# --------------------------------------------------------------------------
# A name may be contributed by a descendant (the icon-link idiom) — PR #211
# --------------------------------------------------------------------------


def test_icon_link_is_named_by_a_descendants_aria_label() -> None:
    # The commonest icon-link idiom there is; assistive tech announces "Twitter".
    svg = '<a href="/tw"><svg role="img" aria-label="Twitter"></svg></a>'
    span = '<a href="/tw"><span aria-label="Twitter"></span></a>'
    assert a11y_findings(svg, require=LINK) == []
    assert a11y_findings(span, require=LINK) == []


def test_icon_link_is_named_by_an_svg_title() -> None:
    assert a11y_findings('<a href="/tw"><svg><title>Twitter</title></svg></a>', require=LINK) == []


def test_icon_link_is_named_by_a_descendants_aria_labelledby() -> None:
    html = '<span id="t">Twitter</span><a href="/tw"><svg aria-labelledby="t"></svg></a>'
    assert a11y_findings(html, require=LINK) == []


def test_icon_link_with_nothing_to_announce_is_still_flagged() -> None:
    # The whole point of crediting descendants is that it must not credit *nothing*.
    assert _located(a11y_findings('<a href="/tw"><svg role="img"></svg></a>', require=LINK)) == [
        ("link_text", 1)
    ]
    dangling = '<a href="/tw"><svg aria-labelledby="gone"></svg></a>'
    assert _located(a11y_findings(dangling, require=LINK)) == [("link_text", 1)]


# --------------------------------------------------------------------------
# Names are resolved, not merely present — PR #211
# --------------------------------------------------------------------------


def test_aria_labelledby_pointing_at_an_empty_element_names_nothing() -> None:
    empty = '<span id="lbl"></span><input aria-labelledby="lbl">'
    blank = '<span id="lbl">   </span><input aria-labelledby="lbl">'
    assert _located(a11y_findings(empty, require=CONTROL)) == [("control_label", 1)]
    assert _located(a11y_findings(blank, require=CONTROL)) == [("control_label", 1)]


def test_aria_labelledby_resolves_when_any_referenced_element_has_text() -> None:
    html = '<span id="a"></span><span id="b">Search</span><input aria-labelledby="a b">'
    assert a11y_findings(html, require=CONTROL) == []


def test_a_referenced_element_may_be_named_by_its_own_aria_label() -> None:
    html = '<span id="lbl" aria-label="Search"></span><input aria-labelledby="lbl">'
    assert a11y_findings(html, require=CONTROL) == []


def test_a_reference_is_not_chased_through_a_second_reference() -> None:
    # One level of indirection, as the accessible-name algorithm allows: an element
    # named only by its *own* aria-labelledby cannot lend that name onward.
    html = '<span id="deep">Search</span><span id="lbl" aria-labelledby="deep"></span>'
    assert _located(a11y_findings(html + '<input aria-labelledby="lbl">', require=CONTROL)) == [
        ("control_label", 1)
    ]


def test_a_label_with_no_text_names_nothing() -> None:
    # Structure is not a name: both of these announce exactly nothing.
    assert _located(a11y_findings("<label><input></label>", require=CONTROL)) == [
        ("control_label", 1)
    ]
    assert _located(a11y_findings('<label for="q"> </label><input id="q">', require=CONTROL)) == [
        ("control_label", 1)
    ]


def test_a_label_whose_only_content_is_an_image_names_the_control() -> None:
    wrapping = '<label><img src="s.svg" alt="Search"><input></label>'
    associated = '<label for="q"><img src="s.svg" alt="Search"></label><input id="q">'
    assert a11y_findings(wrapping, require=CONTROL) == []
    assert a11y_findings(associated, require=CONTROL) == []


def test_a_label_named_by_a_reference_names_the_control() -> None:
    html = '<span id="t">Search</span><label aria-labelledby="t"><input></label>'
    assert a11y_findings(html, require=CONTROL) == []


# --------------------------------------------------------------------------
# Foreign content: inside <svg>/<math> a familiar tag is not an HTML element
# --------------------------------------------------------------------------


def test_an_svg_title_does_not_satisfy_the_documents_title() -> None:
    # It names an icon. A page with no <head><title> is still untitled.
    html = '<html lang="en"><body><svg><title>Twitter icon</title></svg></body></html>'
    assert _located(a11y_findings(html)) == [("page_title", None)]


def test_a_real_title_is_unaffected_by_an_svg_title_elsewhere() -> None:
    html = (
        '<html lang="en"><head><title>Home</title></head>'
        "<body><svg><title>Twitter icon</title></svg></body></html>"
    )
    assert a11y_findings(html) == []


def test_headings_break_out_of_foreign_content_and_are_real_headings() -> None:
    # h1-h6 are in the parsing spec's breakout list (verified against html5lib): a
    # browser hoists <svg><h1> out into a genuine HTML heading, so it is the page's.
    assert a11y_findings(DOC.format("<svg><h1>Real</h1></svg>"), require=HEADING) == []
    assert a11y_findings(DOC.format("<math><h1>Real</h1></math>"), require=HEADING) == []
    # ...which also means a second one really is a duplicate.
    duplicate = DOC.format("<h1>Real</h1><svg><h1>Also</h1></svg>")
    assert _located(a11y_findings(duplicate, require=HEADING)) == [("heading_structure", 1)]


def test_a_breakout_tag_closes_the_whole_foreign_subtree() -> None:
    # The <svg> is popped, not just the heading: everything after it is HTML again.
    # So this <title> is the document's title, and this <input> is a real control.
    titled = '<html lang="en"><body><svg><h1>Real</h1><title>Home</title></svg></body></html>'
    assert a11y_findings(titled) == []
    control = '<html lang="en"><body><svg><h1>Real</h1><input></svg></body></html>'
    assert _rules(a11y_findings(control, require=CONTROL)) == {"control_label"}


def test_a_heading_in_an_html_integration_point_is_a_real_heading() -> None:
    # <foreignObject> resumes HTML inside SVG — a different route to the same answer.
    inside = DOC.format("<svg><foreignObject><h1>Real</h1></foreignObject></svg>")
    assert a11y_findings(inside, require=HEADING) == []


def test_a_control_inside_svg_is_not_a_form_control() -> None:
    assert a11y_findings("<svg><input></svg>", require=CONTROL) == []
    # ...but one in an HTML integration point is.
    inside = "<svg><foreignObject><input></foreignObject></svg>"
    assert _located(a11y_findings(inside, require=CONTROL)) == [("control_label", 1)]


# --------------------------------------------------------------------------
# Element-stack robustness (the name scopes are a real nesting stack)
# --------------------------------------------------------------------------


def test_an_unclosed_child_does_not_leak_text_past_its_parent() -> None:
    # </a> closes the <span> left open inside it; the text after the link is not the
    # link's, and the link itself is still named by what it did contain.
    html = '<a href="/docs"><span>Docs</a> and more'
    assert a11y_findings(html, require=LINK) == []


def test_an_unclosed_void_element_cannot_swallow_the_rest_of_the_document() -> None:
    # <input>/<img> never have content, so a following label must not be credited to
    # them, and the second control is still judged on its own.
    html = '<label>Name <input id="a"></label><input id="b">'
    assert _located(a11y_findings(html, require=CONTROL)) == [("control_label", 1)]


def test_a_void_element_closes_at_once_and_cannot_adopt_later_text() -> None:
    # <input> has no content, so the text that follows it is not its name. If it were
    # left open, the label written *after* an input would silently name it.
    html = '<input id="lbl"><span>Search</span><input aria-labelledby="lbl">'
    assert _located(a11y_findings(html, require=CONTROL)) == [
        ("control_label", 1),
        ("control_label", 1),
    ]


def test_closing_a_parent_also_closes_what_was_left_open_inside_it() -> None:
    # The <span> is never closed, so </a> has to end it as well. Left open, it would go
    # on collecting the text written after the link — and lend that name to a control
    # that references it, which is not what a browser would announce.
    unclosed = '<a href="/x">Docs<span id="lbl"></a> Search<input aria-labelledby="lbl">'
    assert _located(a11y_findings(unclosed, require=CONTROL)) == [("control_label", 1)]
    # ...while a span that really does contain the text still names it.
    named = '<a href="/x"><span id="lbl">Search</span></a><input aria-labelledby="lbl">'
    assert a11y_findings(named, require=CONTROL) == []


def test_an_svg_link_is_still_a_link_and_its_title_names_it() -> None:
    # SVG has its own <a href>, and it is a genuine link — deliberately not excluded
    # along with the tag names that mean something else inside a foreign subtree.
    assert _located(a11y_findings("<svg><a href='/x'></a></svg>", require=LINK)) == [
        ("link_text", 1)
    ]
    assert a11y_findings("<svg><a href='/x'><title>Home</title></a></svg>", require=LINK) == []


def test_an_image_inside_svg_still_needs_an_alt() -> None:
    # <img> breaks out of foreign content into HTML, so it really is an HTML image.
    assert _rules(a11y_findings("<svg><img src=a></svg>", require=("img_alt",))) == {"img_alt"}


def test_a_controls_own_content_is_its_value_not_its_name() -> None:
    # A <select>'s options and a <textarea>'s content are what the user *chose*, never
    # a label — crediting them would silently bless every unlabelled dropdown.
    assert _located(a11y_findings("<select><option>Blue</option></select>", require=CONTROL)) == [
        ("control_label", 1)
    ]
    assert _located(a11y_findings("<textarea>hello</textarea>", require=CONTROL)) == [
        ("control_label", 1)
    ]


def test_a_label_inside_svg_is_not_an_html_label() -> None:
    # <label> is not in the breakout list (html5lib confirms it stays in the SVG
    # namespace), so it labels nothing — by for= or by wrapping.
    associated = '<svg><label for="q">Name</label></svg><input id="q">'
    assert _located(a11y_findings(associated, require=CONTROL)) == [("control_label", 1)]
    wrapping = "<svg><label><foreignObject><input></foreignObject></label></svg>"
    assert _located(a11y_findings(wrapping, require=CONTROL)) == [("control_label", 1)]


# --------------------------------------------------------------------------
# Correct markup this used to fail — the PR #211 adversarial review
# --------------------------------------------------------------------------


def test_an_integration_point_only_resumes_html_in_its_own_namespace() -> None:
    # <desc>/<title>/<foreignObject> are SVG's; <mtext> and friends are MathML's.
    # Testing the union made <svg><mtext><input> a form control, which no browser agrees
    # with — and, in the other direction, let <math><desc><title> pass for the page's.
    assert a11y_findings("<svg><mtext><input></mtext></svg>", require=CONTROL) == []
    assert a11y_findings("<math><desc><input></desc></math>", require=CONTROL) == []
    assert _located(a11y_findings("<math><mtext><input></mtext></math>", require=CONTROL)) == [
        ("control_label", 1)
    ]
    assert _located(a11y_findings("<svg><desc><input></desc></svg>", require=CONTROL)) == [
        ("control_label", 1)
    ]


def test_a_foreign_subtree_keeps_its_language_rather_than_reading_the_tag_name() -> None:
    # html5lib confirms the <svg> inside a <math> is a *MathML* element, so the <desc>
    # in it is MathML's `desc`, not SVG's integration point. Walking up to the nearest
    # <svg>/<math> tag name would get this backwards.
    assert a11y_findings("<math><svg><desc><input></desc></svg></math>", require=CONTROL) == []
    assert a11y_findings("<svg><math><mtext><input></mtext></math></svg>", require=CONTROL) == []
    resumed = "<svg><foreignObject><math><mtext><input></mtext></math></foreignObject></svg>"
    assert _located(a11y_findings(resumed, require=CONTROL)) == [("control_label", 1)]


def test_a_foreign_title_past_the_wrong_integration_point_is_not_the_pages_title() -> None:
    # The same defect read through a default-gated rule: a <title> that is still foreign
    # must not silence page_title.
    icon = '<html lang="en"><body><h1>H</h1><math><desc><title>Icon</title></desc></math>'
    assert _located(a11y_findings(icon)) == [("page_title", None)]
    real = '<html lang="en"><body><h1>H</h1><svg><desc><title>Real</title></desc></svg>'
    assert a11y_findings(real) == []


def test_an_annotation_xml_encoding_is_matched_whole_and_untrimmed() -> None:
    # The spec asks for an ASCII case-insensitive match of the *whole* value. Trimming
    # it made a padded encoding an integration point, where a browser keeps MathML.
    padded = '<math><annotation-xml encoding=" text/html "><input></annotation-xml></math>'
    assert a11y_findings(padded, require=CONTROL) == []
    upper = '<math><annotation-xml encoding="TEXT/HTML"><input></annotation-xml></math>'
    assert _located(a11y_findings(upper, require=CONTROL)) == [("control_label", 1)]


def test_markup_shown_inside_a_textarea_is_a_string_not_elements() -> None:
    # "Paste your markup here" is correct markup that renders correctly, and the gate
    # used to fail it on a *default* rule. html.parser only knows script/style are raw
    # text; the HTML tokenizer says textarea/title/iframe/xmp/noembed/noframes/plaintext
    # are too.
    page = '<html lang="en"><head><title>Snippets</title></head><body><h1>Demo</h1>{}</body>'
    assert a11y_findings(page.format('<textarea><img src="cat.png"></textarea>')) == []
    assert (
        a11y_findings(page.format("<textarea><h1>Example</h1></textarea>"), require=HEADING) == []
    )
    assert a11y_findings(page.format('<iframe><img src="x"></iframe>')) == []
    assert a11y_findings(page.format('<xmp><img src="x"></xmp>')) == []


def test_a_text_only_element_ends_at_its_own_end_tag_and_nothing_else() -> None:
    # An end tag written inside one is text too, so it must not close an outer element:
    # </a> inside the textarea leaves the link open to collect the text after it.
    assert a11y_findings('<a href="/x"><textarea></a></textarea>Docs</a>', require=LINK) == []
    # ...and the element's own end tag does end it.
    assert _located(a11y_findings('<textarea>v</textarea><a href="/x"></a>', require=LINK)) == [
        ("link_text", 1)
    ]


def test_plaintext_runs_to_the_end_of_the_file() -> None:
    # No end tag closes it, so everything after one is text a browser shows verbatim.
    page = '<html lang="en"><head><title>T</title></head><body><h1>H</h1>{}</body></html>'
    assert a11y_findings(page.format('<plaintext></plaintext><img src="x">')) == []


def test_a_script_inside_an_svg_is_markup_the_way_a_browser_reads_it() -> None:
    # <script>/<style> are raw text only in the HTML namespace. Entering CDATA anyway
    # lost the hoisted heading and, with no end tag to return at, swallowed the rest of
    # the document — inventing "no <h1>" on a page that has one.
    page = '<html lang="en"><head><title>T</title></head><body><h1>Real</h1>{}</body></html>'
    assert _located(
        a11y_findings(page.format("<math><style><h1>Hoisted</h1>"), require=HEADING)
    ) == [("heading_structure", 1)]
    assert a11y_findings(page.format("<script><h1>Not markup</h1></script>"), require=HEADING) == []


def test_a_link_named_only_by_its_title_attribute_is_named() -> None:
    # HTML-AAM's last-resort name source, which axe-core's `link-name` accepts. An icon
    # link carrying title="RSS feed" is conformant markup and must not be flagged.
    assert a11y_findings('<a href="/rss" title="RSS feed"><i></i></a>', require=LINK) == []
    assert _located(a11y_findings('<a href="/rss" title=" "><i></i></a>', require=LINK)) == [
        ("link_text", 1)
    ]
    # A control's `title` is still not a label — a tooltip never reaches a touch user.
    assert _located(a11y_findings('<input title="Search">', require=CONTROL)) == [
        ("control_label", 1)
    ]


def test_nothing_hidden_from_assistive_tech_is_judged() -> None:
    # `hidden` and `aria-hidden` remove the element *and its subtree* from the tree a
    # screen reader is given, so a real a11y tool does not judge what is inside one.
    skip = '<a href="#main" aria-hidden="true" tabindex="-1"><span class="chev"></span></a>'
    assert a11y_findings(skip, require=LINK) == []
    assert a11y_findings('<div hidden><input type="text"></div>', require=CONTROL) == []
    assert a11y_findings('<div aria-hidden="TRUE"><a href="/x"></a></div>', require=LINK) == []
    # ...and everything else still is.
    assert _located(a11y_findings('<div aria-hidden="false"><input></div>', require=CONTROL)) == [
        ("control_label", 1)
    ]
    assert _located(a11y_findings('<div><a href="/x"></a></div>', require=LINK)) == [
        ("link_text", 1)
    ]


def test_a_self_closing_html_element_does_not_close_itself() -> None:
    # The HTML parsing spec acknowledges the self-closing flag only in foreign content
    # and ignores it on HTML elements, so the text after <a href="/x" /> is the link's.
    assert a11y_findings('<a href="/x" />Read the docs</a>', require=LINK) == []
    assert a11y_findings('<label for="q"/>Name<input id="q">', require=CONTROL) == []
    assert _located(a11y_findings('<a href="/x" />', require=LINK)) == [("link_text", 1)]
    # In foreign content the flag *is* meaningful, so the SVG link really is empty.
    assert _located(a11y_findings('<svg><a href="/x"/>text</svg>', require=LINK)) == [
        ("link_text", 1)
    ]


def test_void_elements_close_before_the_text_that_follows_them() -> None:
    # Observable through a name reference: a void element cannot contain the text
    # written after it, so `aria-labelledby` pointing at one resolves to nothing.
    for tag in ("keygen", "basefont", "bgsound", "col", "img"):
        html = f'<input aria-labelledby="k"><{tag} id="k">Following text'
        assert _located(a11y_findings(html, require=CONTROL)) == [("control_label", 1)], tag
    # A non-void element in the same shape does hold the text, and does name the control.
    assert a11y_findings('<input aria-labelledby="k"><span id="k">Text', require=CONTROL) == []


def test_a_script_still_gets_the_parsers_own_raw_text_handling() -> None:
    # `html.parser` reads a <script>'s source more carefully than re-tokenizing it
    # would: the legacy `// <!--` idiom must not swallow the rest of the document.
    page = '<html lang="en"><head><title>T</title></head><body><h1>H</h1>{}</body></html>'
    legacy = page.format('<script>// <!-- legacy</script><img src="x">')
    assert _rules(a11y_findings(legacy)) == {"img_alt"}


def test_a_script_written_inside_a_textarea_does_not_eat_the_textarea() -> None:
    # There are no elements inside a <textarea>, only text — so nothing in there puts
    # the parser into raw-text mode and loses the </textarea> that ends it.
    html = '<a href="/x"><textarea><script></textarea>Docs</a>'
    assert a11y_findings(html, require=LINK) == []
