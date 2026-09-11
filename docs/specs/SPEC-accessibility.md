# SPEC — Static accessibility (a11y) invariants gate

**Status:** Implemented · **Realized by:** `src/meta_harness/accessibility.py`,
`checks/shared/15_a11y.sh` · ADR-0045, ADR-0049, ADR-0075

## Problem
A product's HTML carries accessibility invariants no *code* check covers, and the
deterministic core of them is where a screen-reader user is *blocked*, not merely
inconvenienced: a full document must declare `<html lang>`, every `<img>` must carry an
`alt`, a full document needs a non-empty `<title>`, every form control needs an
accessible name, every link needs discernible text, and the heading outline must be
well-formed. This is the static, threshold-free slice of the Product/UX matrix (#6)
— rows U1–U6. Rendered a11y quality (contrast, keyboard reachability, target size)
needs a browser and is **not built**; see §"Not built: needs a rendered DOM".

## Contract
`15_a11y` enumerates the project's tracked `*.html`/`*.htm`/`*.xhtml` (excluding the
segments in `[a11y].exclude`) and fails closed on any violation among the enforced
rules `[a11y].require`.

### Rules gated by default (`html_lang`, `img_alt`, `page_title`)

1. **`html_lang`** — a **full document** (HTML containing an `<html>` tag) must set a
   non-empty `lang` attribute on `<html>` (WCAG 2.2 SC 3.1.1). Whitespace-only counts as
   missing. Matrix row U1; axe-core `html-has-lang`.
2. **`img_alt`** — every `<img>` anywhere must have an `alt` attribute (SC 1.1.1).
   `alt=""` is accepted (correct marking for a decorative image); the attribute must be
   *present*, not non-empty. The finding reports how many `<img>` lack it. An image that
   is **out of the accessibility tree** is not counted — see "Hidden content" below, the
   one rule every content check applies. Row U2; axe-core `image-alt`.
3. **`page_title`** — a **full document** must have a non-empty `<title>` (SC 2.4.2).
   Row U3; axe-core `document-title`.

### Rules available but **opt-in** (`control_label`, `link_text`, `heading_structure`)

These three are *not* in the default `require` set. A project adopts them one at a time
by naming them in `[a11y].require` — a shipped frontend typically has a backlog against
each, and turning them all on at once would make the gate un-adoptable (ADR-0075).

4. **`control_label`** — every labelable form control has an **accessible name**
   (SC 3.3.2 Labels or Instructions, SC 4.1.2 Name, Role, Value; axe-core `label`).
   Matrix row U4.
   - Applies to `<select>`, `<textarea>`, and `<input>` **except** `type` in
     `hidden`, `submit`, `button`, `reset`, `image` — those are named by their `value`
     or `alt`, or are not exposed at all.
   - A control is named when **any** of these holds: it is nested inside a `<label>`
     **that has a name**; some `<label for="X">` **with a name** targets its `id`; it
     carries a non-empty `aria-label`; or its `aria-labelledby` names **at least one
     element that has a name**.
   - A name is **resolved, not merely present**. `<label><input></label>`,
     `<label for="q"> </label>` and `aria-labelledby` pointing at an empty (or missing)
     element all announce *nothing*, and all are violations. An element's name is the
     text of its subtree, plus the `alt` of images inside it and the `aria-label` of
     any descendant — so a `<label>` whose only content is `<img alt="Search">` does
     name the control. References are followed **one level** (an element named only by
     its *own* `aria-labelledby` cannot lend that name onward), which is the limit the
     accessible-name algorithm itself imposes.
   - A control's own content is never its name: a `<select>`'s `<option>`s and a
     `<textarea>`'s content are the *value*.
   - `placeholder` and `title` are **not** accepted as names. A hint that vanishes on
     input, or a tooltip that never reaches a touch user, is not a label. This is
     deliberately stricter than axe-core's `label` rule, which tolerates both.
     **Unsettled:** axe-core lists `non-empty-title` among that rule's passing checks, so
     `<input title="Search">` may well pass there and be reported here. Nothing was
     installed to settle it (no npm, no axe-core), and it is recorded as an open question
     rather than guessed at; if axe does pass it, this rule is stricter than its sibling
     on purpose and the divergence should be stated, not quietly aligned.
   - A control that is **out of the accessibility tree is not checked**: `hidden`, or
     `aria-hidden="true"` on it or on any ancestor, removes the element and its subtree
     from what assistive tech is given, and a real a11y tool judges nothing there. See
     "What these rules do not catch" for the missed-violation this accepts.
5. **`link_text`** — every `<a href>` has **discernible text** (SC 2.4.4 Link Purpose;
   axe-core `link-name`). Matrix row U5. A link is discernible when its **name from
   content** is non-empty after stripping whitespace — that is, when any of the
   following is inside it or on it: text; a non-empty `aria-label`; an `<img>` with a
   non-empty `alt`; an `<svg>` with a `<title>`; or an `aria-labelledby` that resolves.
   - **A descendant can contribute the name.**
     `<a href="/tw"><svg role="img" aria-label="Twitter"></svg></a>` is named
     "Twitter" — the commonest icon-link idiom there is, and a rule that failed it
     would teach people to switch the rule off. `aria-label`, `aria-labelledby` and
     `<svg><title>` count wherever they sit inside the link, exactly as `<img alt>`
     always did.
   - `aria-labelledby` is accepted here for the same reason as in `control_label`: it is
     the same accessible-name computation, and rejecting it would flag conformant
     markup. (#159 enumerated only the first three sources; this is a deliberate,
     recorded widening — it can only *reduce* false positives.)
   - **A `title` attribute on the `<a>` itself names the link** — HTML-AAM's last-resort
     name source, which axe-core's `link-name` (the rule this one is a sibling of)
     accepts. `<a href="/rss" title="RSS feed"><i class="fa fa-rss"></i></a>` is
     conformant markup and flagging it taught nobody anything. This is *not* symmetric
     with `control_label`, and deliberately so: a tooltip is a poor label for a field the
     user must fill in, and the only name a purely decorative icon link ever has.
   - A link that is **out of the accessibility tree is not checked**: `hidden`, or
     `aria-hidden="true"` on it or on an ancestor. The decorative chevron in
     `<a href="#main" aria-hidden="true" tabindex="-1">` is the common case.
   - **There is no banned-phrase list.** "Click here", "read more", "link" are
     *discernible*; whether they are *meaningful* is a judgement about context, not a
     fact about the document. A gate that guessed would be enforcing an opinion. Link
     purpose in context (SC 2.4.4) beyond the empty case stays a human/T2 concern.
   - `<a>` without an `href` is not a link (it is a name/target) and is not checked.
   - Only text that actually **renders inside the link** counts: `<script>`/`<style>`
     source is not text, and a `<template>` (or an `<img>` inside one) nested *within*
     the link is inert, so neither can give the link its name. A link that is itself
     inside a template sits at the same depth as its own content and collects it
     normally.
6. **`heading_structure`** — the document's heading outline is well-formed (SC 1.3.1
   Info and Relationships; axe-core `page-has-heading-one`, `heading-order`). Row U6.
   Two facts, one rule:
   - **Exactly one `<h1>`** — *zero* is a violation only in a **full document** (a
     fragment legitimately has no `<h1>`), reported without a line since an absence has
     no location; each `<h1>` **after the first** is a violation at its own line, in a
     fragment as much as in a document — two top-level headings are one too many
     wherever they appear.
   - **No skipped levels** — for consecutive headings in document order, the level may
     not increase by more than one (`h2` → `h4` is a violation at the `h4`). Checked in
     fragments too, since it needs no document context; a fragment that legitimately
     *starts* at `h3` is not flagged, because only the deltas are examined.
   - Headings that are **out of the accessibility tree** (`hidden`, `aria-hidden="true"`)
     do not count, in *either* half of the rule: a hidden `<h1>` is neither the document's
     top-level heading nor a second one, and a hidden heading is not a step in the
     sequence. See "Hidden content" below.
   - Headings inside `<template>` do **not** count — nor does anything else in one; see
     "`<template>` content is inert, for every rule" below. Headings inside comments do
     not count either (they are not markup). An `<h1>` inside an `<svg>`/`<math>` **does**
     count: `h1`–`h6` are in the parsing spec's breakout list, so a browser hoists the
     heading out into HTML — and closes the `<svg>` doing it, which is why a second `<h1>`
     written after one inside an `<svg>` is a duplicate this rule can see.

The document-level rules (`html_lang`, `page_title`, and the one-`<h1>` half of
`heading_structure`) apply **only when an `<html>` tag is present**, so HTML *fragments*
(components, partials) are never falsely flagged. **No tracked HTML ⇒ `noop`**, never a
hollow `pass`: the check inspected nothing and says so (ADR-0049), the log naming what
was searched and where. A `git ls-files` failure **inside** a repo fails closed (a git
error is not evidence of "no HTML"); a project that genuinely is not a repo falls back to
a bounded filesystem walk. Off unless `15_a11y` is in `[checks].required`.

Config `[a11y]`: `require` (default `["html_lang", "img_alt", "page_title"]`),
`exclude` (path segments dropped from the scan; default
`["node_modules", "dist", "build", "vendor"]`).

### Parser fidelity
The rules answer what a *browser* would build, not what the text looks like:

- **Duplicate attributes resolve first-wins**, as the HTML parsing spec requires:
  `<input type="hidden" type="text">` is a hidden input (exempt), and
  `<input type="text" type="hidden">` is a text input (needs a label). `html.parser`
  reports every occurrence; taking the last would both invent violations and miss them.
- **`<script>`/`<style>` content is source, not text.** `html.parser` hands it to the
  same callback as prose; a link whose only content is code renders empty and is
  flagged. That list is read off `html.parser`'s own `CDATA_CONTENT_ELEMENTS` rather
  than recited, because it is that switch the module has to model.
- **A text-only element's content is a string, not elements.** The HTML tokenizer reads
  `<textarea>`, `<title>`, `<iframe>`, `<xmp>`, `<noembed>`, `<noframes>` and
  `<plaintext>` as raw text or RCDATA, so `<textarea><img src="cat.png"></textarea>` has
  **no image in it** — a "paste your markup here" box is correct markup that renders
  correctly, and reading it as elements failed it on the *default* `img_alt` rule.
  `html.parser` knows this only for `script`/`style`, so the module applies it to the
  rest; the list is **derived from html5lib**, like the breakout list. Only the
  element's own end tag ends the run of text (`</plaintext>` ends nothing — that element
  runs to end of file), and in a foreign subtree none of this applies, because there the
  tag is not the HTML element of that name. Tag-shaped text stays **text**: a browser
  shows `<title><b></b></title>` as the literal string `<b></b>`, so that title is not
  empty and `page_title` does not fire. A `<script src="a.js"/>` written in the
  self-closing form starts its run of text here too — `html.parser` skips its own
  raw-text switch on that form, and an element left open to end of file silently drops
  the rest of the document. `<noscript>` is deliberately **not** in the
  list: a browser with scripting on reads it as raw text but then renders none of it, and
  the reader who does see the content is the one with scripting off, for whom it is
  ordinary markup — so an `<img>` there really does need an `alt`.
- **`<template>` content is inert, for every rule.** It is not part of the outline, a
  `<title>` inside one is not the document's title, it cannot name an enclosing link —
  and since the #211 review, no rule judges what is inside one at all. A template is a
  *stamp*: its text, `href`, `alt` and ids are supplied by whatever clones it, so the
  source cannot tell an unfinished placeholder from a finished element, and
  `<template id="row"><li><a href=""><span></span></a></li></template>` is exactly what
  templates are for. The earlier split — inert for the outline and the title, live for
  `control_label` and `link_text` — flagged that placeholder, and had no defence beyond
  "a name travels with the element". Judging none of it is uniform, states one rule
  instead of two, and can only *reduce* false positives; the violations it now misses are
  listed under "What these rules do not catch".
- **Hidden content: one rule, everywhere.** `hidden` and `aria-hidden="true"` take an
  element **and its subtree** out of the accessibility tree, and **every rule that judges
  rendered content skips it** — `img_alt`, `control_label`, `link_text` *and*
  `heading_structure`. The rule the check enforces is the one assistive technology
  experiences, so the document it judges is the document a screen reader is handed.

  An earlier version of this SPEC exempted the outline, arguing that dropping an element
  out of a **sequence** could *invent* a violation. That argument is wrong, and the
  example it led with argued against it. These two documents are identical to a screen
  reader:

  ```html
  <h1>H</h1><h2>A</h2><div hidden><h3>Hid</h3></div><h4>B</h4>
  <h1>H</h1><h2>A</h2><h4>B</h4>
  ```

  Counting the hidden `<h3>` gave them opposite verdicts. It did not prevent an invented
  finding — it **masked a real one**: with the `<h3>` hidden, `h1 → h2 → h4` *is* the
  sequence the user navigates, and the skip is a fact about the page, which is why
  axe-core's `heading-order` reads the accessibility tree. Working the other two cases
  points the same way. **Presence:** if the only `<h1>` is inside a `hidden` container the
  page has no perceivable top-level heading, so reporting its absence is correct.
  **Duplication:** a hidden `<h1>` is not perceived, so it cannot be the second of two —
  `<div hidden><h1>Dup</h1></div><h1>Real</h1>` used to be reported and no longer is.
  Each of the three is pinned by a test.

  **`page_title` and `html_lang` are untouched by this**, and not because they read no
  sequence: a `<title>` and the `<html>` element are **document metadata**, never rendered
  content, so there is nothing for `hidden` to remove from the accessibility tree.
  `<title hidden>Dashboard</title>` still names the page, exactly as it does in a browser.
  Pinned by a test, so the rule cannot quietly spread to them.

  **`hidden` and `aria-hidden` are not the same thing, and are treated the same here on
  purpose.** `hidden` is not rendered at all; `aria-hidden="true"` leaves the element
  visible and potentially focusable. For these four rules the question is only "is this in
  the accessibility tree", and the answer is no for both. The difference matters for a
  fact this check does **not** carry: a *focusable* element inside an `aria-hidden`
  subtree can be tabbed to while announcing nothing, which is axe-core's separate
  `aria-hidden-focus` rule — listed under "What these rules do not catch" with
  `empty-heading` and `valid-lang`, not silently folded in here.
- **A self-closing flag on an HTML element means nothing.** The parsing spec
  acknowledges `<x/>` only in foreign content, where `<rect/>` really does close;
  `html.parser` closes every one, which made `<a href="/x" />Read the docs</a>` an empty
  link. In an `.xhtml` file the flag *is* meaningful, and treating it as HTML there is a
  deliberate missed violation rather than an invented one. A **void** element written
  `<br/>` was already closed when it opened, and a **foreign** one (`<rect/>`) really does
  self-close.
- **Inside an `<svg>`/`<math>` subtree a familiar tag name is usually not an HTML
  element** — but the parsing spec has a **breakout list** of tags a browser refuses to
  keep there: it closes the foreign element and parses them as HTML. The list is
  `b, big, blockquote, body, br, center, code, dd, div, dl, dt, em, embed, h1, h2, h3,
  h4, h5, h6, head, hr, i, img, li, listing, menu, meta, nobr, ol, p, pre, ruby, s,
  small, span, strike, strong, sub, sup, table, tt, u, ul, var`, plus `font` when it
  carries `color`, `face` or `size`. It is **derived from html5lib by
  `tests/unit/test_accessibility_conformance.py`, not copied from prose** — reciting it
  is what got it wrong twice.
  - So an `<svg><h1>` **is** the document's heading, and an `<svg><img>` **does** need an
    `alt`. A breakout closes the whole subtree, so everything written after it is HTML
    too.
  - What stays foreign: `<title>` (it names an icon, never the page), `<input>`,
    `<select>`, `<textarea>` (not form controls), `<label>` (labels nothing),
    `<template>`, `<script>`, `<style>`, and `<a>`. HTML resumes at an integration point
    — `<foreignObject>`, `<desc>`, `<title>`'s children, the MathML text points
    (`<mtext>`, `<mi>`, `<mo>`, `<mn>`, `<ms>`), and `<annotation-xml>` **only** when its
    `encoding` is `text/html` or `application/xhtml+xml`, matched whole and untrimmed.
  - **An integration point only resumes HTML in its own language.** `<foreignObject>`,
    `<desc>` and `<title>` are SVG's; the text points and `<annotation-xml>` are MathML's.
    Testing the union of the two made `<svg><mtext><input>` a form control, and let
    `<math><desc><title>` pass for the page's title — the same shape of defect in both
    directions, one of them on a default-gated rule.
  - **The language is inherited, not read off the tag name.** html5lib confirms the
    `<svg>` inside a `<math>` is a *MathML* element, so a `<desc>` in it is MathML's
    `desc` and not an integration point at all.
  - **A `<script>`/`<style>` is raw text only in HTML.** A browser parses the content of
    an `<svg><script>` as markup, so an `<h1>` there is a real heading that closes the
    `<svg>`. `html.parser` switched to CDATA on any `script`/`style`, which lost that
    heading and — with no `</script>` to come back at — swallowed the rest of the
    document, *inventing* "document has no `<h1>`" on a page that has one. The module
    now overrides `set_cdata_mode` so a foreign one stays in markup mode. That reaches
    into an implementation detail of `html.parser` deliberately, with eyes open: the
    conformance suite pins the behaviour against html5lib, so a future Python that
    changes it fails the suite instead of drifting.
  - **One deliberate departure:** an SVG `<a href>` stays in the SVG namespace, and
    `link_text` checks it anyway. That is a **judgement about user-facing links** — it is
    a link a user clicks and a screen reader announces — not a claim about HTML element
    classification. It is **SVG only**: MathML has no anchor element, so `<math><a href>`
    is nothing a user can click and is not checked.

### Reporting
Each violation is one line:

```
  - <file>:<line> — [<rule>] — <what is wrong, and the WCAG SC>
```

The line number is the source line of the offending element. Findings that report an
*absence* (`page_title`, a document with no `<h1>`) or an aggregate (`img_alt` reports a
count) have no single location and print as `<file> — [<rule>] — …`. Nothing is
summarised away: every offending element gets its own line.

## What these rules do **not** catch
Stated so the green is never read as more than it is:

- **`control_label`** proves a name *exists*, not that it is *right*. A `<label>` reading
  "Email" over a phone field, a copy-pasted `for=` pointing at the wrong control, an
  `aria-label` that contradicts the visible text — all pass. So does a label that is
  present but visually hidden by a broken stylesheet (a rendered concern).
- **`link_text`** proves the link *has* an accessible name, not that the name *conveys
  purpose*. Ten "Read more" links on one page pass. So does an `alt` that describes the
  image instead of the link's destination.
- **`heading_structure`** proves the outline is *legal*, not *logical*. `h1 → h2 → h2`
  where the second `h2` should have been an `h3` passes; so does an `<h2>` used purely
  because it "looks right". Nesting the headings correctly and titling them meaningfully
  stays a human judgement.
- **All three** see the source, not the page. Content injected by JavaScript, names
  computed at runtime (`aria-labelledby` resolved into a component's shadow root), and
  anything a framework generates at build time are outside a static scan. A project
  whose HTML is generated should scan the *build output* (drop `dist`/`build` from
  `[a11y].exclude`) or wait for the rendered lane.
- **An *empty* heading still counts as a heading.** `<h1></h1>` satisfies "the document
  has an `<h1>`", because the fact this rule states is about the outline's *shape*.
  Whether a heading announces anything is axe-core's separate `empty-heading` rule and a
  row the Product/UX matrix does not carry; it is not silently folded in here.
- **`lang` is checked for presence, not validity.** `<html lang="nonsense">` passes;
  whether the value is a well-formed BCP-47 tag is axe-core's `valid-lang`, a different
  fact from SC 3.1.1's "has a language".
- **An SVG link that uses only the deprecated `xlink:href` is not seen as a link**, so it
  is never checked for a name.
- **Nothing inside a `<template>` is judged** — not a missing `alt`, not an unnamed
  control, not an empty link. This is the deliberate cost of treating a template as a
  stamp (see "Parser fidelity"): a real image with a real `alt` missing from a row
  template passes. A project that ships most of its markup through templates should know
  that this check is nearly silent about it.
- **Nothing marked `hidden` or `aria-hidden="true"` is judged at all** (except by
  `page_title`/`html_lang`, which read metadata). A field in a `<div hidden>` panel that
  is shown later by script does need a label, and an image in one does need an `alt`; this
  check judges the page as delivered, and will not say so. The alternative — flagging it —
  fails the markup axe-core passes, which is the error that gets a rule switched off. Note
  that html5lib *does* build those elements: this is a departure from the **accessibility
  tree**, not from the DOM, so a differential against a tree builder reports it as a
  difference. It is the intended one.
- **A focusable element inside an `aria-hidden` subtree is not reported.** It can be
  tabbed to while announcing nothing, which is a real defect — and a *different* one:
  axe-core's `aria-hidden-focus`, about focus order rather than about names or outlines.
  It needs the resolved focus order (`tabindex`, `inert`, shadow roots), which is the
  rendered lane's job (#210), so it is named here rather than approximated.
- **Content inside an `aria-hidden` subtree still counts as an enclosing element's
  name.** The accessible-name algorithm excludes it, so
  `<a href="/x"><span aria-hidden="true">Icon</span></a>` really is an unnamed link and
  this check stays quiet. Crediting it is the missed-violation direction, chosen over
  modelling name computation's exclusions.
- **A `<select>`'s insertion-mode quirks are not modelled — and this one runs the wrong
  way.** `html.parser` is a tokenizer, not a tree builder: a browser silently discards an
  `<img>` written inside a `<select>`, and this check counts it. That is an **invented
  finding**, not a missed one, and it is recorded here as such rather than filed with the
  safe departures. It is tolerated because the markup is invalid either way and the
  alternative is carrying the "in select" insertion mode — where `<input>`/`<textarea>`
  *close* the `<select>` — whose subtleties would trade this false positive for several
  false negatives on valid markup.
- **`<image>` is not rewritten to `<img>`, and that one runs the wrong way too** — in the
  other direction: a browser renames the obsolete `<image>` tag, so `<image src="x">`
  needs an `alt` and this check never asks for one. A missed violation, listed here with
  the `<select>` case so both known non-conformances are visible in one place.
- **Text a browser shows inside a `<textarea>` still names an enclosing `<label>`.**
  `<label><textarea>draft</textarea></label>` is announced as unnamed by a real tool
  (the embedded control's value is excluded when naming that control) and passes here.
  Missed violation, safe direction.
- **A self-closing non-void element in an `.xhtml` file is read as HTML.** `<a href="/x"
  />` really is an empty link in XHTML; here it stays open and takes the text after it,
  so the violation is missed rather than invented. `.xhtml` is in scope for the scan and
  the check does not otherwise distinguish it.
- **`id` resolution is document-wide and does not model `<template>` scope.** A
  `<label for="x">` or `aria-labelledby="x"` outside a template is accepted when the
  only `id="x"` lives *inside* one, though a browser would not resolve it. This is a
  deliberate **false negative**: the alternative is a scope model this gate should not
  carry, and a missed violation is the safe direction — the gate never invents one.
- **Duplicate `id`s are not reported.** Two elements sharing an `id` is invalid HTML
  and breaks label association in practice; here the reference simply resolves. That is
  an HTML-validity fact, not an accessibility rule, and belongs to a validator.

## Not built: needs a rendered DOM (matrix rows U7–U9, U18) — #210
These rows of `docs/matrices/06-product-ux.md` are **specified here and deliberately not
implemented**. They are not properties of the HTML source at all, so no amount of
parsing gets them honestly:

- **U7 contrast** (SC 1.4.3) needs the *computed* foreground and background colours after
  the cascade, inheritance, opacity and compositing against what is actually painted
  behind the text. A CSS rule is not a rendered colour.
- **U8 keyboard reachability and visible focus** (SC 2.1.1, 2.4.7, 2.4.11) needs the real
  focus order after `tabindex`, `display:none`, `visibility`, `inert` and shadow roots
  are resolved, and whether the `:focus-visible` styles that win the cascade actually
  paint an indicator.
- **U9 target size** (SC 2.5.8) is a *layout* fact — the CSS-pixel box of an element at a
  given viewport, which only layout produces.
- **U18 rendered-a11y ratchet** — axe-core's violation count per rule id, which requires
  running axe-core inside a page.

Guessing any of them from source text produces false positives, and a fail-closed gate
that cries wolf gets switched off. A future **opt-in heavy lane** (`[a11y].rendered =
true`, tracked as **#210**) would need: a renderer and axe-core installed locally (no API
key, no network beyond a locally served page); **`noop`, never `pass`, when the tool is
absent** (ADR-0049); the tool version recorded in the receipt; a deterministic viewport
and settled fonts; binary WCAG-cited findings for U7–U9 carrying the rendered evidence
(measured ratio, computed box, focus position); and for U18 a **per-rule non-regression
ratchet**, never a score threshold (ADR-0045 rejected a Lighthouse-style number, and this
project rejects arbitrary targets generally). No browser or renderer was installed to
scope this — the reasoning above is from the specifications, which is all it needs.

## Guarantees
- **Deterministic & native** — stdlib `html.parser` (lenient, case-insensitive); no
  node/axe-core/browser dependency, so a project can adopt a11y gating with nothing to
  install. The parse is a single pass that gathers facts; each rule is a pure function of
  those facts, so adding a rule cannot change another rule's verdict.
- **Threshold-free** — each rule is a yes/no WCAG-cited fact; no score target.
- **Fragment-safe** — document rules gate on the presence of `<html>`, so
  component-based frontends don't get false positives.
- **Adoptable one rule at a time** — the three new rules are off by default; a project
  turns each on in `[a11y].require` when it is ready to keep it green.
- **Honest about nothing** — no HTML ⇒ `noop`; an undecidable git state ⇒ fail closed.
- **Right floor** — a resolved name and a well-formed outline, not rendered quality.
  Unit-tested (line and branch coverage at the repo's 100% ratchet, exact-value
  assertions including wrapping vs `for=` labels, a label with no text at all, a
  dangling and an empty-target `aria-labelledby`, the `<svg aria-label>` icon link, an
  `<a>` wrapping only an `<img alt="">`, an `<svg><title>` against the document title, an
  `<h1>` inside `<template>`, a comment or an `<svg>`, two `<h1>`s, and `h1 → h3`) and
  integration-tested by driving the real `verify.sh`. Every rule has been shown to fail
  when the behaviour it describes regresses.
- **Conformance is derived, not recited** — `tests/unit/test_accessibility_conformance.py`
  parses every namespace fixture twice, once with **html5lib** (a spec-conformant tree
  builder; a dev-only test oracle, never a runtime dependency) and once with this module,
  and requires the two to agree on where each element lands. **All three** recited lists
  are now *computed* from html5lib and compared to the ones the module implements — the
  breakout tags, the text-only (raw text / RCDATA) tags, and the void tags — plus a
  differential over adversarial documents that cross every seam at once. Only `<col>`
  cannot be probed (a browser drops it outside a `<colgroup>`) and is asserted in a
  table instead. The review that prompted this showed the cost of leaving one unguarded:
  adding `iframe` to the void list passed the entire suite.
- **The oracle is not total, and the check outlives it.** html5lib 1.1 raises
  `AssertionError` inside its own `resetInsertionMode` on some `<svg><select>` shapes.
  It is a dev-only test dependency, so nothing shipped is affected — but the module is
  tested to parse that markup and return findings, because a gate that raises is a gate
  that blocks. A differential is evidence about the classes its generator can express and
  nothing more; the fixtures here name the classes, and the two non-conformances above
  are the ones a wider generator keeps finding.

## Dogfood
- **fire** (Electron; raw renderer HTML) — five pages, *every one* missing
  `<html lang>`; the check flags all five (`html_lang`) and correctly stays silent on
  `img_alt`/`page_title` (those pages have titles and no bare `<img>`). The justified
  need this check was built for.
- **borromeanRings** — has no HTML, so it does **not** declare `15_a11y` (that would be
  vacuous) and the check reports `noop` here. The fixtures for every rule live inside the
  test suites (`tests/unit/test_accessibility.py`, `tests/integration/test_a11y_gate.py`)
  and are materialized into temporary projects at run time, deliberately: committing
  `.html` fixtures into this repo would give its own `15_a11y` HTML to find and turn an
  honest `noop` into a manufactured verdict.
