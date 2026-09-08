# Matrix #6 — Product / UX

Scope: what a *user-facing* artefact must satisfy — accessibility, usability heuristics,
performance as experienced, internationalisation, and error/feedback design. Rows U1–U3 are
static HTML facts shipped today; rendered-DOM rows need a heavy-lane browser tool; the rest
are archetype-gated on a `web-app` / `desktop` declaration (#79). Conventions:
[`README.md`](README.md).

| Row | Criterion (binary or ratchet) | Enforced by | Buildability | Source |
|---|---|---|---|---|
| U1 | Every full HTML document declares a non-empty `<html lang>` | ✅ `15_a11y` rule `html_lang` (ADR-0045) | now | WCAG 2.2 SC 3.1.1 Language of Page (Level A); axe-core rule `html-has-lang` |
| U2 | Every `<img>` carries an `alt` attribute (`alt=""` allowed for decorative images) | ✅ `15_a11y` rule `img_alt` | now | WCAG 2.2 SC 1.1.1 Non-text Content (A); axe-core rule `image-alt` |
| U3 | Every full HTML document has a non-empty `<title>` | ✅ `15_a11y` rule `page_title` | now | WCAG 2.2 SC 2.4.2 Page Titled (A); axe-core rule `document-title`; HTML Living Standard §4.2.2 (`title` element) |
| U4 | Form controls have an accessible label (`<label for>`, `aria-label`, or `aria-labelledby`) | gap → #159 (static, same parser as `15_a11y`; no sub-issue yet) | now | WCAG 2.2 SC 3.3.2 Labels or Instructions (A), SC 4.1.2 Name, Role, Value (A); axe-core rule `label` |
| U5 | Links have discernible text (no empty anchors, no bare "click here" by declared list) | gap → #159 (static) | now | WCAG 2.2 SC 2.4.4 Link Purpose (In Context) (A); axe-core rule `link-name` |
| U6 | Heading structure is well-formed: exactly one `<h1>` per document, no skipped levels | gap → #159 (static) | now | WCAG 2.2 SC 1.3.1 Info and Relationships (A); axe-core rules `page-has-heading-one`, `heading-order` |
| U7 | Text colour contrast meets the minimum ratio on the rendered page | gap → #159 (needs a rendered DOM — axe-core/pa11y on the heavy lane; explicitly deferred by ADR-0045) | telemetry (rendered) | WCAG 2.2 SC 1.4.3 Contrast (Minimum) (AA); axe-core rule `color-contrast` |
| U8 | All interactive elements are keyboard-reachable and focus is visible | gap → #159 (rendered) | telemetry (rendered) | WCAG 2.2 SC 2.1.1 Keyboard (A), SC 2.4.7 Focus Visible (AA), SC 2.4.11 Focus Not Obscured (Minimum) (AA, new in 2.2) |
| U9 | Interactive targets meet the minimum size or spacing | gap → #159 (rendered) | telemetry (rendered) | WCAG 2.2 SC 2.5.8 Target Size (Minimum) (AA, new in 2.2) |
| U10 | Content reflows at narrow viewports without two-dimensional scrolling (responsive) | gap → #79 (`web-app` profile; rendered) | archetype + rendered | WCAG 2.2 SC 1.4.10 Reflow (AA); SC 1.4.4 Resize Text (AA) |
| U11 | **Core Web Vitals ratchet**: LCP, INP and CLS measured on the declared pages may not regress vs the recorded baseline (threshold-free; Google's "good" bands are *not* gates) | gap → #159 (heavy lane, Lighthouse/`web-vitals` library; no sub-issue yet) | telemetry (rendered) | web.dev "Core Web Vitals" (LCP, INP — replaced FID March 2024 — CLS); Lighthouse |
| U12 | **Bundle-size ratchet**: the shipped JS/CSS byte size may not regress vs baseline | gap → #79 (`web-app` profile has a build output to measure) | archetype | `docs/ENFORCEMENT-COVERAGE.md` row I "Bundle / binary size ratchet"; web.dev "Reduce JavaScript payloads" |
| U13 | The system shows status for every asynchronous action (a loading/progress state exists for each declared long operation) | gap → #79 (profile playbook + a T2 critic rubric; not statically decidable) | archetype | Nielsen, "10 Usability Heuristics for User Interface Design" (NN/g, 1994/2020) #1 Visibility of system status |
| U14 | Error messages are expressed in plain language, identify the problem and suggest a fix; validation errors identify the field | gap → #79 + `56_critics` rubric `error_handling` (advisory, dormant — ADR-0036) | archetype | Nielsen heuristic #9 Help users recognize, diagnose, and recover from errors; WCAG 2.2 SC 3.3.1 Error Identification (A), SC 3.3.3 Error Suggestion (AA) |
| U15 | Destructive actions require confirmation or are undoable (error prevention) | gap → #79 (profile playbook; a static `required_arg`-style contract via #130 where the UI framework makes it declarable) | archetype | Nielsen heuristic #5 Error prevention, #3 User control and freedom |
| U16 | Help is reachable in a consistent location across pages; navigation and terminology are consistent | gap → #79 | archetype | WCAG 2.2 SC 3.2.6 Consistent Help (A, new in 2.2), SC 3.2.3 Consistent Navigation (AA); Nielsen heuristic #4 Consistency and standards |
| U17 | User-facing strings are externalised for translation (no hard-coded UI literals in the declared locales' code paths) | gap → #79 (`i18n` capability of the `web-app` profile; AST-decidable per framework) | archetype | W3C Internationalization "Internationalization techniques: Authoring HTML & CSS" (`lang` declarations); ISO 9241-210:2019 §6 (human-centred design — context of use) |
| U18 | Rendered-a11y regression ratchet: the count of axe-core violations per rule may not regress vs baseline (threshold-free alternative to a score) | gap → #159 (heavy lane; explicit rejection of a Lighthouse score threshold in ADR-0045) | telemetry (rendered) | axe-core rule set (Deque); ADR-0045 "Alternatives considered" |

## Notes

- **The buildable slice is shipped.** U1–U3 are the presence facts ADR-0045 chose; the `fire`
  project (five pages, all missing `<html lang>`) is the justified need.
- **U4–U6 are the next rows to build**: static, same `html.parser` pass, no browser — each a
  yes/no fact with an axe-core rule id to cite. They belong in the same `15_a11y` rule set
  (`[a11y].require`), not in a new check.
- **Known honesty defect (recorded, not fixed here).** `15_a11y` exits with status `pass` when a
  project has no tracked HTML ("nothing to check"); by ADR-0049 that is a `noop`. Every other
  archetype check (`14_container`, `13_adr`, `34_api_diff`) already emits `noop`. Tracked under
  #138; fixing it is a check change, out of scope for a documentation issue.
- **Why no usability *score*.** Nielsen's heuristics are judgment rows (T2/T3), so they are
  expressed as presence facts a playbook can check (U13, U15, U16) or as critic rubrics, never as
  a heuristic-evaluation score.
