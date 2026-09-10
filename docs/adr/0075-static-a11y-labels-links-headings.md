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
  have an accessible name: nested inside a `<label>`, targeted by a `<label for>`,
  a non-empty `aria-label`, or an `aria-labelledby` naming **an id that exists in the
  document**. A dangling reference names nothing and is a violation. `placeholder` and
  `title` are **not** accepted (stricter than axe-core's `label` rule, deliberately: a
  hint that disappears on input, or a tooltip a touch user never sees, is not a label).
- **`link_text`** (SC 2.4.4; axe-core `link-name`) — every `<a href>` must have non-empty
  text content, a non-empty `aria-label`, an `aria-labelledby` that resolves, or an
  `<img>` with non-empty `alt` inside it. `aria-labelledby` was not in #159's
  enumeration; it is accepted here because it is the same accessible-name computation as
  U4 and rejecting it would flag conformant markup — a widening that can only *reduce*
  false positives, recorded rather than silent.
- **`heading_structure`** (SC 1.3.1; axe-core `page-has-heading-one`, `heading-order`) —
  a **full document** has exactly one `<h1>` (zero and every extra are violations), and
  in any document or fragment no heading may descend more than one level below the
  heading before it. Headings inside `<template>` are excluded (inert until cloned, so
  not part of this outline); headings inside comments are not markup. `control_label`
  and `link_text` *do* apply inside `<template>`, because a name and a link's text
  travel with the element wherever it is inserted.

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
- **`<template>` content cannot name an enclosing element**: it never renders in place,
  so it is not the outline, not the document `<title>`, and not a link's text — while a
  link or control *inside* a template is still checked on its own terms.

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
- (−) `id` references are resolved document-wide, so one that a browser would not resolve
  (the id lives inside a `<template>`) is accepted, and duplicate `id`s are not reported
  at all — an HTML-validity concern, not an a11y rule. Both are false *negatives*, stated
  in the SPEC.
- (−) The heading rule proves the outline is *legal*, not *logical*, and the label rule
  proves a name *exists*, not that it is *right*. Both limits are stated in the SPEC so
  the green is never read as more than it is.
