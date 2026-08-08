"""Static accessibility (a11y) invariants for HTML — the Product/UX archetype slice.

A product's UX carries invariants no code check sees. This gates the *high-confidence,
deterministic* accessibility facts derivable from static HTML — the kind a screen-reader
user is blocked by and that need no rendering to detect:

- ``html_lang`` — a full document's ``<html>`` must declare a ``lang`` (WCAG 3.1.1);
  a screen reader can't pick a voice/pronunciation without it.
- ``img_alt`` — every ``<img>`` must carry an ``alt`` attribute (WCAG 1.1.1); empty
  ``alt=""`` is allowed for decorative images, but the attribute must be present.
- ``page_title`` — a full document must have a non-empty ``<title>`` (WCAG 2.4.2).

Deliberately low-false-positive (presence facts only) — contrast ratios, ARIA
correctness, and focus order need a rendered DOM and belong to a real a11y tool
(axe-core) on the heavy lane, not a deterministic static gate. Threshold-free: no
arbitrary score target. Rules that presuppose a full page (``html_lang``,
``page_title``) apply only when an ``<html>`` tag is present, so HTML *fragments*
(components, partials) don't trip them. stdlib ``html.parser`` only; no dependency.
See docs/specs/SPEC-accessibility.md and ADR-0045.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from html.parser import HTMLParser

#: Every a11y rule this module knows. The default enforced set is all three.
ALL_RULES: tuple[str, ...] = ("html_lang", "img_alt", "page_title")


@dataclass(frozen=True)
class A11yFinding:
    """A single accessibility violation: which rule failed and a human-facing reason."""

    rule: str
    message: str


@dataclass
class _Facts:
    """The presence facts an a11y ruling needs, gathered from one HTML document."""

    has_html: bool = False
    html_has_lang: bool = False
    imgs_missing_alt: int = 0
    title_text: str = ""


class _Collector(HTMLParser):
    """Gathers a11y-relevant presence facts from an HTML document (lenient parse)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.facts = _Facts()
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        names = {name.lower() for name, _ in attrs}
        values = {name.lower(): (value or "") for name, value in attrs}
        if tag == "html":
            self.facts.has_html = True
            self.facts.html_has_lang = bool(values.get("lang", "").strip())
        elif tag == "img" and "alt" not in names:
            self.facts.imgs_missing_alt += 1
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.facts.title_text += data


def _facts(html: str) -> _Facts:
    """Parse ``html`` and return the gathered a11y presence facts."""
    collector = _Collector()
    collector.feed(html)
    collector.close()
    return collector.facts


def a11y_findings(
    html: str,
    *,
    require: Sequence[str] = ALL_RULES,
) -> list[A11yFinding]:
    """Return the accessibility violations in one HTML document for the enforced rules.

    ``require`` selects which rules apply (default: all of :data:`ALL_RULES`).
    ``html_lang`` and ``page_title`` apply only to a *full document* (one containing
    an ``<html>`` tag), so fragments are never falsely flagged. ``img_alt`` applies
    to any ``<img>`` anywhere. Deterministic and threshold-free; unknown rule names
    are ignored.
    """
    enforced = set(require)
    facts = _facts(html)
    findings: list[A11yFinding] = []

    if "html_lang" in enforced and facts.has_html and not facts.html_has_lang:
        findings.append(
            A11yFinding(
                "html_lang",
                '<html> has no lang attribute — set <html lang="..."> so assistive '
                "tech can pronounce the page (WCAG 3.1.1).",
            )
        )
    if "img_alt" in enforced and facts.imgs_missing_alt:
        findings.append(
            A11yFinding(
                "img_alt",
                f"{facts.imgs_missing_alt} <img> without an alt attribute — add "
                'alt="..." (or alt="" for decorative) so the image has a text '
                "alternative (WCAG 1.1.1).",
            )
        )
    if "page_title" in enforced and facts.has_html and not facts.title_text.strip():
        findings.append(
            A11yFinding(
                "page_title",
                "document has no non-empty <title> — add a descriptive <title> so the "
                "page is identifiable (WCAG 2.4.2).",
            )
        )
    return findings
