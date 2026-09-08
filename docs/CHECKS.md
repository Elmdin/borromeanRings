# borromeanRings — Checks Catalog

The single reference for **every check borromeanRings can enforce**, what each one
guarantees, how to turn it on, and how it's configured. If you want to know "what features
exist and am I using them", this is the page. Companion docs: `docs/ENFORCEMENT-COVERAGE.md`
(how checks map to the SE best-practice matrix) and `docs/ARCHITECTURE.md` (how the gate is
built). Each check's rationale lives in its ADR (`docs/adr/`).

## How governance works (30 seconds)

- **By reference.** A governed project doesn't copy borromeanRings; it *invokes* the on-disk
  code at `BORROMEANRINGS_HOME` — via Claude hooks (automatic) or `./verify.sh` (manual).
- **Fail-closed.** The gate exits `0` only if **every required check** produced a
  non-failing receipt. A missing receipt, a failed check, or a tampered receipt ⇒ FAIL.
  Non-failing is an explicit allowlist (`pass`, `noop`), never "anything but fail", so an
  unknown or forged status still fails (ADR-0049).
- **Four statuses, and `noop` matters.** `pass` (inspected something, found nothing wrong) ·
  `noop` (**ran but inspected NOTHING** — no source yet, no Dockerfile, rule not declared) ·
  `fail` · `error` (tool missing). A run that leans on `noop` checks prints
  `inspected NOTHING: N of M`, because a green resting on checks that looked at nothing
  proves less than it appears to. `./status.sh` surfaces the same count.
- **Evidence.** Every run writes tamper-evident receipts to
  `<project>/.meta-harness/receipts/<run_id>/`, a compact `last_verdict.json`, and appends to
  `verdict_history.jsonl`. Each run is stamped with the governing `harness-version`
  (ADR-0048).
- **Two lanes.** The **fast lane** runs on every gate; the **heavy (CI-tier) lane** runs only
  under `./verify.sh --heavy` or in CI — expensive tool-checks that must not slow the inner
  loop (ADR-0033).
- **Opt-in, per check *and* per project.** Nothing is enabled by default; you choose.

## Enabling checks in a project

Checks a project runs are declared in its `borromeanrings.toml`:

```toml
[checks]
required = ["00_build", "10_format", "40_test", ...]   # fast lane — gates every run
heavy    = ["60_mutation", "70_pip_audit", ...]        # heavy lane — gates under --heavy / CI
```

- **New project:** `./init.sh <path>` writes a starter `borromeanrings.toml` + the hook wiring.
- **Existing project:** `./adopt.sh <path>` adds the recommended quality/security set
  (`12_secrets, 11_changelog, 32_complexity, 33_coupling, 45_docstrings`), seeds each ratchet
  baseline from the current state, and rewrites `[checks].required` (idempotent — ADR-0041).
- **Manually:** add the check ID to `[checks].required` (or `heavy`) and provide any config it
  needs (below). Ratchet checks also need their baseline file seeded.

## Opting a project into *automatic* governance (per-project model)

Governance is **per-project opt-in**: there is no global auto-enforcement. A project runs the
gate automatically only if its own `.claude/settings.json` wires the hooks. `./init.sh` writes
exactly that block — four hooks pointing at `$BORROMEANRINGS_HOME/.claude/hooks/`:

| Hook | Fires on | Effect |
|------|----------|--------|
| `UserPromptSubmit` | every prompt | injects the prompt-rewrite / context directive |
| `Stop` | end of a turn | runs the gate; blocks on FAIL |
| `PostToolUse` (Edit/Write) | after edits | auto-formats changed files |
| `PreToolUse` (Bash) | before shell | guards protected-branch commits |

Without that block, the project is *enrolled but dormant* — the gate runs only when you type
`./verify.sh`. (borromeanRings itself is governed this way, via its own project-local hooks.)

---

## Fast lane — shared checks (language-agnostic)

| Check | Enforces | Config (`borromeanrings.toml`) | ADR |
|-------|----------|--------------------------------|-----|
| `05_hygiene` | The engineering surround exists (README, LICENSE, CI dir, …) | `[hygiene].requires` | 0012 |
| `06_git_identity` | Commits unique to the branch are authored by the declared identity | `[git].name`, `[git].email` | 0019 |
| `07_layout` | Repo layout: specs live under `specs_dir`; only allow-listed `.md` at root; test grouping past a threshold | `[layout].specs_dir`, `root_doc_allowlist`, `test_grouping_threshold`, `test_groups` | 0018 |
| `08_branch` | Work branch matches an allowed pattern; a protected branch carries no commits its remote ref lacks (direct commits fail; the PreToolUse guard is the preventive layer) | `[collaboration].branch_patterns`, `protected_branches` | 0021, 0058 |
| `09_commits` | Commit messages are typed + within the subject length | `[collaboration].commit_types`, `subject_max_length` | 0021 |
| `11_changelog` | `CHANGELOG.md` exists with an `Unreleased` section; optionally an entry on every source change | `[changelog].enabled`, `path`, `require_entry_on_src_change` | 0028 |
| `12_secrets` | No high-confidence provider tokens / private keys in tracked files; **fails closed on a non-git dir** | (scan; escape hatch inline) | 0032 / 0042 |
| `13_adr` | On a feature branch, a change touching `src` must add/modify an ADR | `[adr].dir`, `require_prefixes` | 0043 |
| `14_container` | Dockerfile hygiene: non-root final user, pinned base, healthcheck | `[container].dockerfile`, `require` | 0044 |
| `15_a11y` | Tracked HTML declares `<html lang>`, `<img alt>`, `<title>` (WCAG 3.1.1/1.1.1/2.4.2) | `[a11y].require`, `exclude` | 0045 |

## Fast lane — Python checks

| Check | Enforces | Config / notes | ADR |
|-------|----------|----------------|-----|
| `00_build` | Source compiles and the declared package imports cleanly | `[project].package`, `src_dir` | — |
| `01_source_coherence` | **Fails** when the declared source path resolves to no files *while tracked source exists elsewhere* — the misconfiguration that makes every source-reading check pass vacuously. Genuine greenfield ⇒ `noop` | `[project].src_dir`, `package` | 0049 |
| `10_format` | No unformatted files (black) | toolchain | — |
| `20_lint` | No lint violations (ruff) | toolchain | — |
| `30_typecheck` | No type errors (mypy); greenfield with no source ⇒ `noop` | toolchain | — |
| `32_complexity` | **Ratchet**: worst-case cyclomatic complexity doesn't regress (no absolute ceiling) | baseline file, seeded by `adopt.sh` | 0031 |
| `33_coupling` | **Ratchet**: worst efferent coupling (fan-out) doesn't regress | baseline file | 0038 |
| `34_api_diff` | Public-API breaking change (removed/renamed symbol, new required param) fails unless allowed | `[api].allow_breaking` | 0040 |
| `35_architecture` | Import-direction fitness: leaves import no domain module, private modules stay unimported, no cycles | `[architecture].leaves`, `private`, `forbidden`, `forbid_cycles` | 0027 |
| `40_test` | Tests pass **and** coverage doesn't regress (**ratchet**, not an absolute %) | `[project].tests_dir`; coverage baseline | — |
| `45_docstrings` | **Ratchet**: public-API docstring coverage doesn't regress | baseline file | 0029 |
| `50_security` | No bandit findings at/above the configured severity in source | bandit severity | — |
| `55_doc_drift` | *(Advisory)* an external model judge checks docstrings against code | `[critic].judge_command` (dormant if empty) | 0030 |
| `56_critics` | *(Advisory)* model judge applies Wave-2 rubrics (error-handling, naming, security, boundary-value, test-smell) | `[critic].rubrics`, `judge_command` | 0036 |

## Heavy (CI-tier) lane — run under `./verify.sh --heavy` or CI only

| Check | Enforces | Config / notes | ADR |
|-------|----------|----------------|-----|
| `60_mutation` | **Ratchet**: mutation score (assertion strength beyond coverage) doesn't regress; fails on 0 evaluated | `.borromeanrings-mutation-baseline` (0.80) | 0022 |
| `70_pip_audit` | No known-vulnerable dependencies (pip-audit) | `[audit].ignore_packages`, `ignore_vulns` | 0034 |
| `72_licenses` | No incompatible copyleft licenses in the dependency tree | `[licenses].deny`, `allow_packages` | 0035 |
| `74_secret_history` | No high-confidence secret in **any** blob reachable from any ref (history, not just HEAD) | `[secrets].history_allow` | 0042 |

## Notes

- **Ratchets are threshold-free.** `32/33/40/45/60` enforce *non-regression* against a seeded
  baseline, never an arbitrary target number — you can only improve or hold, never silently
  slip. Move a baseline deliberately (a reviewed commit), never as a side effect.
- **Advisory checks** (`55_doc_drift`, `56_critics`) require a wired model judge
  (`[critic].judge_command`, e.g. the local `claude` CLI — no API keys). Empty ⇒ dormant; they
  never block until you opt in.
- **Version stamping.** Every gate run records the governing borromeanRings version
  (`git describe` of `BORROMEANRINGS_HOME`, or the `VERSION` file) in its output, its
  `last_verdict.json`, and a `harness_version.txt` in the receipt bundle (ADR-0048).
