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
  or ``for=``-associated ``<label>`` that has text, an ``aria-label``, or an
  ``aria-labelledby`` naming an element that has one (WCAG 3.3.2, 4.1.2).
- ``link_text`` — every ``<a href>`` has discernible text, from its own content or from
  a named descendant (``<img alt>``, ``aria-label``, an ``<svg><title>``) (WCAG 2.4.4).
- ``heading_structure`` — a full document has exactly one ``<h1>``, and no heading
  skips a level on the way down (WCAG 1.3.1).

Deliberately low-false-positive — contrast ratios, keyboard reachability, focus
visibility and target size are properties of the *rendered* page, not of the source, and
belong to a real a11y tool (axe-core) on an opt-in heavy lane (issue #210), not to a
deterministic static gate. Threshold-free: no arbitrary score target. Rules that
presuppose a full page (``html_lang``, ``page_title``, the "has an ``<h1>``" half of
``heading_structure``) apply only when an ``<html>`` tag is present, so HTML *fragments*
(components, partials) don't trip them. stdlib ``html.parser`` only; no dependency.

The tree is read the way a browser would build it, not the way the text looks:
duplicate attributes resolve **first-wins** (the HTML parsing spec); ``<script>`` and
``<style>`` content is source rather than text; ``<template>`` content is inert — scanned
on its own terms, but never the outline, the document title, or an enclosing link's name;
and inside an ``<svg>``/``<math>`` subtree a familiar tag name is **not** an HTML element
(an ``<svg><title>`` names an icon, not the page), until an HTML integration point such
as ``<foreignObject>`` resumes HTML.

Names are **resolved, not merely present**: every element accumulates the text of its own
subtree plus the names contributed by descendants, so a reference or a wrapping
``<label>`` that resolves to *nothing* names nothing. The parse is a single
fact-gathering pass; each rule is then a pure function of those facts, so adding a rule
cannot perturb another. See docs/specs/SPEC-accessibility.md, ADR-0045 and ADR-0075.
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

#: Elements that never have content: they close the moment they open, so an unclosed
#: one can't swallow the rest of the document.
_VOID_TAGS: frozenset[str] = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)

#: Roots of a foreign subtree: inside one, an HTML tag name is not an HTML element.
_FOREIGN_ROOT_TAGS: frozenset[str] = frozenset({"svg", "math"})

#: Where HTML resumes inside a foreign subtree (the HTML parsing spec's integration
#: points). Tag names arrive lower-cased, so ``<foreignObject>`` is ``foreignobject``.
_HTML_INTEGRATION_TAGS: frozenset[str] = frozenset(
    {"foreignobject", "desc", "title", "annotation-xml", "mtext", "mi", "mo", "mn", "ms"}
)

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


@dataclass
class _NameScope:
    """The accessible-name evidence accumulating for one element's subtree.

    ``text`` is everything that would be announced from this element's content: its
    descendants' text, the ``alt`` of images inside it, and the ``aria-label`` of any
    descendant. ``refs`` are the ``aria-labelledby`` ids found on it or on a descendant,
    resolved after the parse (an id can be defined later in the document).
    """

    tag: str
    line: int
    template_depth: int
    text: str = ""
    refs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _Control:
    """A labelable form control and the naming evidence carried on the element.

    Its own subtree text is deliberately *not* naming evidence: a ``<select>``'s
    ``<option>``s and a ``<textarea>``'s content are the value, never the label.
    """

    tag: str
    type_: str
    line: int
    control_id: str
    aria_label: str
    labelledby: tuple[str, ...]
    wrapping_label: _NameScope | None


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
    id_scopes: dict[str, _NameScope] = field(default_factory=dict)
    label_targets: dict[str, _NameScope] = field(default_factory=dict)
    named_ids: set[str] = field(default_factory=set)
    controls: list[_Control] = field(default_factory=list)
    links: list[_NameScope] = field(default_factory=list)
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
        self._scopes: list[_NameScope] = []
        self._open_tags: dict[str, int] = {}
        self._starters: dict[str, Callable[[str, dict[str, str]], None]] = {
            "html": self._start_html,
            "title": self._start_title,
            "img": self._start_img,
            "a": self._start_anchor,
            "label": self._start_label,
            **dict.fromkeys(_CONTROL_TAGS, self._start_control),
            **dict.fromkeys(_HEADING_LEVELS, self._start_heading),
        }

    # -- parser callbacks --------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Open this element's name scope, credit its own naming attributes, dispatch."""
        values = _attr_map(attrs)
        self._push(tag, values)
        starter = self._starters.get(tag)
        if starter is not None:
            starter(tag, values)
        if tag in _VOID_TAGS:
            self._pop_to(tag)  # no content to accumulate; never left hanging open

    def handle_endtag(self, tag: str) -> None:
        """Close the innermost matching element, and anything left open inside it."""
        if tag == "title":
            self._in_title = False
        self._pop_to(tag)

    def handle_data(self, data: str) -> None:
        """Route rendered text to the ``<title>`` and to the elements it names."""
        if self._in_raw_text():
            return  # <script>/<style> source is not text the user or a reader sees
        if self._in_title:
            self.facts.title_text += data
        for scope in self._live_scopes():
            scope.text += data

    # -- element stack -----------------------------------------------------
    def _push(self, tag: str, values: dict[str, str]) -> None:
        """Start a name scope for this element and record the id it may be known by."""
        depth = self._open_tags.get("template", 0)
        if tag == "template":
            depth += 1  # the template's own content sits one level in
        scope = _NameScope(tag=tag, line=self.getpos()[0], template_depth=depth)
        self._scopes.append(scope)
        self._open_tags[tag] = self._open_tags.get(tag, 0) + 1
        element_id = values.get("id", "").strip()
        if element_id:
            self.facts.id_scopes.setdefault(element_id, scope)  # first id wins, as in the DOM
        self._credit_aria(values)

    def _pop_to(self, tag: str) -> None:
        """Close the innermost open ``tag``; a stray end tag closes nothing."""
        for index in range(len(self._scopes) - 1, -1, -1):
            if self._scopes[index].tag != tag:
                continue
            for scope in self._scopes[index:]:
                self._open_tags[scope.tag] -= 1
            del self._scopes[index:]
            return

    def _live_scopes(self) -> Iterator[_NameScope]:
        """The open elements that content here actually contributes a name to.

        Content inside a ``<template>`` nested *within* an element never renders in
        place, so it cannot name it; an element inside a template sits at the same depth
        as its own content and accumulates it normally.
        """
        depth = self._open_tags.get("template", 0)
        return (scope for scope in self._scopes if scope.template_depth == depth)

    def _in_raw_text(self) -> bool:
        """True inside ``<script>``/``<style>``, whose content is source, not text."""
        return any(self._open_tags.get(tag, 0) for tag in _RAW_TEXT_TAGS)

    def _in_foreign_content(self) -> bool:
        """True when the element being started is *not* an HTML element.

        Inside an ``<svg>``/``<math>`` subtree a familiar tag name belongs to that
        language — an ``<svg><title>`` names an icon and an ``<svg><h1>`` is not a
        heading — until an HTML integration point (``<foreignObject>``, ``<desc>``,
        ``<mtext>``, …) resumes HTML. Ancestors only: the element's own scope is
        already on the stack when its collector runs.
        """
        for scope in reversed(self._scopes[:-1]):
            if scope.tag in _HTML_INTEGRATION_TAGS:
                return False
            if scope.tag in _FOREIGN_ROOT_TAGS:
                return True
        return False

    def _wrapping_label(self) -> _NameScope | None:
        """The innermost ``<label>`` this element is nested inside, if any."""
        for scope in reversed(self._scopes):
            if scope.tag == "label":
                return scope
        return None

    def _credit_aria(self, values: dict[str, str]) -> None:
        """Credit this element's own ARIA naming attributes to it and its ancestors.

        A named descendant contributes to the name of the element containing it — which
        is what makes ``<a href><svg role="img" aria-label="Twitter"></svg></a>`` a
        named link, the commonest icon-link idiom there is.
        """
        label = values.get("aria-label", "").strip()
        refs = _id_tokens(values.get("aria-labelledby", ""))
        if not label and not refs:
            return
        for scope in self._live_scopes():
            scope.text += f" {label}"
            scope.refs.extend(refs)

    # -- per-element collectors -------------------------------------------
    def _start_html(self, tag: str, values: dict[str, str]) -> None:
        self.facts.has_html = True
        self.facts.html_line = self.getpos()[0]
        self.facts.html_has_lang = bool(values.get("lang", "").strip())

    def _start_title(self, tag: str, values: dict[str, str]) -> None:
        if self._open_tags.get("template", 0):
            return  # inert until cloned — not this document's title
        if self._in_foreign_content():
            return  # an <svg>/<math> <title> names an icon, not the page
        self._in_title = True

    def _start_img(self, tag: str, values: dict[str, str]) -> None:
        if "alt" not in values:
            self.facts.imgs_missing_alt += 1
            return
        alt = values["alt"].strip()
        if alt:
            for scope in self._live_scopes():
                scope.text += f" {alt}"

    def _start_anchor(self, tag: str, values: dict[str, str]) -> None:
        if "href" in values:  # an <a> without one is a named target, not a link
            self.facts.links.append(self._scopes[-1])

    def _start_label(self, tag: str, values: dict[str, str]) -> None:
        target = values.get("for", "").strip()
        if target:
            self.facts.label_targets.setdefault(target, self._scopes[-1])

    def _start_heading(self, tag: str, values: dict[str, str]) -> None:
        if self._open_tags.get("template", 0) or self._in_foreign_content():
            return  # inert, or not an HTML heading at all
        self.facts.headings.append(_Heading(_HEADING_LEVELS[tag], self.getpos()[0]))

    def _start_control(self, tag: str, values: dict[str, str]) -> None:
        if self._in_foreign_content():
            return  # an <svg><input> is an SVG element, not a form control
        self.facts.controls.append(
            _Control(
                tag=tag,
                type_=values.get("type", "").strip().lower(),
                line=self.getpos()[0],
                control_id=values.get("id", "").strip(),
                aria_label=values.get("aria-label", ""),
                labelledby=_id_tokens(values.get("aria-labelledby", "")),
                wrapping_label=self._wrapping_label(),
            )
        )


def _facts(html: str) -> _Facts:
    """Parse ``html``, then resolve which ids actually name something."""
    collector = _Collector()
    collector.feed(html)
    collector.close()
    facts = collector.facts
    # One level of indirection, as the accessible-name algorithm allows: an element
    # named only by its *own* aria-labelledby cannot lend that name onward.
    facts.named_ids = {name for name, scope in facts.id_scopes.items() if scope.text.strip()}
    return facts


def _scope_has_name(scope: _NameScope, named_ids: set[str]) -> bool:
    """True when this element's subtree yields a non-empty accessible name."""
    return bool(scope.text.strip()) or any(ref in named_ids for ref in scope.refs)


def _has_aria_name(aria_label: str, labelledby: Sequence[str], named_ids: set[str]) -> bool:
    """True when ARIA supplies a name: a non-empty label, or a reference that resolves.

    A dangling ``aria-labelledby``, or one pointing at an element with no text of its
    own, names nothing — so neither counts.
    """
    return bool(aria_label.strip()) or any(ref in named_ids for ref in labelledby)


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


def _labelled_by_element(control: _Control, facts: _Facts) -> bool:
    """True when a ``<label>`` that actually says something names this control.

    Structure alone is not a name: ``<label><input></label>`` and
    ``<label for="q"></label>`` announce nothing at all.
    """
    for label in (control.wrapping_label, facts.label_targets.get(control.control_id)):
        if label is not None and _scope_has_name(label, facts.named_ids):
            return True
    return False


def _control_is_named(control: _Control, facts: _Facts) -> bool:
    """True when the control has an accessible name from a label or from ARIA."""
    return _labelled_by_element(control, facts) or _has_aria_name(
        control.aria_label, control.labelledby, facts.named_ids
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
            "<label> that has text, point a <label for=...> at its id, or give it a "
            "non-empty aria-label / an aria-labelledby naming an element that has a "
            "name (WCAG 3.3.2, 4.1.2).",
            control.line,
        )
        for control in facts.controls
        if _control_needs_name(control) and not _control_is_named(control, facts)
    ]


def _link_text_findings(facts: _Facts) -> list[A11yFinding]:
    """WCAG 2.4.4 — every link has discernible text.

    Whether that text is *meaningful* ("click here") is a judgement about context, not
    a fact about the document, so it is deliberately not gated here.
    """
    return [
        A11yFinding(
            "link_text",
            "<a href> has no discernible text — give the link text, a non-empty "
            "aria-label/aria-labelledby, or a named child such as an "
            '<img alt="..."> or an <svg> with a <title>, so its purpose is '
            "announced (WCAG 2.4.4).",
            link.line,
        )
        for link in facts.links
        if not _scope_has_name(link, facts.named_ids)
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
