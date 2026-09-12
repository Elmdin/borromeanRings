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

### Security
- Gate no longer self-certifies via a planted stdlib name (ADR-0080, #222). `verify.sh`
  ran its trusted Python (verdict aggregation, language detect) and `checks/_lib.sh` ran
  `emit_receipt` / `borromeanrings_project_cfg` from `PROJECT_ROOT` — putting the
  governed project first on `sys.path`, so a `json.py` committed at the repo root could
  shadow stdlib and make `bash verify.sh` (what CI runs) print `RESULT: PASS` and exit 0
  on a failing tree, forging the required `gate` check. New `checks/_py.sh` defines
  `borromeanrings_py` (runs Python from `/` with `PYTHONPATH` at borromeanRings' own
  `src`, plus `PYTHONNOUSERSITE=1` so a user-site `usercustomize.py` cannot forge the
  verdict either — #224 review; mirrors #221's hook helper); the four named calls plus
  every verdict-deciding analysis heredoc (`05`–`15`, `32`–`35`, `45`, `55`, `56`, `74`)
  and `00_build`'s stdlib `compileall` step now route through it. Deliberately not
  `python3 -P`/`-I` (3.11-only / drops `PYTHONPATH`). Tool runs that execute project code
  by design (`pytest`, `mypy`, `mutmut`, `pip-audit`, `pip-licenses`, and `00_build`'s
  `import <package>` half) are left as-is — already untrusted per #218, blocked on M7.
  This closes the project-directory shadow completely and the user-site vector; it is not
  full interpreter isolation. The Stop-hook half of #222 (forged `last_green_state`, hook
  markers) also remains, on M7.
### Fixed
- The Stop hook's retry count could be reset by deleting a file (#218, ADR-0079). It lived
  in `.meta-harness/stop_attempts/`, inside the project, and a missing file read as `0`. It
  now lives under `${XDG_STATE_HOME:-$HOME/.local/state}/borromeanrings/<project-digest>/`,
  keyed by the project's resolved path, via the new `meta_harness.retry_state` (pure, 100%
  unit-tested). This resists accident and a naive reset: tidying `.meta-harness/`, deleting
  the counter or writing `0` into it no longer buys attempts. It is **not** a bound against
  intent: the gate runs the project's own tests as the user, so a `conftest.py` can still
  delete the count, as can any same-user process; only an isolated test run closes that.
  Keyless. Fails closed: a broken or unusable state directory, one that resolves inside the
  project, or a symlink on the old in-tree path now escalates to the human instead of
  silently counting from zero. The old in-tree count is carried over with `max()`, walked
  without following symlinks, then removed. The headless driver from #217 must adopt the
  same module when it lands.
- Hooks no longer import modules from the governed project. They run from the project
  directory, where `python3 -c` put a planted `json.py` ahead of the standard library; the
  Stop hook's payload parse imported one and got a fresh session id on every Stop. Every
  hook now starts Python through `borromeanrings_py` (`.claude/hooks/_lib.sh`), which runs
  it from `/`. Not `-P`, which needs Python 3.11 against `requires-python = ">=3.10"`.
### Deprecated
- The pre-rename config file name `borromeo.toml` (issue #62). It still loads —
  `meta_harness.spine.resolve_config_path` falls back to it when `borromeanrings.toml`
  is absent and prints a `FutureWarning` to stderr (once per process per legacy file;
  shown by Python's default filters, which a `DeprecationWarning` is not). Visible from
  `verify.sh` (its own notice on every run), `status.sh`, `ledger.sh`, the Stop and
  UserPromptSubmit hooks; the PreToolUse branch guard swallows stderr by design and stays
  silent but still governs — so no already-governed project falls out of governance. Migrate with `git mv borromeo.toml borromeanrings.toml`.
  The `meta_harness` package and the `.meta-harness/` evidence directory are deliberately
  NOT renamed (receipts, baselines, mutmut config and import paths depend on them).

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
- `docs/RENAME.md` (issue #62): the borromeo -> borromeanRings rename tail — what was
  renamed, what deliberately was not and why, and the exact commands to fix a local
  clone's remote URL, re-run `install-global.sh`, and refresh the GitHub label
  descriptions that still say "borromeo".
### Changed
- Enhancement catalog health-audited (#133): entries carry `maintained_as_of` / `needs_api_key` / `applies_to`, `recommend()` filters by substrate, RouteLLM (dead) and OmniRoute (search-query URL) removed, Serena / Repomix / ast-grep / pyright-lsp added.

### Added
- Issue forms, PR template, and label scheme (closes #61): YAML issue forms for bug
  report (repro, expected/actual, gate output + receipt path, `harness-version`),
  feature request (user story, acceptance checkboxes, quality attributes, the check
  that would enforce it, ADR/milestone fit) and research/spike (question, sources,
  deliverable under `docs/research/`); blank issues disabled, vulnerabilities routed to
  the private advisory. `PULL_REQUEST_TEMPLATE.md` now mirrors the real definition of
  done (fast gate, `--heavy` with `60_mutation`/`74_secret_history`, sub-agent review
  on the PR, ADR/CHANGELOG/spec when applicable, no new CI/packaging, subject ≤ 72).
  `docs/LABELS.md` documents the label + milestone vocabulary reconciled with the
  labels that exist; `scripts/labels.sh` (idempotent, `--dry-run`, shellcheck-clean)
  applies it — run by a human on purpose, never by a hook.
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
