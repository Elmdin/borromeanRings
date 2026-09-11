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
   *present*, not non-empty. The finding reports how many `<img>` lack it. Row U2;
   axe-core `image-alt`.
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
   - Headings inside `<template>` do **not** count: template content is inert until
     cloned, so it is not part of this document's outline. Headings inside comments do
     not count either (they are not markup), nor does an `<h1>` inside an
     `<svg>`/`<math>` subtree (there it is not an HTML heading at all) — unless an HTML
     integration point such as `<foreignObject>` has resumed HTML, where it is. `control_label` and `link_text` *do* apply
     inside `<template>` — a control's name and a link's text are properties of the
     element wherever it is finally inserted.

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
  flagged.
- **`<template>` content is inert until cloned**: it is not part of the outline, a
  `<title>` inside one is not the document's title, and it cannot name an enclosing
  link. It *is* still scanned in its own right (a control inside a template still needs
  a name).
- **Inside an `<svg>`/`<math>` subtree a familiar tag name is not an HTML element.** An
  `<svg><title>` names an icon, so it never satisfies the document's `<title>`; an
  `<svg><h1>` is not a heading; an `<svg><input>` is not a form control. HTML resumes at
  an integration point (`<foreignObject>`, `<desc>`, `<mtext>`, …), where all three are
  judged normally again. Two things are deliberately *not* excluded there: an SVG
  `<a href>` is a genuine link and still needs a name, and an `<img>` really does break
  out of foreign content into HTML, so it still needs an `alt`.

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
