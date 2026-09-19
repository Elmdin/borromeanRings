# Survey — a per-project report of what is practised, lacking, and next to adopt

**Question.** #139 asks for one answer to "what does this project practise, what does it
lack, and what should it adopt next?" Did anything in this repo, a dependency, or the
ecosystem already answer it?

## What already exists

| Where | What was found | Fit |
|---|---|---|
| This repo | `meta_harness.status` / `status_assess` — `build_status`, `render_self_status`, `obligations`, `hollow_checks`. Says whether the gate is green and which checks fail or inspected nothing. | **Reuse the facts, not the view.** It answers "is it green now", not "what is missing". `status.sh --swe` composes the two rather than growing the status view. |
| This repo | `meta_harness.adopt` — `plan_adoption`, `RECOMMENDED`, `RATCHET_BASELINES`. Knows which checks a project has not adopted and which ratchets lack a baseline. | **Reuse.** The "adopt next" check and baseline lines are `plan_adoption`'s output, so the report and `adopt.sh` cannot disagree. |
| This repo | `meta_harness.verdict` — `Verdict`, `is_failing`. The last run's per-check status. | **Reuse** for every pass / fail / unknown classification. |
| This repo | `meta_harness.ledger` — run counts and streaks over verdict history. | Not a fit: it answers "has the gate done anything", a question about history, not about gaps. |
| This repo | `meta_harness.archetypes` — per-archetype feature evaluation. | **Reuse its results**, passed in as plain `FeatureFact` values so `swe_state` does not import it (see Decision). |
| A declared dependency | None. borromeanRings has no runtime dependencies; this is standard-library parsing of files already on disk. | Not a fit. |
| Ecosystem | Maturity and scorecard tools (OpenSSF Scorecard, DORA-style self-assessments). Advisory only: no key-free search exists, see ADR-0051. | Not a fit: each produces a **score**, which ADR-0067 rejects. A blended number over rows of unequal weight is the signal #139 warns against. |

## Decision

**Build a thin composition**, not a new source of truth. Every line `swe_state` renders
comes from a module that already owned that fact: the required set from the spine, the
statuses from `verdict`, the adoption gaps from `adopt`, the features from `archetypes`,
and the rows from the matrices' *Enforced by* column. What was missing was the one place
that puts them together and says, in a fixed order, what to do about them.

One duplication is deliberate. `swe_state` declares its own `"noop"` literal rather than
importing `status_assess.NOOP`. Importing it would add a third project import and exceed
the `33_coupling` fan-out baseline, and ADR-0067 records that the ratchet is met by design,
never by raising it. The right fix is to move `NOOP` into `verdict`, which both modules
already import. That belongs in its own change, not this feature.

## Sources
- `docs/adr/0067-swe-state-report.md` — the decision, including the rejected score
- `docs/specs/SPEC-swe-state.md` — the contract
- `git grep -n "def obligations\|def hollow_checks\|def plan_adoption\|NOOP =" src/` — how the existing pieces were found
