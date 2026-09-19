# Repository Hygiene Audit (Phase 0)

> **STATUS: committed deliverable for issue #74** ("Audit GitHub Actions, CI/CD,
> workflows, and repository settings"). Audited 2026-08-14; re-verified and landed
> 2026-08-28.
>
> The §4 reconcile below was *proposed* when this was drafted and has since been
> **carried out with maintainer approval**: issues #55, #56, #57 and #63 are closed
> as already-shipped, and #60 is narrowed (see its comments). No repository
> *settings* were changed — the `enforce_admins` gap in §2 remains a recommendation
> awaiting a decision. Sections 2, 3 and 5 record verified state at the dates above;
> re-check the live API before relying on them.

## 1. Executive summary

The repository is **not** at "basics" — it already carries mature SE scaffolding:
33 well-formed issues, 22 labels, 4 milestones, issue/PR templates, three CI
workflows (gate + CodeQL + Dependency Graph), branch protection on `main` **and**
`dev` (required `gate` check + linear history + 1 required review), 46 ADRs, 31
specs, 100% coverage + a mutation ratchet, native secret scanning, and a security
policy. The disciplined move is therefore **reconcile + fill narrow gaps**, not
re-scaffold.

**Cost posture: healthy.** Public repo ⇒ Actions minutes are free; no paid
packaging, no registry publish, no scheduled jobs. Only one mild redundancy (heavy
gate double-runs on PR then post-merge push) is worth trimming.

## 2. Branch protection (verified via API)

| Control | `main` | `dev` | Assessment |
|---|---|---|---|
| Required status check | `gate` | `gate` | ✅ present; CodeQL is **not** required (advisory only) |
| Required approving reviews | 1 | 1 | ✅ |
| Linear history | on | on | ✅ |
| Strict / up-to-date before merge | on | on | ✅ |
| Force pushes / deletions | off / off | off / off | ✅ |
| Require CODEOWNER review | off | off | ⚠ no CODEOWNERS file exists |
| Dismiss stale approvals | off | off | ⚠ optional hardening |
| Require conversation resolution | off | off | ⚠ optional hardening |
| Enforce for admins | off | off | ⚠ admins can bypass |

## 3. CI/CD & cost audit

- **Workflows:** `verify.yml` (the `gate`), CodeQL (GitHub default setup),
  Dependency Graph. No cron/scheduled runs. No build/publish/packaging steps.
- **Triggers:** `verify.yml` fires on every `pull_request` **and** on `push` to
  `main`/`dev`, running `verify.sh --heavy` (includes mutation testing ≈ minutes).
- **Redundancy (the one real waste):** after a PR squash-merges to `dev`, the
  resulting `push` to `dev` re-runs the full **heavy** gate that already passed on
  the PR head. → *Recommendation:* keep `pull_request` (validates the change) and
  restrict the `push` heavy run to `main` only (release verification), or dedupe by
  concurrency. Saves ~one heavy run per merge; correctness unaffected.
- **No unnecessary packaging.** Nothing publishes artifacts or images in CI.
- **$ cost = 0** (public repo, free minutes). This is compute-hygiene, not billing.

> **API note (cost us a wrong reading once).** The aggregate
> `GET /branches/main/protection` response **omits** `required_pull_request_reviews`
> entirely, which reads as "no reviews required". The dedicated
> `/protection/required_pull_request_reviews` endpoint is authoritative and reports
> `required_approving_review_count: 1`. Always check the sub-endpoint.

## 4. Issue reconcile (verified done → propose CLOSE)

| # | Title | Evidence it's done |
|---|---|---|
| 60 | Branch protection on main (require the gate) | gate required + linear history + 1 review (§2). **Narrowed, not closed:** `enforce_admins: false` still lets an admin bypass the gate |
| 56 | Add SECURITY.md + disclosure policy | `.github/SECURITY.md` present |
| 63 | CONTRIBUTING.md | `.github/CONTRIBUTING.md` present |
| 57 | Secrets scanning in gate and CI | `12_secrets` + heavy `74_secret_history` |
| 55 | Mutation testing | `60_mutation` heavy ratchet (baseline 0.80) |

**Partial (keep open, narrow scope):**
- **#61** templates/CODEOWNERS/label & milestone scheme — templates ✅, labels ✅,
  milestones ✅; **only CODEOWNERS remains**. Narrow the issue to CODEOWNERS.
- **#58** dependency & supply-chain hardening — Dependency Graph + CodeQL + heavy
  `70_pip_audit` + `72_licenses` exist; verify residual scope then likely close.

**Genuinely open (unchanged):** #52 shellcheck gate (no shellcheck check exists),
#75 trunk-based branching enforcement, #74 (this audit).

## 5. Planning gaps

- **5 open issues have no milestone:** #32, #69 (roadmap epic — fine unassigned),
  #79, #80, #81. → Assign #79/#80/#81 (feature ideas) to a milestone or a `backlog`
  milestone so nothing is untracked.
- **M1 "Pre-public hardening" is nearly complete** once §4 closures land (remaining:
  #58 verify, #59 exposure review, #66 README polish, #74 this) — worth a milestone
  review.

## 6. Documentation gaps (Phase 1 candidates — in-repo, via feat→PR→gate→review)

| Gap | Why it matters | Maps to |
|---|---|---|
| `docs/QUALITY-ATTRIBUTES.md` | The `-ilities` + priority order (correctness → security → maintainability → performance) aren't in one authoritative doc mapping each to its enforcing gate | user request |
| `CODE_OF_CONDUCT.md` | Community-health file; GitHub surfaces it | #65 / M4 |
| `.github/CODEOWNERS` | Enables CODEOWNER-required reviews (§2) | #61 |
| Definition-of-Done / acceptance-criteria convention | Specs exist per-feature; no single DoD contract | user request |

Present docs already covering the user's list: `docs/ARCHITECTURE.md` (system
design), 46 ADRs (design patterns/principles/decisions), 31 specs (per-feature
contracts), `docs/ROADMAP.md`, `docs/ENFORCEMENT-COVERAGE.md`.

## 7. Recommended settings changes (Phase 2 — OUTWARD-FACING, needs explicit OK)

1. Add `.github/CODEOWNERS`, then enable `require_code_owner_reviews` on `main`/`dev`.
2. Set `deleteBranchOnMerge = true` (auto-tidy merged feature branches).
3. Restrict merge methods to **squash-only** (match Gitflow-lite; disable merge-commit + rebase).
4. Consider `enforce_admins`, `required_conversation_resolution`, `dismiss_stale_reviews` on protected branches.
5. Consider adding CodeQL as a **required** status check (currently advisory).
6. Trim the heavy-gate double-run (§3).

None of §7 is applied yet. Nothing here is committed or pushed.
