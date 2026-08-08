# SPEC — Static accessibility (a11y) invariants gate

**Status:** Implemented · **Realized by:** `src/meta_harness/accessibility.py`,
`checks/shared/15_a11y.sh` · ADR-0045

## Problem
A product's HTML carries accessibility invariants no *code* check covers, and the
deterministic core of them is where a screen-reader user is *blocked*, not merely
inconvenienced: a full document must declare `<html lang>`, every `<img>` must carry an
`alt`, and a full document needs a non-empty `<title>`. This is the static,
threshold-free slice of the Product/UX matrix (#6); rendered a11y quality (contrast,
ARIA, focus order) needs a browser and is out of scope (it belongs on a heavy lane with
a real tool such as axe-core).

## Contract
`15_a11y` enumerates the project's tracked `*.html`/`*.htm`/`*.xhtml` (excluding the
segments in `[a11y].exclude`) and fails closed on any violation among the enforced
rules `[a11y].require` (default all three):

1. **`html_lang`** — a **full document** (HTML containing an `<html>` tag) must set a
   non-empty `lang` attribute on `<html>` (WCAG 3.1.1). Whitespace-only counts as
   missing.
2. **`img_alt`** — every `<img>` anywhere must have an `alt` attribute (WCAG 1.1.1).
   `alt=""` is accepted (correct marking for a decorative image); the attribute must be
   *present*, not non-empty. The finding reports how many `<img>` lack it.
3. **`page_title`** — a **full document** must have a non-empty `<title>` (WCAG 2.4.2).

The document-level rules (`html_lang`, `page_title`) apply **only when an `<html>` tag
is present**, so HTML *fragments* (components, partials) are never falsely flagged.
`img_alt` applies to any `<img>`, fragment or not. No tracked HTML ⇒ **pass** (not a UI
project). Off unless `15_a11y` is in `[checks].required`.

Config `[a11y]`: `require` (default `["html_lang", "img_alt", "page_title"]`),
`exclude` (path segments dropped from the scan; default
`["node_modules", "dist", "build", "vendor"]`).

## Guarantees
- **Deterministic & native** — stdlib `html.parser` (lenient, case-insensitive); no
  node/axe-core/browser dependency.
- **Threshold-free** — each rule is a yes/no WCAG-cited fact; no score target.
- **Fragment-safe** — document rules gate on the presence of `<html>`, so
  component-based frontends don't get false positives.
- **Right floor** — presence, not rendered quality (no contrast/ARIA/focus — those need
  a DOM and belong on a heavy lane). Unit-tested (11 cases) + adversarially verified
  (bad page fails all three; fixed page and no-HTML repo pass).

## Dogfood
- **fire** (Electron; raw renderer HTML) — five pages, *every one* missing
  `<html lang>`; the check flags all five (`html_lang`) and correctly stays silent on
  `img_alt`/`page_title` (those pages have titles and no bare `<img>`). The justified
  need this check was built for.
- **borromeanRings** — has no HTML, so it does **not** declare `15_a11y` (that would be
  vacuous). The unit suite carries the module's behavioural coverage.
