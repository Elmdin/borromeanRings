# ADR-0045 — Static accessibility (a11y) invariants gate

**Status:** Accepted

## Context
A product's **UX** carries invariants no code check sees, and the most consequential
of them — accessibility — is where a screen-reader user is simply *blocked*, not merely
inconvenienced. This is matrix **#6 (Product/UX)**. Most a11y quality (colour contrast,
ARIA correctness, focus order) needs a *rendered* DOM and belongs to a real tool
(axe-core) on a heavy lane. But a hard core of accessibility facts is **deterministic
and derivable from static HTML**: a full document must declare `<html lang>` (WCAG
3.1.1 — a screen reader can't choose a voice without it), every `<img>` must carry an
`alt` (WCAG 1.1.1), and a full document needs a non-empty `<title>` (WCAG 2.4.2). Each
is a threshold-free presence fact — the kind borromeanRings gates well.

Building this surfaced a real defect in a project in the roster: **fire** (an Electron
app, raw renderer HTML) has **five** pages and *every one* is missing `<html lang>` —
the exact justified need this check targets. borromeanRings itself has no HTML, so it does
**not** add `15_a11y` to its own required set (that would be vacuous); the dogfood is
fire plus the unit suite.

## Decision
Add `15_a11y` + `meta_harness.accessibility`: a native (stdlib `html.parser`) static
scan that reports violations for a per-project rule set (`[a11y].require`):

- `html_lang` — a full document (one containing an `<html>` tag) must set a non-empty
  `lang` on `<html>`.
- `img_alt` — every `<img>` anywhere must have an `alt` attribute (`alt=""` is allowed
  for decorative images — the attribute must merely be *present*).
- `page_title` — a full document must have a non-empty `<title>`.

The document-level rules (`html_lang`, `page_title`) apply **only when an `<html>` tag
is present**, so HTML *fragments* (components, partials, email templates) never trip
them. The check enumerates tracked `*.html`/`*.htm`/`*.xhtml`, minus configured
build-output/vendored dirs (`[a11y].exclude`, default `node_modules`/`dist`/`build`/
`vendor`). No tracked HTML ⇒ pass. Off unless `15_a11y` is in `[checks].required`.

## Alternatives considered
- **Shell out to `axe-core` / `pa11y`** — rejected as the gate's engine: they need Node
  + a headless browser to render each page (a heavy dependency and install surface),
  and their value is exactly the *rendered* checks (contrast, ARIA, focus) that a static
  gate can't and shouldn't fake. Those belong on a future heavy lane; the three rules
  here are the unambiguous static core that needs no browser.
- **A Lighthouse-style a11y score with a threshold (e.g. "≥ 90")** — rejected. A numeric
  target is exactly the arbitrary-metric gate borromeanRings refuses: it invites gaming,
  is tool-version-dependent, and says nothing actionable. Each rule here is a discrete
  yes/no fact a developer can fix.
- **Include contrast / ARIA statically** — rejected as false-positive-prone. Contrast
  needs computed styles; ARIA correctness needs the accessibility tree. Statically
  "guessing" them produces noise that erodes trust in the gate. Presence facts only.
- **Flag fragments for missing `<html lang>`/`<title>`** — rejected: a partial legitimately
  has neither. Gating document-level rules on the presence of `<html>` keeps the check
  correct for component-based frontends (the common case).

## Consequences
- (+) A governed frontend can no longer ship a page a screen reader can't announce.
  fire gets five real, actionable findings the moment it opts in; the rules that don't
  apply (fire's pages have titles and no bare `<img>`) correctly stay silent.
- (+) Deterministic, threshold-free, native (no node/axe-core), unit-tested (11 cases
  incl. fragment-safety, empty/whitespace `lang`, `alt=""`, case-insensitivity,
  per-rule narrowing) and adversarially verified (bad page fails all three; fixed page
  and no-HTML repo pass).
- (−) Static text analysis: it covers the *presence* floor, not rendered a11y quality
  (contrast, ARIA, focus). That's the right scope for a deterministic gate; the richer
  checks are a heavy-lane / T2 concern, explicitly deferred, not silently skipped.
- (−) Opt-in and role-dependent: each project picks its `require` set and `exclude`
  dirs. Omitting `15_a11y` leaves UX ungoverned — the same opt-in trade-off every
  archetype check makes.
