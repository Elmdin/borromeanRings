---
name: ai-fluency-stewardship
description: >
  Govern an AI run while it is in motion: at each checkpoint, continue, interrupt, or stop.
  Stewardship is a cadence over the four AI Fluency competencies (ADR-0020 amendment),
  not a fifth one — two speeds plus detector-backed checkpoints. Use before granting
  extended autonomy and whenever a trigger fires. Triggers: "is this still on track",
  "should I let it keep going", "trajectory check", "is the agent stuck".
---

# Stewardship — the cadence over the four competencies

The four competencies are one kind of judgment each. A long autonomous run adds no new
kind; it adds a third *time* to exercise them — **during**, not only before and after.
Stewardship is that schedule. Its question, **"should it keep going?"**, splits into the
four applied mid-run:

| Mid-run question | Which competency it is |
|---|---|
| Still inside the authorized scope? | Delegation, re-checked against `CHARTER.toml` |
| Trajectory coherent — progressing, not looping? | Discernment (process dimension) |
| Continue, interrupt, or stop? | Diligence — owning what happens next |

## Two speeds
- **Fast** (every turn, seconds): request read as intended (`Reading this as:`)? one
  assumption stated? nothing in `may_not` touched? Log it.
- **Full** (per task): re-read the charter (`goal`, `stakes`, `done_when`, `stop_when`,
  `may_not`); read `.meta-harness/receipts/<run-id>/`; test each `done_when` predicate;
  run the trajectory audit from `ai-fluency-discernment`.

## Checkpoints — no trigger without a detector
| Trigger | Detector |
|---|---|
| The Stop verdict flips (PASS↔FAIL) | `stop_gate.sh` gates every Stop; verdicts persist in `.meta-harness/last_verdict.json` + `verdict_history.jsonl` |
| The gate fails three Stops running | the Stop hook's bounded retry (`CAP=3`) escalates to the human — the charter's "failed twice" line, mechanized |
| A `stop_when` condition holds | `22_charter` validates and prints the charter every gate run; the agent tests each line at every full pass |
| Context is compacted or resumed | `pre_compact.sh` snapshots the brief; `session_start.sh` re-injects it (verdict, open obligations) |
| Stakes change (`low`↔`high`) or scope grows | `CHARTER.toml` is committed, so the change is in the diff; `22_charter` refuses `high` without rollback/reviewer/blast_radius |
| The rewrite contract is missed | the Stop-time record `.meta-harness/rewrite_contract.jsonl` (ADR-0059, #81; not yet merged) |

At a checkpoint: **continue** (in scope, coherent, progressing) · **interrupt**
(drift or a trigger fired — pause, review, redirect) · **stop** (a `may_not` crossed, an
irreversible action imminent, behaviour no longer understandable).

## Back-edges — where a failed checkpoint sends the work
- **Product failure** (wrong output, a `done_when` predicate false, drifted scope) → back to
  **Description**: re-specify with `ai-fluency-prompting`, then resume.
- **Process failure** (looping, a gate-logic edit attempted, wrong division of labour or
  autonomy mode) → back to **Delegation**: redraw the scope with `ai-fluency-delegation`.
Re-running the step without the back-edge fixes the wrong layer.

## Tripwires (interrupt wherever the run is)
Edits to gate logic (`verify.sh`, `checks/`) or the spine (`borromeanrings.toml`); any
merge/push attempt; an irreversible action (delete, publish, deploy, force-push); a failing
step retried instead of diagnosed; many steps with no reviewable artifact; an orphaned process.

## Under borromeanRings
Mechanized today: bounded Stop-gate retry (ADR-0016), explicit `merge.sh`, `22_charter`, the
compaction brief (ADR-0053). Retry-loop and orphaned-process detectors remain Tier C
follow-up (`docs/specs/SPEC-collaboration.md`); until then the checkpoints above are the
human-run protocol. Trust: earned by track record, bounded by stakes, revocable.
