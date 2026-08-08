"""Unit tests for static accessibility invariants (meta_harness.accessibility)."""

from __future__ import annotations

from meta_harness.accessibility import ALL_RULES, A11yFinding, a11y_findings


def _rules(findings: list[A11yFinding]) -> set[str]:
    return {f.rule for f in findings}


# A well-formed page: <html lang>, a titled head, every <img> carries alt.
CLEAN_PAGE = """\
<!DOCTYPE html>
<html lang="en">
  <head><title>Dashboard</title></head>
  <body>
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
    # both bare <img> are counted in the single finding's message
    assert any("2 <img>" in f.message for f in findings)


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
