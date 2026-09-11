# ADR-0075 — Static a11y rules for labels, link text and heading structure (U4–U6)

**Status:** Accepted

## Context
ADR-0045 shipped the three static a11y presence facts of the Product/UX matrix
(`docs/matrices/06-product-ux.md`): `<html lang>` (U1), `<img alt>` (U2), `<title>`
(U3). The matrix routes six more rows to issue #159, and they split cleanly in two:

- **U4 form controls have an accessible label**, **U5 links have discernible text**,
  **U6 exactly one `<h1>` and no skipped levels** — all decidable from the source with
  the parser `15_a11y` already runs. Each is a yes/no fact with a WCAG success criterion
  and an axe-core rule id behind it.
- **U7 contrast**, **U8 keyboard reachability / visible focus**, **U9 target size**, and
  **U18 the axe-core violation ratchet** — none of which are properties of the HTML
  source at all. They are properties of the *rendered* page.

Three questions had to be answered before building.

**Is the existing parse honest enough for these rules?** `15_a11y` does **not** use
regular expressions — `meta_harness.accessibility` parses with the stdlib
`html.parser.HTMLParser`, and that is load-bearing here. A regex could approximate U1–U3
(single-element attribute presence), but it could not answer U4–U6 honestly: a wrapping
`<label>` is a *nesting* fact (which requires tracking open/close depth), `for=` and
`aria-labelledby` resolution needs the *set of ids in the whole document* (defined
before or after the reference), the heading rule needs the *ordered sequence* of
headings, and `<template>` and comment content must be excluded from that sequence —
none of which a regular language decides. So the rules stay on `html.parser`: one pass
that gathers facts, then a pure predicate per rule over those facts.

**Can these rules be turned on for everyone?** No. U1–U3 are cheap to satisfy; a shipped
frontend typically has a real backlog against U4–U6 (every icon-only link, every
placeholder-as-label). Making them default would break every governed frontend at once,
and a gate a project has to switch off governs nothing.

**Where does "click here" belong?** The matrix row U5 mentions a banned-phrase list. It
is not built. Whether "Read more" conveys purpose depends on its context (SC 2.4.4 is
*Link Purpose **In Context***) — that is a judgement, not a fact, and a deterministic
gate that enforced an opinion would be the wrong kind of authority. Empty is a fact;
vague is a review comment.

## Decision
Extend `15_a11y` and `meta_harness.accessibility` — **not** a second check — with three
rules, each **opt-in** via the existing `[a11y].require` list so a project adopts them
one at a time:

- **`control_label`** (WCAG 2.2 SC 3.3.2, 4.1.2; axe-core `label`) — `<select>`,
  `<textarea>` and `<input>` except `type` in `hidden|submit|button|reset|image` must
  have an accessible name: nested inside a `<label>` **that has a name**, targeted by a
  `<label for>` that has one, a non-empty `aria-label`, or an `aria-labelledby` naming
  **an element that has a name**. A dangling reference, an empty referenced element and
  a `<label>` with no text all name nothing and are violations. `placeholder` and
  `title` are **not** accepted (stricter than axe-core's `label` rule, deliberately: a
  hint that disappears on input, or a tooltip a touch user never sees, is not a label).
- **`link_text`** (SC 2.4.4; axe-core `link-name`) — every `<a href>` must have a
  non-empty **name from content**: its own text, or a name contributed by anything inside
  it — an `<img alt>`, an `aria-label`, an `aria-labelledby` that resolves, or an `<svg>`
  with a `<title>`. That is what makes the icon-link idiom
  `<a href="/tw"><svg role="img" aria-label="Twitter"></svg></a>` pass, as it must.
  `aria-labelledby` was not in #159's
  enumeration; it is accepted here because it is the same accessible-name computation as
  U4 and rejecting it would flag conformant markup — a widening that can only *reduce*
  false positives, recorded rather than silent. The #211 review added a second such
  widening for the same reason: a `title` attribute **on the `<a>` itself** names the
  link (HTML-AAM's last-resort source, which axe-core's `link-name` accepts), even though
  `title` is still refused for `control_label` — a tooltip is a poor label for a field
  the user must fill in, and often the only name a decorative icon link has.
- **`heading_structure`** (SC 1.3.1; axe-core `page-has-heading-one`, `heading-order`) —
  a **full document** has exactly one `<h1>` (zero and every extra are violations), and
  in any document or fragment no heading may descend more than one level below the
  heading before it. Headings inside `<template>` are excluded (inert until cloned, so
  not part of this outline); headings inside comments are not markup, and neither is an
  `<h1>` inside an `<svg>`/`<math>` subtree unless an HTML integration point has resumed
  HTML.

The defaults are unchanged: `[a11y].require` still defaults to
`["html_lang", "img_alt", "page_title"]` (`DEFAULT_RULES`), and `ALL_RULES` now
enumerates all six. `adopt`'s `RECOMMENDED` set is **unchanged** — `15_a11y` is not in
it and does not join it here; it stays an archetype check a UI project adds
deliberately. These rules change only what an adopting project *can* turn on.

Three **parser-fidelity** decisions came out of review, because these rules are only as
honest as the tree they read (the shipped presence facts barely noticed them; the new
rules turn on exemptions, id matching and text content, which do):

- **Duplicate attributes resolve first-wins**, as the HTML parsing spec and every
  browser do. `html.parser` reports each occurrence verbatim, and the obvious dict
  comprehension keeps the *last* — which would call `<input type="hidden" type="text">`
  a text input (a false positive) and `<input type="text" type="hidden">` exempt (a
  false negative). Both directions are now tested.
- **`<script>`/`<style>` content is source, not text.** `html.parser` delivers it
  through the same callback as prose, so `<a href="/"><script>go()</script></a>` looked
  like a named link while rendering completely empty.
- **`<template>` content is inert, for every rule.** It never renders in place, so it is
  not the outline, not the document `<title>`, and not a link's text. The first cut kept
  `control_label` and `link_text` *live* inside a template, on the grounds that a name
  travels with the element. The #211 review showed what that costs:
  `<template id="row"><li><a href=""><span></span></a></li></template>` — a placeholder
  whose text and `href` are filled in at clone time, which is precisely what templates
  are **for** — was flagged. A template is a stamp, not a page, and the source cannot
  tell an unfinished stamp from a finished element. So no rule judges what is inside one.
  The asymmetry is resolved by *narrowing*: one rule instead of two, and it can only
  reduce false positives. The cost — a genuinely missing `alt` inside a row template goes
  unreported — is stated in the SPEC rather than left implicit.
- **`hidden` and `aria-hidden="true"` remove an element and its subtree from the
  accessibility tree**, so `control_label` and `link_text` do not judge what is inside
  one; a real a11y tool does not either. `<a href="#main" aria-hidden="true"
  tabindex="-1"><span class="chev"></span></a>` is correct markup. The other four rules
  are unaffected: an `<img>` in a `hidden` panel still needs an `alt` for when it shows.
- **A text-only element's content is a string, not elements.** The tokenizer reads
  `<textarea>`, `<title>`, `<iframe>`, `<xmp>`, `<noembed>`, `<noframes>` and
  `<plaintext>` as raw text or RCDATA; `html.parser` knows this for `script`/`style`
  only. So `<textarea><img src="cat.png"></textarea>` — a "paste your markup here" box,
  correct markup that renders correctly — failed the **default** `img_alt` rule. That is
  a false positive on a default-gated rule, the one direction "the better of the two
  errors" never covered.
- **The self-closing flag means nothing on an HTML element.** The spec acknowledges it
  only in foreign content; `html.parser` closes every `<x/>`, which made
  `<a href="/x" />Read the docs</a>` an empty link. Verification of that fix found its
  own tail: `html.parser` skips its raw-text switch on the `/>` form too, so a
  `<script src="a.js"/>` that no longer self-closed stayed open to end of file and
  swallowed the document. An element whose content is text starts that run explicitly now.
- **`hidden`/`aria-hidden` is applied by every rule that judges rendered content**, the
  outline included. The first cut exempted `heading_structure`, arguing that dropping an
  element out of a *sequence* could invent a finding. Verification showed the argument
  inverted: `<h1><h2><div hidden><h3></div><h4>` and `<h1><h2><h4>` are the same document
  to a screen reader, and counting the hidden heading gave them opposite verdicts —
  **masking** a real skip rather than preventing an invented one. With the `<h3>` hidden,
  `h1 → h2 → h4` *is* the sequence the user navigates, which is why axe-core's
  `heading-order` reads the accessibility tree. Presence and duplication point the same
  way: a page whose only `<h1>` is hidden has no perceivable top-level heading, and a
  hidden `<h1>` cannot be the second of two (that one was an invented finding).
  `page_title` and `html_lang` stay out of it for a different reason than the one first
  given — a `<title>` and the `<html>` element are *document metadata*, never rendered
  content, so there is nothing for `hidden` to remove. The two-category boundary collapses
  into one rule, which is both simpler and the correct one.
- **`hidden` and `aria-hidden` are kept together here deliberately.** They are not the
  same thing — `aria-hidden` leaves the element rendered and focusable — but for rules
  that ask "is this in the accessibility tree" the answer is no for both. The place they
  part company is a fact this check does not carry: a focusable element inside an
  `aria-hidden` subtree is axe-core's `aria-hidden-focus`, about focus order, which needs
  the rendered lane (#210) and is disclosed rather than approximated.
- **MathML has no anchor.** The SVG `<a href>` departure is about links a user clicks;
  `<math><a href>` is not one, and is not checked.
- **Inside an `<svg>`/`<math>` subtree, a familiar tag name is usually not an HTML
  element** — an `<svg><title>` names an icon and must never satisfy the (default-on)
  `page_title` rule, and an `<svg><input>` is not a form control. But the parsing spec
  keeps a **breakout list** of tags a browser refuses to leave there: it closes the
  foreign element and parses them as HTML. `h1`–`h6` and `img` are both on it, so an
  `<svg><h1>` *is* the document's heading — and the breakout closes the whole subtree, so
  what follows is HTML too. HTML also resumes at an integration point (`<foreignObject>`,
  `<desc>`, the MathML text points, and `<annotation-xml>` only with an HTML `encoding`).
  One deliberate departure: an SVG `<a href>` stays in the SVG namespace and `link_text`
  checks it anyway — a judgement about user-facing links, not a classification claim.

**The namespace rules are derived from a real parser, not recited.** The first attempt at
the foreign-content model had no breakout list; the second suppressed headings, which is
the exact opposite of what a browser does; a third recitation of the list would have been
a coin flip. So `html5lib` (a spec-conformant HTML5 tree builder) is now a **dev-only test
oracle**: `tests/unit/test_accessibility_conformance.py` parses each fixture with both
html5lib and this module and requires them to agree on where every element lands, and it
*computes* the breakout list from html5lib and compares it with the one the module
implements. It is in the `dev` extra only and never imported by the harness — the gate
must keep running on the stdlib alone.

The #211 review showed the discipline had been applied to **one** list: `_RAW_TEXT_TAGS`
and `_VOID_TAGS` were still recited and unguarded — adding `iframe` to the void list
passed all 211 tests, and the raw-text list was the one that was actually wrong. Both are
now derived the same way, with a differential over adversarial documents on top. The same
review found the integration points tested as a **union** of the two namespaces, so
`<svg><mtext><input>` was a form control and `<math><desc><title>` passed for the page's
title: a point belongs to one language, and the language is *inherited* rather than read
off the nearest `<svg>`/`<math>` tag name (html5lib confirms the `<svg>` in `<math><svg>`
is a MathML element).

Where Python's tokenizer disagreed with a conformant one — it entered CDATA for an
`<svg><script>`, which a browser parses as markup — the departure was first disclosed and
then **fixed**, once the review showed it was not merely a missed violation: with no
`</script>` to return at, the rest of the document was swallowed and the check invented
"document has no `<h1>`" on a page that has one. `_Collector` overrides
`set_cdata_mode` so a foreign `<script>`/`<style>` stays in markup mode. That is a
deliberate reach into an implementation detail of `html.parser`, taken because the
alternative fails correct pages, and it is pinned against html5lib by the conformance
suite so a future Python that changes it fails the suite instead of drifting.

**A name is resolved, not merely present.** The first cut asked only whether a naming
*mechanism* was attached; a second review showed that answers the wrong question in both
directions. `<label><input></label>`, `<label for="q"></label>` and an `aria-labelledby`
pointing at an empty element all passed while announcing nothing (false negatives), and
`<a href="/tw"><svg role="img" aria-label="Twitter"></svg></a>` — the commonest icon-link
idiom there is — was flagged, because only `<img alt>` was credited from inside a link
(a false positive, and the kind that gets a rule switched off). So every element now
accumulates its **name from content**: the text of its subtree, plus the `alt` of images
and the `aria-label` of *any* descendant, plus `aria-labelledby` references resolved
after the parse (an id may be defined later). A reference is followed one level, the
limit the accessible-name algorithm itself imposes. A control is the exception that
proves the rule: its own content is its *value*, never its name.

`id` resolution stays deliberately **document-wide**: a reference that only resolves
across a `<template>` boundary is accepted. Modelling template/shadow scope is a DOM
job, and the failure mode of not doing it is a missed violation, never an invented one.

Findings gained a `line`, and the check now reports
`file:line — [rule] — what is wrong`, with the WCAG SC in the message. A finding that
reports an *absence* (no `<title>`, no `<h1>`) or a count (`img_alt`) prints without a
line rather than inventing one.

**U7, U8, U9 and U18 are specified, not built** — see SPEC-accessibility.md
§"Not built: needs a rendered DOM" and follow-up issue **#210**. Contrast needs computed
colours after the cascade and compositing; keyboard reachability and focus visibility
need the resolved focus order and the `:focus-visible` styles that actually paint; target
size is a layout box in CSS pixels; the U18 ratchet needs axe-core running inside a page.
Approximating any of them from source text produces false positives, and a fail-closed
gate that cries wolf gets switched off. No browser or renderer was installed to explore
this: the reasoning is from the specifications, which is all it needs.

## Alternatives considered
- **A new check (`16_a11y_forms` or similar)** — rejected. One HTML corpus, one parse,
  one config surface, one receipt; a second check would double the discovery, the
  fail-closed git handling and the `noop` semantics, and would let the two drift.
- **Turn the three rules on by default** — rejected, as above: un-adoptable for existing
  frontends. `[a11y].require` already existed for exactly this.
- **A banned-phrase list for link text ("click here", "read more")** — rejected. It is a
  judgement about context, not a fact about the document; SC 2.4.4 is explicitly *in
  context*. Recorded in the SPEC as a human/T2 concern.
- **Accept `placeholder`/`title` as a control's name (axe-core's tolerance)** — rejected.
  Both are known-poor name sources; accepting them would let the gate bless the exact
  pattern it exists to catch. The cost is a knowingly stricter rule, which is why the
  rule is opt-in and the SPEC says so.
- **Report only the first violation per file** — rejected. Every offending element gets
  its own `file:line`; an a11y backlog is worked element by element.
- **Regex over the HTML instead of the parser** — rejected (see Context): nesting, the
  document-wide id set, heading order and `<template>` exclusion are not regular. The
  check already parses, so this cost nothing.
- **Build the rendered lane now (axe-core/pa11y/Playwright)** — rejected here. It needs
  an install surface this task explicitly could not create, and its design questions
  (which runner, how to be `noop` when absent, how to pin the version) deserve their own
  ADR. Filed as #210 with acceptance criteria instead of half-built.

## Consequences
- (+) A governed frontend can gate the three a11y defects that most often reach
  production: an unlabelled field, an icon-only link, a heading outline a screen-reader
  user cannot navigate. Each finding names the file, the line, the rule and the WCAG SC.
- (+) Adoption is incremental and honest: a project turns on one rule, clears its
  backlog, turns on the next. Nothing changes for projects that do not opt in.
- (+) The unbuilt rows are on the record with the reason they are unbuilt, not silently
  missing — the same discipline as ADR-0049's `noop`.
- (−) `control_label` is stricter than axe-core (no `placeholder`/`title`), so a project
  can see findings a browser extension would not report. Deliberate, documented, opt-in.
- (−) Static analysis still sees the source, not the page: JS-injected content, framework
  output and runtime-computed names are invisible. A generated site should scan its build
  output (drop `dist`/`build` from `[a11y].exclude`) or wait for #210.
- (−) The name model is a deliberate subset of the accessible-name algorithm: no roles,
  no CSS-generated content, no shadow DOM, `title`/`placeholder` rejected on purpose, and
  references followed one level. It answers "is there a non-empty name here?", not "what
  is the name?".
- (−) The namespace model rides on `html.parser`'s tokenizer, which treats `<script>`/
  `<style>` as raw text in *any* namespace. Markup written inside an `<svg><script>` is
  therefore invisible, where a browser would parse it. Suppressing it is still the better
  error (crediting JS source as a name would be a false positive); it is disclosed.
- (+) Conformance is now checkable rather than recited: a dev-only html5lib oracle
  derives the breakout list and the integration points, so the next disagreement fails a
  test instead of surviving three reviews.
- (−) An *empty* heading still satisfies "the document has an `<h1>`" — that is
  axe-core's separate `empty-heading` rule and a row this matrix does not carry, so it is
  disclosed rather than silently folded into `heading_structure`.
- (−) `id` references are resolved document-wide, so one that a browser would not resolve
  (the id lives inside a `<template>`) is accepted, and duplicate `id`s are not reported
  at all — an HTML-validity concern, not an a11y rule. Both are false *negatives*, stated
  in the SPEC.
- (−) The heading rule proves the outline is *legal*, not *logical*, and the label rule
  proves a name *exists*, not that it is *right*. Both limits are stated in the SPEC so
  the green is never read as more than it is.
