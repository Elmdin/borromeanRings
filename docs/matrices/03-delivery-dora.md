# Matrix #3 — Delivery / DORA

Scope: how change flows from a branch to the trunk to production — batch size, integration,
review, traceability and the four DORA outcome metrics. Rows D1–D8 are *process gates* the
repo can decide from git alone; D9–D13 are the *outcome metrics*, which need deploy or
incident telemetry the gate does not have. Conventions: [`README.md`](README.md).

| Row | Criterion (binary or ratchet) | Enforced by | Buildability | Source |
|---|---|---|---|---|
| D1 | Work happens on short-lived branches whose names match a declared pattern; protected branches receive merges only | ✅ `08_branch` (`[collaboration].branch_patterns`) + `pre_bash_guard.sh` (denies commit/push on a protected branch; ADR-0021) | now | DORA capability "Trunk-based development"; *Accelerate* (Forsgren, Humble, Kim 2018) ch. 4 |
| D2 | Every commit on the branch is a Conventional Commit with a declared type and a bounded subject length | ✅ `09_commits` (`[collaboration].commit_types`, `subject_max_length`) | now | Conventional Commits 1.0.0; Keep a Changelog 1.1.0 (derivability of the log) |
| D3 | The changelog exists with an `Unreleased` section and is updated whenever source changes on the branch | ✅ `11_changelog` (`[changelog].require_entry_on_src_change`; ADR-0028) | now | Keep a Changelog 1.1.0 ("Guiding principles") |
| D4 | A feature branch that touches source records an architecture decision (ADR added or modified) | ✅ `13_adr` (ADR-0043) | now | Nygard, "Documenting Architecture Decisions" (2011); DORA capability "Documentation quality" (2023 report) |
| D5 | The gate runs in CI on every pull request and every push to the trunk, with the same script a human runs locally | ✅ `.github/workflows/verify.yml` (`bash verify.sh --heavy` on `pull_request` and `push`; ADR-0008) + `05_hygiene` (requires `.github/workflows` to exist) | now | DORA capability "Continuous integration"; Fowler, "Continuous Integration" (2006) |
| D6 | A merge to the trunk happens only through an explicit, gate-passing command (fail-closed if the gate fails) | ✅ `merge.sh` (runs `./verify.sh`, refuses on failure; `meta_harness.merge_policy`, ADR-0007) | now | *Accelerate* ch. 4 (deployment pipeline as the only path to production) |
| D7 | Breaking public-API changes are detected against the merge-base and fail unless a major release is declared | ✅ `34_api_diff` (`[api].allow_breaking`; ADR-0040) | now | Semantic Versioning 2.0.0 §8 (major version on incompatible change) |
| D8 | Branch commit authorship matches the declared identity (provenance travels with the commit) | ✅ `06_git_identity` (opt-in per project; omitted on this public repo by ADR-0019) | now | SSDF PS.1; DORA "Version control" capability |
| D9 | **Batch size ratchet**: the largest change set on the branch (files or lines vs merge-base) may not exceed the recorded baseline — threshold-free, git-derivable | gap → #156 | now | DORA capability "Working in small batches"; *Accelerate* ch. 4; Google Engineering Practices, "Small CLs" |
| D10 | **Deployment frequency**: every deploy is recorded with commit and timestamp; the recorded cadence may not regress vs baseline | gap → #156 (telemetry sub-issue) | telemetry | DORA "Four keys" — *Accelerate* ch. 2; DORA State of DevOps Report 2023 (metric definitions) |
| D11 | **Lead time for changes**: commit-to-deploy interval is recorded per deploy and the rolling value may not regress vs baseline | gap → #156 | telemetry (needs D10's deploy record) | *Accelerate* ch. 2; DORA 2023 |
| D12 | **Change failure rate**: each deploy is marked failed/ok from incident linkage; the rolling rate may not regress vs baseline | gap → #156 | telemetry | *Accelerate* ch. 2; DORA 2023 |
| D13 | **Failed-deployment recovery time** (formerly MTTR): time from a failed deploy to restoration is recorded; the rolling value may not regress | gap → #156 | telemetry | DORA State of DevOps Report 2023 ("failed deployment recovery time" replaces MTTR) |
| D14 | Every PR receives an independent review whose findings are recorded on the PR before merge (a separate agent counts; the author's own session does not) | ⚠️ process rule (`docs/HANDOFF.md` §2 item 3); server-side "1 approving review" on `dev`; gap → #60 for the gate-as-required-check | telemetry (repo settings) | DORA capability "Code review" / *Accelerate* ch. 4 (peer review over change-approval boards); Scorecard `Code-Review` |
| D15 | The verdict for each run carries what changed, what evidence was produced and a categorical risk band — so review attention is allocated, never a gate relaxed | gap → #134 | now (git-derived bands; evidence from receipts) | DORA 2023 (lightweight change approval); Kun Chen pipeline review in `docs/research/VIDEO-REVIEW.md` |
| D16 | Reliability is tracked alongside the four keys (DORA's fifth metric) — see matrix #4 rows O8–O10 | see #4 | telemetry | DORA State of DevOps Report 2022/2023 ("reliability" added to the throughput/stability keys) |

## Notes

- **Why D10–D13 are ratchets, not targets.** DORA publishes *cluster* bands (elite/high/…);
  borromeanRings refuses to gate on any published band. The buildable form is: the gate records
  the metric, and a run may not *regress* the rolling value below the recorded baseline —
  exactly the `meta_harness.ratchet` shape `60_mutation` already uses.
- **Where the telemetry would come from.** A `deploy` record appended by the project's own
  deploy step (a `verdict_history.jsonl`-style ledger), plus incident linkage. No hosted
  service and no API key — the same rule as everything else (`docs/HANDOFF.md` §3).
- **D9 is the first row to build**: it is git-derivable today and the issue calls it out
  explicitly.
