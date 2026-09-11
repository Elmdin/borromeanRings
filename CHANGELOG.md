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

### Fixed
- Git-identity guard hardened against per-command overrides and exotic invocations
  (closes #54). Two independent holes, both preventive-layer only (check `06_git_identity`
  remained the backstop). **(1) Overrides were invisible.** The guard compared the repo's
  *configured* identity, but git accepts an identity per invocation — `--author=`,
  `-c user.email=`, and the `GIT_AUTHOR_*`/`GIT_COMMITTER_*` environment variables — none
  of which config-comparison can see, so a correct repo could still produce a
  wrong-authored commit. **(2) Detection was a substring match.** Keying on the literal
  `"git commit"` misses every spelling that puts something between the two words
  (`git -c … commit`, `git -C dir commit`, `VAR=value git commit`) — so those invocations
  skipped the identity *and* protected-branch guards entirely. New `git_subcommand()`
  parses the real subcommand, stepping over leading environment assignments and git's
  global options; `command_override_violation()` compares any declared override against
  the required identity, allows one that states the correct identity (being explicit is
  not evasion), and refuses an override it cannot parse rather than failing open. Both
  guards now key off the parsed subcommand. Scoped so it only ever fires on a real
  `git commit`/`push`: a script or heredoc that merely mentions git is not a commit.
  Verified end to end against all four evasion paths through the hook's own stdin
  protocol, with negative controls.
  Those hook tests now run against a throwaway governed project (configured identity =
  declared identity, HEAD on a work branch) instead of the harness checkout: CI's checkout
  has no `user.name`/`user.email`, so the configured-identity rule denied every commit
  there — failing the negative control and letting the override test pass for the wrong
  reason. The override test now also asserts the denial came from the override rule.
- `merge.sh` now merges the **governed project**, not borromeanRings itself (closes #121).
  It unconditionally `cd`-ed into `BORROMEANRINGS_HOME`, so invoking it from a governed
  project checked *borromeanRings's* working tree for dirtiness and would have merged
  *borromeanRings's* branches — the wrong repository. Found in the field: an untracked file
  in the harness blocked a clean merge in another repo. `verify.sh` has always honoured
  `BORROMEANRINGS_PROJECT`/`CLAUDE_PROJECT_DIR`; `merge.sh` now resolves the same two roots
  (ADR-0013) and runs every git/`gh` call, the gate, the policy check and the audit receipt
  against `PROJECT_ROOT`, while loading harness code from `BORROMEANRINGS_HOME`. It also
  refuses outright when the target has no `borromeanrings.toml`. Regression-tested against
  a real fixture repo with a local bare origin; both tests fail against the pre-fix script
  with the exact symptom from the report.

### Added
- Shell lint gate (ADR-0050, closes #52): `16_shellcheck` lints the project's own shell,
  **fail-closed on any finding at any severity**. borromeanRings is 43 scripts / ~2.8k lines
  of bash and that bash IS the trust root — the gate itself, every check, the four Claude
  hooks — yet it was the one part of the codebase nobody linted while the Python beside it
  faced twenty checks. Running it found five issues, **two of them real defects**:
  `scripts/critic-judge.sh` piped its prompt into `python3 - <<'PY'`, where the heredoc
  overrides the pipe, so `sys.stdin.read()` returned `""` and the API-key judge path was
  sending an **empty prompt** to the model (SC2259); and `pre_bash_guard.sh` carried a dead
  `case` alternative in the dangerous-command guard, unreachable because an earlier pattern
  subsumed it (SC2221/SC2222). Both fixed, plus an unchecked `cd` in `merge.sh` (SC2164) and
  a missing shell directive. Design notes: sources are **resolved, not suppressed** — `-x`
  with `[shell].source_paths` (`SCRIPTDIR`) clears all 33 SC1091 notes that a blanket
  `-e SC1091` would have muted along with real unreadable-source bugs; the file list is
  git-tracked shell (an untracked scratch script never fails a gate) with a filesystem-walk
  fallback; no shell ⇒ `noop`, not a hollow pass; and **no `xargs`**, which would split a
  long list across invocations and report only the last exit code. `shellcheck-py` is added
  to the dev extras so CI needs no apt step. A missing shellcheck is `error`, never a skip.
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
