# Changelog

All notable changes to borromeanRings are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to
follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Discipline is enforced by check `11_changelog`: this file must exist and carry an
`## [Unreleased]` section (a home for pending changes). The stricter
"every source change updates the changelog" rule is available via
`[changelog].require_entry_on_src_change` and will be enabled once the current PR
queue is merged.

## [Unreleased]

### Added
- **Static a11y rules for labels, link text and heading structure** (ADR-0075, #159) —
  matrix rows U4–U6 of `docs/matrices/06-product-ux.md`, added to `15_a11y` (not a second
  check) and **opt-in** via `[a11y].require`, so a project adopts one at a time:
  `control_label` (every `<select>`/`<textarea>`/`<input>` except
  `hidden|submit|button|reset|image` has an accessible name — a wrapping or
  `for=`-associated `<label>`, a non-empty `aria-label`, or an `aria-labelledby` naming an
  id that **exists**; WCAG 2.2 SC 3.3.2, 4.1.2), `link_text` (every `<a href>` has
  non-empty text, an ARIA name, or an `<img alt="...">` inside it; SC 2.4.4), and
  `heading_structure` (a full document has exactly one `<h1>`; no heading skips a level;
  `<template>` and comment content excluded; SC 1.3.1). Findings now carry a source line
  and are reported as `file:line — [rule] — what is wrong` (an absence, such as a missing
  `<title>` or `<h1>`, prints without a line rather than inventing one). Defaults are
  unchanged — `[a11y].require` still defaults to the three ADR-0045 rules, and `adopt`'s
  `RECOMMENDED` set is untouched.
  Deliberately **not** built and specified instead (#210): contrast, keyboard
  reachability/visible focus, target size and the axe-core violation ratchet (rows
  U7–U9, U18) are properties of the *rendered* page, not the source. No banned-phrase
  ("click here") list either: link purpose *in context* is a judgement, not a fact.

### Fixed
- `15_a11y` suppressed headings inside `<svg>`/`<math>`, which is the **opposite** of what
  a browser does (PR #211 follow-up review). `h1`–`h6` are in the HTML parsing spec's
  foreign-content *breakout* list: a browser hoists `<svg><h1>` out into a genuine
  heading and closes the `<svg>` doing it. The old behaviour both invented a "no `<h1>`"
  finding for a page whose heading sat in an `<svg>` and hid a duplicate `<h1>`. The
  **whole** breakout list is now implemented (`b, big, blockquote, body, br, center,
  code, dd, div, dl, dt, em, embed, h1`–`h6`, `head, hr, i, img, li, listing, menu, meta,
  nobr, ol, p, pre, ruby, s, small, span, strike, strong, sub, sup, table, tt, u, ul,
  var`, plus `font` with `color`/`face`/`size`), along with `<annotation-xml>`'s
  `encoding` condition — and it is **derived from html5lib by a new conformance suite**
  rather than recited, since reciting it is what got it wrong twice. `html5lib` joins the
  `dev` extra as a test oracle only — **pinned** (`==1.1`), because an oracle whose
  version drifts can disagree with itself between a laptop and CI (ADR-0077); the
  harness itself still runs on the stdlib alone.
- `15_a11y` treated an accessible *name* as present when only the **mechanism** was
  present (PR #211 review). `<label><input></label>`, `<label for="q"></label>` and an
  `aria-labelledby` pointing at an empty element all passed while announcing nothing;
  and `<a href="/tw"><svg role="img" aria-label="Twitter"></svg></a>` — the commonest
  icon-link idiom there is — was **flagged**, because only `<img alt>` was credited from
  inside a link. Names are now resolved from content: every element accumulates its
  subtree text plus the `alt`/`aria-label` of any descendant, and `aria-labelledby` is
  resolved (one level) after the parse.
- `15_a11y` let an `<svg><title>` satisfy the **default-on** `page_title` rule, so a page
  with no `<head><title>` at all passed if it contained one titled icon (pre-existing,
  undisclosed). Inside an `<svg>`/`<math>` subtree a familiar tag name is no longer taken
  for an HTML element — `<title>`, `h1`–`h6` and form controls are all namespace-aware,
  and HTML resumes at an integration point such as `<foreignObject>`.
- `15_a11y` read the HTML tree in three ways a browser does not (found in review of
  #159, and applying to the rules shipped in ADR-0045 as well): **duplicate attributes**
  resolved last-wins where the HTML parsing spec keeps the *first*
  (`<html lang="" lang="en">` was read as valid); **`<script>`/`<style>` source** was
  treated as rendered text, so a link containing only code looked named; and
  **`<template>` content** — inert until cloned — could supply a document's `<title>` or
  an enclosing link's name. Each is now resolved the way the DOM would, with tests in
  both directions.
- `15_a11y` reported `pass` for a project with no HTML at all — a hollow green (#154).
  Under ADR-0049 a check that inspected nothing must say so: it now exits 3 ⇒ `noop`,
  the log names what was searched (git-tracked `*.html/*.htm/*.xhtml`, minus
  `[a11y].exclude`) and where, and the gate output counts it under `inspected NOTHING`.
  Clean HTML ⇒ `pass`, violations ⇒ `fail`, unchanged. The HTML walk now mirrors
  `01_source_coherence`: a `git ls-files` failure inside a repo **fails closed** (never a
  `noop`), and a non-git project falls back to a filesystem walk (honouring `exclude`) and
  evaluates what it finds. Locked down by an integration suite
  (`tests/integration/test_a11y_gate.py`) driving `verify.sh` on every fixture.

### Added
- Honest no-op status + source-coherence guard + self-status (ADR-0049) — the fix for a
  **hollow green**. A governed project reported `ok: true`, 12/12, while seven of those
  checks had inspected *nothing*: `src_dir` pointed at a missing `src/` and the real code
  lived in `tools/`. Root cause: `_lib.sh` derived status from the exit code alone, so "I
  inspected nothing" and "I inspected everything and it's clean" were indistinguishable
  (`50_security` was worst — `bandit -r src` on a missing dir exits 0 with *empty* output).
  Four parts: (1) a fourth receipt status **`noop`** (`emit_noop`, plus exit code 3 as the
  heredoc→bash signal), surfaced in the gate output (`inspected NOTHING: N of M`), the
  persisted verdict and its history; (2) **fail-closed by allowlist** —
  `verdict.NON_FAILING_STATUSES` / `is_failing()` replace the old `status != "pass"`
  negation, so an unknown/typo'd/forged status still fails (regression-tested), and
  `status_assess` no longer mislabels a `noop` check as *failed*; (3) **`01_source_coherence`**,
  which fails the gate when a declared source path resolves to nothing *while tracked
  source exists elsewhere*, naming where the code actually is — genuine greenfield stays
  green as `noop`, and untracked files never fail a gate; (4) **self-status**: `status.sh`
  now reports **this project** by default (governed? enforcement AUTO/PARTIAL/MANUAL? last
  verdict? how many checks were hollow?), with the `$HOME` portfolio roster demoted to
  opt-in `--all`, plus a `borromeanrings-status` skill so any session can be asked "check
  my borromeanRings status". Enforcement is detected by hook *script name*, not path, so a
  self-governing repo isn't misreported as unenforced. Unit- + integration-tested
  (misconfigured fixture gates red; greenfield gates green-as-noop; correctly-configured
  passes for the right reason). Remaining vacuity in `05_hygiene`/`07_layout`/`09_commits`
  is documented as deferred in the ADR — the hollow count is a floor, not a total.
- Harness versioning + per-run version stamping (ADR-0048): a top-level `VERSION` file
  (`0.1.0`) as the human-declared release marker, and every gate run now records **which
  borromeanRings governed it**. `verify.sh` computes `HARNESS_VERSION` from
  `git describe --tags --always --dirty` on `BORROMEANRINGS_HOME` (honest about
  dirty/ahead-of-tag state), falling back to `VERSION`. It's printed in the gate output
  (`harness-version:`), carried on the persisted `Verdict` (new `harness_version` field →
  `last_verdict.json` + `verdict_history.jsonl`, back-compatible default `""`), and written
  as `harness_version.txt` into the receipt bundle. Answers "is it stable / which version
  verified this project?". Surfacing it as a `status.sh` column is a deferred follow-up.
- Checks catalog (`docs/CHECKS.md`): the single reference for **every** check (all 27 across
  the shared / Python / heavy-CI lanes) — what each enforces, its `borromeanrings.toml`
  config keys, its lane, whether it's a threshold-free ratchet, and its ADR. Plus how to
  enable a check (`init.sh`/`adopt.sh`/manual) and how to opt a project into *automatic*
  governance (the per-project hooks model). Closes the "how do I know how to use all its
  features" gap.
- Effectiveness ledger (ADR-0047): `ledger.sh` + `meta_harness.ledger` + append-only
  verdict history — answers "is governing this project actually *catching* anything?"
  (which `status` can't). `verify.sh` now appends each run's `Verdict` to
  `.meta-harness/verdict_history.jsonl` (best-effort, alongside the last-verdict write);
  `read_history`/`append_history` are fail-soft (missing → `[]`, bad lines skipped).
  `ledger.sh [PATH ...]` renders per project: gate RUNS, failures CAUGHT (the gate is
  load-bearing, not decorative), and current pass/fail STREAK, plus a portfolio tally.
  Reuses `discover_projects` + the gate's own verdict; pure core, unit-tested (100%),
  threshold-free (counts + streak, no score). Ratchet-baseline movement deferred to a
  follow-up.
- Portfolio status / roster view (ADR-0046): `status.sh` + `meta_harness.status` +
  `meta_harness.verdict` — the missing view *across* governed projects. One table shows,
  per project: git-or-not, required-check count, last gate verdict
  (`pass`/`fail`/never-gated), config drift (uncommitted `borromeanrings.toml`), and
  adoption drift (recommended checks not yet required, via `plan_adoption`). The gate
  now persists a compact last-known `Verdict` to `.meta-harness/last_verdict.json`
  (best-effort — a write failure never turns a PASS into a FAIL); `status` reads it, so
  the default view is instant. `--run` re-gates each project first (authoritative,
  CI-usable exit); `--list` prints paths. Reuses the single sources of truth
  (`load_config`, `plan_adoption`/`RECOMMENDED`, the gate's own verdict) — no duplicated
  policy. Threshold-free (a per-project table, not a blended score). Unit-tested (100%,
  23 cases) + dogfooded on the maintainer's real 10-project portfolio.
- Static accessibility (a11y) invariants gate (ADR-0045): `15_a11y` +
  `meta_harness.accessibility` — the deterministic, threshold-free slice of matrix #6
  (Product/UX). Native stdlib `html.parser` scan of tracked `*.html`/`*.htm`/`*.xhtml`
  (minus `[a11y].exclude`) reports WCAG-cited violations for a per-project rule set
  `[a11y].require`: `html_lang` (a full document declares a non-empty `<html lang>` —
  WCAG 3.1.1), `img_alt` (every `<img>` carries an `alt`; `alt=""` allowed — WCAG
  1.1.1), `page_title` (a full document has a non-empty `<title>` — WCAG 2.4.2).
  Document-level rules gate on the presence of `<html>`, so HTML *fragments* are never
  falsely flagged. No tracked HTML ⇒ pass. Dogfooded on **fire** (Electron; five
  renderer pages, *all* missing `<html lang>` — the justified need); borromeanRings has
  no HTML so it does not declare the check. Threshold-free (no Lighthouse-style score);
  rendered a11y (contrast/ARIA/focus) is deferred to a future heavy lane. Unit-tested
  (11 cases) + adversarially verified.
- Container (Dockerfile) hygiene gate (ADR-0044): `14_container` +
  `meta_harness.container` — the deterministic, threshold-free slice of matrix #4
  (SRE / operational). Native stdlib Dockerfile parse (multi-stage, line-continuations,
  comments, registry `host:port`, digests) reports violations for a per-project rule
  set `[container].require`: `non_root` (final stage must end on a non-root `USER`),
  `pinned_base` (external `FROM` pins a non-`latest` tag or digest; `scratch`/`$`-var
  exempt), `healthcheck` (a `HEALTHCHECK` is declared). No Dockerfile ⇒ pass. A
  run-and-exit gate-runner omits `healthcheck`; a service keeps the full set. Fixes
  borromeanRings's **own** image (was root — added a non-root `USER`) and dogfoods
  `["non_root", "pinned_base"]` on it; the full set is validated against AutoApply's
  real service Dockerfile (flags its missing HEALTHCHECK). Unit-tested (13 cases) +
  adversarially verified.
- ADR-discipline gate (ADR-0043): `13_adr` + `meta_harness.adr_discipline` — on a
  feature branch (name starts with `[adr].require_prefixes`, default `feat/`), a
  change that touches `src` must also add/modify an ADR under `[adr].dir`
  (`docs/adr/`), so a new capability can't land with no recorded decision. Fills
  coverage-map rows D/H; deterministic, threshold-free, git-derivable (merge-base
  diff, `--relative` so it works for git-root and subdir projects). The buildable,
  no-telemetry slice of the delivery/process matrix. Native, unit-tested +
  adversarially verified.
- Secret-scanning completeness (ADR-0042): `74_secret_history` (heavy lane) scans
  every blob reachable from any ref for high-confidence secrets — a
  committed-then-deleted secret still lives in history and is compromised.
  Reachable-only (dangling objects excluded), fail-closed, deduped by a one-way
  fingerprint (the secret is never emitted); acknowledge rotated/benign findings
  via `[secrets].history_allow`. Native (`meta_harness.secret_history`),
  unit-tested + adversarially verified. Also hardens `12_secrets` to **fail
  closed on a non-git directory** (was a vacuous pass — found in rollout).
- Adoption helper for existing projects: `adopt.sh` + `meta_harness.adopt` —
  migrates a project already governed at the founding baseline onto the newer
  quality/security checks. Plans the missing recommended set (`12_secrets`,
  `11_changelog`, `32_complexity`, `33_coupling`, `45_docstrings`), seeds each
  ratchet's baseline from current state, creates a `CHANGELOG.md` if needed, and
  rewrites `[checks].required` in place. Idempotent, native, no installs.
  Complements `init.sh` (new projects); piloted on `reliefq` 7 → 12 checks green
  (ADR-0041).
- Public-API breaking-change detection: `34_api_diff` — diffs the public
  surface vs the merge-base; a removed symbol / removed-renamed param / new
  required param fails unless `[api].allow_breaking=true`. Native ast+git,
  dogfooded on `examples/textkit` (ADR-0040).
- Example governed project: `examples/textkit` — a small library (different
  archetype) with its own `borromeanrings.toml`, governed by borromeanRings's
  gate end-to-end (11 checks). Proves the 'any project' portability claim; a
  permanent integration test asserts its gate passes.
- Coupling ratchet: `33_coupling` — worst-case efferent coupling (fan-out) over
  the internal module graph, non-regression, native (ADR-0038).
- Critic activation: `scripts/critic-judge.sh` (provider-agnostic, fail-closed
  judge — claude CLI or ANTHROPIC_API_KEY) + `docs/CRITIC-ACTIVATION.md`; the
  Wave-2 critics are now one config line from live (ADR-0030/0036).
- Agent-enhancement recommender (advisory): `meta_harness.enhancements` — a
  curated, maintainer-verified catalog of open-source tools that improve the
  *wrapped agent* (model routing, MCP servers, observability, caching), with a
  `[enhancements].interests` filter. Proposes, never gates (ADR-0037).
- **Enforcement-coverage program** — turning the SWE best-practice matrix into
  real gates:
  - Adversarial self-test corpus: the gate must reject known-bad and accept
    known-good (ADR-0025).
  - Tamper-evident receipts: content digest + fail-closed verdict, run-digest
    anchor (ADR-0026).
  - Native import-direction architectural fitness: `leaves` / `private` /
    `forbidden` / `forbid_cycles` contracts over the internal module graph
    (ADR-0027).
  - Changelog discipline (this check): presence + `Unreleased` section, with an
    opt-in strict "entry on source change" rule (ADR-0028).
  - Native secret scanning: high-confidence provider tokens + private keys in
    tracked files, fail-closed, `allow-secret` escape hatch (ADR-0032).
  - Docstring-coverage ratchet: native, non-regression, no absolute target
    (ADR-0029).
  - Wave-2 critic rubrics (advisory): `56_critics` judges functions against
    error-handling / naming / security / boundary-value / test-smell rubrics
    via a live model judge; a DRY registry over the doc-drift machinery,
    dormant until `[critic].judge_command` is wired (ADR-0036).
  - Doc-drift critic: first live application of the T2 seam — a model judge
    external to the generator checks docstrings against code; advisory-first,
    opt-in via `[critic].judge_command` (ADR-0030).
  - Cyclomatic-complexity ratchet: native McCabe, worst-case non-regression, no
    absolute ceiling (ADR-0031).

  - Mutation-score ratchet (heavy): `60_mutation` runs mutmut in CI and
    ratchets assertion strength vs `.borromeanrings-mutation-baseline`
    (0.80; current 0.83), fail-closed on 0-evaluated (ADR-0022).
  - License compliance (heavy): `72_licenses` runs pip-licenses in CI and
    denies incompatible copyleft (`[licenses].deny`), with `allow_packages`
    exceptions (ADR-0035).
  - Dependency CVE audit (heavy): `70_pip_audit` runs pip-audit in CI and
    fails on known vulnerabilities; base tooling / accepted CVEs ignorable
    via `[audit]` (ADR-0034).
  - CI-tier heavy lane: `verify.sh --heavy` runs + requires `checks/ci/`
    (`[checks].heavy`), the home for expensive tool-checks; landed dormant
    (ADR-0033).

### Changed
- Enforcement-coverage map corrected to reality: coverage-ratchet was mis-claimed
  ✅ but no check exists (now ❌ candidate); coupling (`33_coupling`), public-API
  breaking-change (`34_api_diff`), and the adoption path (`adopt.sh`) marked ✅;
  doc-drift noted as activation-paused (agent-only, no API keys); added §6 for the
  other governance matrices (security, DORA, SRE, data/ML, product/UX).
- Grouped `tests/` into `unit/` (23) + `integration/` (5 shell-out tests); layout
  threshold back to 15; mutmut ignore paths updated; retires the 30 workaround.
- Enforcement-coverage map refreshed to reflect the shipped suite (T1 filled,
  T2 critic seam + rubric family live-advisory); honest scorecard updated.
- Changelog strict rule (`require_entry_on_src_change`) turned **on** now the
  PR queue has cleared (ADR-0028).

### Notes
- Earlier increments that are in review: mutation-score ratchet (ADR-0022),
  external rubric-critic seam (ADR-0023), project profiler (ADR-0024), and the
  enforcement-coverage map.
