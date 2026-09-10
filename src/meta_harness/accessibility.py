"""Static accessibility (a11y) invariants for HTML — the Product/UX archetype slice.

A product's UX carries invariants no code check sees. This gates the *high-confidence,
deterministic* accessibility facts derivable from static HTML — the kind a screen-reader
user is blocked by and that need no rendering to detect.

Gated by default (matrix rows U1–U3):

- ``html_lang`` — a full document's ``<html>`` must declare a ``lang`` (WCAG 3.1.1);
  a screen reader can't pick a voice/pronunciation without it.
- ``img_alt`` — every ``<img>`` must carry an ``alt`` attribute (WCAG 1.1.1); empty
  ``alt=""`` is allowed for decorative images, but the attribute must be present.
- ``page_title`` — a full document must have a non-empty ``<title>`` (WCAG 2.4.2).

Available but **opt-in**, because a shipped frontend usually has a backlog against each
and a gate nobody can turn on governs nothing (rows U4–U6, ADR-0075):

- ``control_label`` — every labelable form control has an accessible name: a wrapping
  or ``for=``-associated ``<label>``, an ``aria-label``, or an ``aria-labelledby``
  naming an id that exists (WCAG 3.3.2, 4.1.2).
- ``link_text`` — every ``<a href>`` has discernible text, an ``aria-label``/
  ``aria-labelledby``, or an ``<img alt="...">`` inside it (WCAG 2.4.4).
- ``heading_structure`` — a full document has exactly one ``<h1>``, and no heading
  skips a level on the way down (WCAG 1.3.1).

Deliberately low-false-positive (presence facts only) — contrast ratios, keyboard
reachability, focus visibility and target size are properties of the *rendered* page,
not of the source, and belong to a real a11y tool (axe-core) on an opt-in heavy lane
(issue #210), not to a deterministic static gate. Threshold-free: no arbitrary score
target. Rules that presuppose a full page (``html_lang``, ``page_title``, the
one-``<h1>`` half of ``heading_structure``) apply only when an ``<html>`` tag is
present, so HTML *fragments* (components, partials) don't trip them. stdlib
``html.parser`` only; no dependency. The parse is a single fact-gathering pass and each
rule is a pure function of those facts, so adding a rule cannot perturb another.

The tree is read the way a browser would build it, not the way the text looks:
duplicate attributes resolve **first-wins** (the HTML parsing spec), ``<script>`` and
``<style>`` content is source rather than text, and ``<template>`` content is inert —
scanned on its own terms, but never the outline, the document title, or an enclosing
link's name. See docs/specs/SPEC-accessibility.md, ADR-0045 and ADR-0075.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from html.parser import HTMLParser

#: The rules a project gets without asking — the U1–U3 presence facts (ADR-0045).
DEFAULT_RULES: tuple[str, ...] = ("html_lang", "img_alt", "page_title")

#: Every a11y rule this module knows, in reporting order. The three beyond
#: :data:`DEFAULT_RULES` are opt-in per project via ``[a11y].require`` (ADR-0075).
ALL_RULES: tuple[str, ...] = (
    *DEFAULT_RULES,
    "control_label",
    "link_text",
    "heading_structure",
)

#: Form controls that need an accessible name (``<button>`` is named by its content).
_CONTROL_TAGS: frozenset[str] = frozenset({"input", "select", "textarea"})

#: ``<input type>`` values exempt from ``control_label``: they take their name from
#: ``value``/``alt``, or are never exposed to the user at all.
_SELF_NAMING_INPUT_TYPES: frozenset[str] = frozenset(
    {"hidden", "submit", "button", "reset", "image"}
)

#: Elements whose content is source code, not text anyone reads or hears.
_RAW_TEXT_TAGS: frozenset[str] = frozenset({"script", "style"})

#: Heading tag → outline level.
_HEADING_LEVELS: dict[str, int] = {f"h{level}": level for level in range(1, 7)}


@dataclass(frozen=True)
class A11yFinding:
    """A single accessibility violation: the rule, a human-facing reason, and where.

    ``line`` is the 1-based source line of the offending element, or ``None`` when the
    violation is an *absence* (no ``<title>``, no ``<h1>``) or an aggregate count, which
    have no single location. A finding never invents a line it does not know.
    """

    rule: str
    message: str
    line: int | None = None


@dataclass(frozen=True)
class _Control:
    """A labelable form control and the naming evidence carried on the element."""

    tag: str
    type_: str
    line: int
    control_id: str
    aria_label: str
    labelledby: tuple[str, ...]
    wrapped_in_label: bool


@dataclass
class _Link:
    """An ``<a href>`` and the naming evidence gathered while it is open."""

    line: int
    aria_label: str
    labelledby: tuple[str, ...]
    template_depth: int = 0
    text: str = ""
    has_img_alt: bool = False


@dataclass(frozen=True)
class _Heading:
    """One heading in the document outline."""

    level: int
    line: int


@dataclass
class _Facts:
    """The presence facts an a11y ruling needs, gathered from one HTML document."""

    has_html: bool = False
    html_line: int = 0
    html_has_lang: bool = False
    imgs_missing_alt: int = 0
    title_text: str = ""
    ids: set[str] = field(default_factory=set)
    label_targets: set[str] = field(default_factory=set)
    controls: list[_Control] = field(default_factory=list)
    links: list[_Link] = field(default_factory=list)
    headings: list[_Heading] = field(default_factory=list)


def _attr_map(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
    """Attributes as a lower-cased name → value map — **first occurrence wins**.

    ``html.parser`` reports duplicate attributes verbatim; the HTML parsing spec (and
    every browser) keeps the *first* and drops the rest, so
    ``<input type="hidden" type="text">`` really is a hidden input. Matching the DOM
    here keeps the type exemption and the id/``for=`` matching honest in both
    directions — last-wins would both invent and miss violations. A valueless
    attribute (``<img alt>``) maps to the empty string, so presence is still visible.
    """
    values: dict[str, str] = {}
    for name, value in attrs:
        values.setdefault(name.lower(), value or "")
    return values


def _id_tokens(value: str) -> tuple[str, ...]:
    """Split an id-reference list (``aria-labelledby``) into its whitespace-separated ids."""
    return tuple(value.split())


class _Collector(HTMLParser):
    """Gathers a11y-relevant presence facts from an HTML document (lenient parse)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.facts = _Facts()
        self._in_title = False
        self._label_depth = 0
        self._template_depth = 0
        self._rawtext_depth = 0
        self._open_links: list[_Link] = []
        self._starters: dict[str, Callable[[str, dict[str, str]], None]] = {
            "html": self._start_html,
            "title": self._start_title,
            "img": self._start_img,
            "a": self._start_anchor,
            "label": self._start_label,
            "template": self._start_template,
            **dict.fromkeys(_RAW_TEXT_TAGS, self._start_rawtext),
            **dict.fromkeys(_CONTROL_TAGS, self._start_control),
            **dict.fromkeys(_HEADING_LEVELS, self._start_heading),
        }
        self._enders: dict[str, Callable[[], None]] = {
            "title": self._end_title,
            "a": self._end_anchor,
            "label": self._end_label,
            "template": self._end_template,
            **dict.fromkeys(_RAW_TEXT_TAGS, self._end_rawtext),
        }

    # -- parser callbacks --------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Record any ``id`` this element defines, then dispatch to its rule collector."""
        values = _attr_map(attrs)
        element_id = values.get("id", "").strip()
        if element_id:
            self.facts.ids.add(element_id)
        starter = self._starters.get(tag)
        if starter is not None:
            starter(tag, values)

    def handle_endtag(self, tag: str) -> None:
        """Close whichever nesting context this end tag ends, if any."""
        ender = self._enders.get(tag)
        if ender is not None:
            ender()

    def handle_data(self, data: str) -> None:
        """Route rendered text to the ``<title>`` and to the links it belongs to."""
        if self._rawtext_depth:
            return  # <script>/<style> source is not text the user or a reader sees
        if self._in_title:
            self.facts.title_text += data
        for link in self._live_links():
            link.text += data

    def _live_links(self) -> Iterator[_Link]:
        """The open links that content here actually belongs to.

        Content inside a ``<template>`` nested *within* a link never renders in place,
        so it cannot give that link its name; a link that is itself inside a template
        sits at the same depth as its own content and collects it normally.
        """
        return (link for link in self._open_links if link.template_depth == self._template_depth)

    # -- per-element collectors -------------------------------------------
    def _start_html(self, tag: str, values: dict[str, str]) -> None:
        self.facts.has_html = True
        self.facts.html_line = self.getpos()[0]
        self.facts.html_has_lang = bool(values.get("lang", "").strip())

    def _start_title(self, tag: str, values: dict[str, str]) -> None:
        if self._template_depth:
            return  # inert until cloned — not this document's title
        self._in_title = True

    def _end_title(self) -> None:
        self._in_title = False

    def _start_img(self, tag: str, values: dict[str, str]) -> None:
        if "alt" not in values:
            self.facts.imgs_missing_alt += 1
        elif values["alt"].strip():
            for link in self._live_links():
                link.has_img_alt = True

    def _start_anchor(self, tag: str, values: dict[str, str]) -> None:
        if "href" not in values:
            return  # a named target, not a link
        link = _Link(
            line=self.getpos()[0],
            aria_label=values.get("aria-label", ""),
            labelledby=_id_tokens(values.get("aria-labelledby", "")),
            template_depth=self._template_depth,
        )
        self.facts.links.append(link)  # document order, evaluated even if never closed
        self._open_links.append(link)

    def _end_anchor(self) -> None:
        if self._open_links:
            self._open_links.pop()

    def _start_label(self, tag: str, values: dict[str, str]) -> None:
        self._label_depth += 1
        target = values.get("for", "").strip()
        if target:
            self.facts.label_targets.add(target)

    def _end_label(self) -> None:
        self._label_depth = max(0, self._label_depth - 1)

    def _start_template(self, tag: str, values: dict[str, str]) -> None:
        self._template_depth += 1

    def _end_template(self) -> None:
        self._template_depth = max(0, self._template_depth - 1)

    def _start_rawtext(self, tag: str, values: dict[str, str]) -> None:
        self._rawtext_depth += 1

    def _end_rawtext(self) -> None:
        self._rawtext_depth = max(0, self._rawtext_depth - 1)

    def _start_heading(self, tag: str, values: dict[str, str]) -> None:
        if self._template_depth:
            return  # inert until cloned — not part of this document's outline
        self.facts.headings.append(_Heading(_HEADING_LEVELS[tag], self.getpos()[0]))

    def _start_control(self, tag: str, values: dict[str, str]) -> None:
        self.facts.controls.append(
            _Control(
                tag=tag,
                type_=values.get("type", "").strip().lower(),
                line=self.getpos()[0],
                control_id=values.get("id", "").strip(),
                aria_label=values.get("aria-label", ""),
                labelledby=_id_tokens(values.get("aria-labelledby", "")),
                wrapped_in_label=self._label_depth > 0,
            )
        )


def _facts(html: str) -> _Facts:
    """Parse ``html`` and return the gathered a11y presence facts."""
    collector = _Collector()
    collector.feed(html)
    collector.close()
    return collector.facts


def _has_aria_name(aria_label: str, labelledby: Sequence[str], ids: set[str]) -> bool:
    """True when ARIA supplies a name: a non-empty label, or a reference that resolves.

    A dangling ``aria-labelledby`` names nothing, so it does not count.
    """
    return bool(aria_label.strip()) or any(ref in ids for ref in labelledby)


def _html_lang_findings(facts: _Facts) -> list[A11yFinding]:
    """WCAG 3.1.1 — a full document declares the language it is written in."""
    if not facts.has_html or facts.html_has_lang:
        return []
    return [
        A11yFinding(
            "html_lang",
            '<html> has no lang attribute — set <html lang="..."> so assistive '
            "tech can pronounce the page (WCAG 3.1.1).",
            facts.html_line,
        )
    ]


def _img_alt_findings(facts: _Facts) -> list[A11yFinding]:
    """WCAG 1.1.1 — every image carries a text alternative (``alt=""`` if decorative)."""
    if not facts.imgs_missing_alt:
        return []
    return [
        A11yFinding(
            "img_alt",
            f"{facts.imgs_missing_alt} <img> without an alt attribute — add "
            'alt="..." (or alt="" for decorative) so the image has a text '
            "alternative (WCAG 1.1.1).",
        )
    ]


def _page_title_findings(facts: _Facts) -> list[A11yFinding]:
    """WCAG 2.4.2 — a full document is identifiable by a non-empty title."""
    if not facts.has_html or facts.title_text.strip():
        return []
    return [
        A11yFinding(
            "page_title",
            "document has no non-empty <title> — add a descriptive <title> so the "
            "page is identifiable (WCAG 2.4.2).",
        )
    ]


def _describe_control(control: _Control) -> str:
    """Render a control as it appears in the source, e.g. ``<input type="email">``."""
    if control.type_:
        return f'<{control.tag} type="{control.type_}">'
    return f"<{control.tag}>"


def _control_is_named(control: _Control, facts: _Facts) -> bool:
    """True when the control has an accessible name from a label or from ARIA."""
    return (
        control.wrapped_in_label
        or control.control_id in facts.label_targets
        or _has_aria_name(control.aria_label, control.labelledby, facts.ids)
    )


def _control_needs_name(control: _Control) -> bool:
    """False for input types named by their own value/alt, or never exposed."""
    return control.tag != "input" or control.type_ not in _SELF_NAMING_INPUT_TYPES


def _control_label_findings(facts: _Facts) -> list[A11yFinding]:
    """WCAG 3.3.2 / 4.1.2 — every labelable form control has an accessible name."""
    return [
        A11yFinding(
            "control_label",
            f"{_describe_control(control)} has no accessible name — wrap it in a "
            "<label>, point a <label for=...> at its id, or give it a non-empty "
            "aria-label / an aria-labelledby naming an id that exists "
            "(WCAG 3.3.2, 4.1.2).",
            control.line,
        )
        for control in facts.controls
        if _control_needs_name(control) and not _control_is_named(control, facts)
    ]


def _link_is_discernible(link: _Link, facts: _Facts) -> bool:
    """True when the link has text, an image alternative, or an ARIA name."""
    return (
        bool(link.text.strip())
        or link.has_img_alt
        or _has_aria_name(link.aria_label, link.labelledby, facts.ids)
    )


def _link_text_findings(facts: _Facts) -> list[A11yFinding]:
    """WCAG 2.4.4 — every link has discernible text.

    Whether that text is *meaningful* ("click here") is a judgement about context, not
    a fact about the document, so it is deliberately not gated here.
    """
    return [
        A11yFinding(
            "link_text",
            "<a href> has no discernible text — give the link text, a non-empty "
            'aria-label/aria-labelledby, or an <img alt="..."> inside it, so its '
            "purpose is announced (WCAG 2.4.4).",
            link.line,
        )
        for link in facts.links
        if not _link_is_discernible(link, facts)
    ]


def _extra_h1_findings(headings: Sequence[_Heading]) -> list[A11yFinding]:
    """Every ``<h1>`` after the first: a document has one top-level heading."""
    return [
        A11yFinding(
            "heading_structure",
            "a further <h1> — the document already has a top-level heading; use "
            "<h2>...<h6> for sections so the outline is unambiguous (WCAG 1.3.1).",
            heading.line,
        )
        for heading in [h for h in headings if h.level == 1][1:]
    ]


def _skipped_level_findings(headings: Sequence[_Heading]) -> list[A11yFinding]:
    """Any heading that descends more than one level below the heading before it."""
    return [
        A11yFinding(
            "heading_structure",
            f"heading level skips from <h{previous.level}> to <h{current.level}> — "
            "do not skip levels; the outline is how a screen reader navigates the "
            "page (WCAG 1.3.1).",
            current.line,
        )
        for previous, current in zip(headings, headings[1:], strict=False)
        if current.level > previous.level + 1
    ]


def _heading_structure_findings(facts: _Facts) -> list[A11yFinding]:
    """WCAG 1.3.1 — exactly one ``<h1>`` per document, and no skipped levels."""
    findings: list[A11yFinding] = []
    if facts.has_html and not any(h.level == 1 for h in facts.headings):
        findings.append(
            A11yFinding(
                "heading_structure",
                "document has no <h1> — give the page exactly one top-level heading "
                "naming what it is (WCAG 1.3.1).",
            )
        )
    findings.extend(_extra_h1_findings(facts.headings))
    findings.extend(_skipped_level_findings(facts.headings))
    return findings


#: Rule name → the pure predicate over the parsed facts that reports its violations.
_RULE_CHECKS: dict[str, Callable[[_Facts], list[A11yFinding]]] = {
    "html_lang": _html_lang_findings,
    "img_alt": _img_alt_findings,
    "page_title": _page_title_findings,
    "control_label": _control_label_findings,
    "link_text": _link_text_findings,
    "heading_structure": _heading_structure_findings,
}


def a11y_findings(
    html: str,
    *,
    require: Sequence[str] = DEFAULT_RULES,
) -> list[A11yFinding]:
    """Return the accessibility violations in one HTML document for the enforced rules.

    ``require`` selects which rules apply (default: :data:`DEFAULT_RULES` — the three
    rules gated without opt-in; the rest of :data:`ALL_RULES` are named explicitly by a
    project that has adopted them). Document-level rules apply only to a *full document*
    (one containing an ``<html>`` tag), so fragments are never falsely flagged.
    Findings are reported rule by rule in :data:`ALL_RULES` order and, within a rule, in
    document order. Deterministic and threshold-free; unknown rule names are ignored.
    """
    enforced = set(require)
    facts = _facts(html)
    findings: list[A11yFinding] = []
    for rule in ALL_RULES:
        if rule in enforced:
            findings.extend(_RULE_CHECKS[rule](facts))
    return findings
