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

### Changed
- Enhancement catalog health-audited (#133): entries carry `maintained_as_of` / `needs_api_key` / `applies_to`, `recommend()` filters by substrate, RouteLLM (dead) and OmniRoute (search-query URL) removed, Serena / Repomix / ast-grep / pyright-lsp added.

### Added
- Platform self-assessment (`docs/SELF-ASSESSMENT.md`, issue #51): how the gate, receipts,
  hooks, ratchets and lanes work with every claim cited; the defect-class table built from
  this cycle's 25 sub-agent PR reviews (#148–#185) plus the full-source licence sweep, and
  whether a mechanism or only review catches each class; gaps ranked fail-closed → vacuous evidence → matrix coverage →
  ergonomics; ten prioritised improvements with tracking issues (four newly filed:
  #186 fail-closed enumeration, #187 mutation-lane vacuity guard, #188 citation check,
  #189 license shingle check); the constraints honoured and where each is enforced.
- Toolchain pinning (ADR-0077): `[project.optional-dependencies].dev` pins with `==`
  every package that decides a verdict — the check tools, plus `coverage` (measures the
  ratchet) and `libcst` (generates mutmut's mutants). The rest of the closure stays free
  to resolve current, because pinning it froze four packages at versions with known CVEs
  and `70_pip_audit` correctly went red. `meta_harness.toolchain` + integration tests fail
  closed when the gate runs a version other than the pinned one, when a version cannot be
  read, when a `dev` requirement is not exact, or when a tool reachable from `checks/**.sh`
  has no pin. Each tool is observed through **the argv its check uses** (`ruff` from
  `PATH`, `pytest` via `python3 -m`), because those resolve to different installs on a
  machine with a user-site shim.
- CI prints the log of every check that did not pass, marking checks outside the required
  set as advisory. A red gate used to name the failing check and nothing else. Adding a check that
  invokes a new binary now also requires registering and pinning it; the failure message
  names the three steps.
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
