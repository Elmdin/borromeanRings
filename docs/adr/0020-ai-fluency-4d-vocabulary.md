# ADR-0020 — Adopt the AI Fluency 4D framework as borromeanRings's collaboration vocabulary (re-authored under Apache-2.0)

**Status:** Accepted

## Context
borromeanRings already mechanizes a set of human↔agent collaboration disciplines without
naming them: the gate is automated evaluation of an agent's output, the prompt-rewrite hook
is enforced clarification of intent, and `merge.sh` is a human-vouched release boundary.
Anthropic's **AI Fluency** framework (Rick Dakan, Joseph Feller, Anthropic) gives these a
precise, externally-recognized vocabulary — the **4Ds**: Delegation, Description, Discernment,
Diligence — plus a proposed 5th, **Stewardship** (real-time governance of an autonomous run).
A set of skill notes distilled from that course was offered for inclusion.

Two problems blocked dropping those notes in directly:
1. **License.** The AI Fluency framework is **CC BY-NC-SA 4.0** (NonCommercial + ShareAlike).
   Copying its *expression* into this Apache-2.0 repo would be incompatible: ShareAlike would
   force the copied files to stay CC-licensed, and NonCommercial conflicts with permissive OSS.
2. **Accuracy & fit.** The notes misdescribed the current gate (e.g. "6 checks" — it is 8),
   referenced config that does not exist (`[hooks]`, `[post_task]`, `[post_session]`,
   `[diligence]` blocks; hooks actually live in `.claude/settings.json`), used the old
   filename `borromeo.toml`, and carried personal/portfolio material out of scope for a
   public meta-harness repo.

## Decision
Adopt the 4D (+Stewardship) vocabulary as borromeanRings's collaboration framing, and
**re-author it in our own words** rather than port the source text. Ideas and methods are not
copyrightable — only their expression is — so original text describing the same ideas is ours
to license **Apache-2.0** with the rest of the repo. The AI Fluency framework is credited as
prior art (Dakan, Feller, Anthropic) in `NOTICE` and at the top of `docs/AI-FLUENCY.md`.

Concretely (see `docs/specs/SPEC-ai-fluency.md`): one philosophy doc (`docs/AI-FLUENCY.md`,
linked from `MANIFESTO.md`) mapping the 4Ds onto borromeanRings's existing mechanisms, and
five user-level skills under `skills/` — `ai-fluency-stewardship`, `-discernment`,
`-delegation`, `-prompting`, `-diligence`. Every borromeanRings reference is verified against
the live schema; no fictional config ships.

## Alternatives considered
- **Port the notes verbatim (or lightly edited) under a CC carve-out** — rejected: introduces
  a second, NonCommercial license into an otherwise Apache-2.0 public repo (a redistribution
  and contribution hazard), and would still carry the factual errors and personal content.
- **Skip the framing entirely; keep the mechanisms unnamed** — rejected: the vocabulary is
  genuinely clarifying for contributors and costs little; naming what the gate *is* strengthens
  the project's own thesis.
- **Mechanize Stewardship now (a tripwire check/hook)** — deferred, not rejected: the
  Stewardship *skill* ships as guidance; turning its tripwires into a gated check is follow-up
  work folded into the collaboration-governance Tier C effort and the pending hook-hang fix.

## Consequences
- (+) The repo gains a principled, externally-recognized vocabulary for what it already does,
  as clean Apache-2.0 text with proper attribution — no license conflict.
- (+) Re-authoring removes all personal/conversational content and corrects every schema
  inaccuracy *by construction*; the skills describe the real gate (8 checks), real hook
  location (`.claude/settings.json`), and real filename (`borromeanrings.toml`).
- (+) Skills install user-level via `install-global.sh`, available in any governed workspace —
  consistent with `borromeanrings` / `borromeanrings-contribute`.
- (−) The framing is borrowed; borromeanRings does not own the 4D concept and must keep its
  attribution intact (NOTICE + doc header).
- (−) Five new skills are surface to maintain; kept small and consolidated (13 source files →
  5 skills + 1 doc) to limit that cost.

## Amendment (2026-09-09, #177) — Stewardship is a cadence, not a fifth competency

**Status of the amendment:** Accepted. Supersedes every "fifth competency" / "5th D" phrasing
in this repo's docs and skills.

### Context
The original decision above adopted "the 4Ds plus a proposed 5th, Stewardship". Two facts
have since surfaced.

1. **Attribution.** The AI Fluency framework has exactly four competencies. Neither
   "Stewardship" nor a fifth competency appears anywhere in its published material. The
   idea of governing a run in motion is this repo's own extension; describing it as
   "proposed" by the framework attributed a position to its authors that they never took.
   Whatever the structural answer, that wording had to go.
2. **A sibling project's argument** (the maintainer's 4D project, ADR-0004 there; read for the
   argument only and re-authored here under the license rule of the decision above) is that
   every question Stewardship asks is one of the existing four asked at a different moment.

### The case for a fifth competency (this repo's original reason)
Delegation, Description, Discernment and Diligence read as *before-and-after* disciplines:
scope, specify, then judge and vouch. An agent running unattended for an hour is neither
before nor after; someone has to decide, in real time, whether it keeps going. That
"continue / interrupt / stop" decision felt like a distinct skill — one the gate had the seed
of (bounded Stop-gate retry, ADR-0016) and the skill catalogue lacked a name for.

### The case for a cadence (the sibling's argument, re-authored)
Take Stewardship's three questions apart:
- *Is the agent still inside what it was authorized to do?* — that is Delegation, re-checked
  mid-run against the written scope (`CHARTER.toml`).
- *Is the trajectory coherent — progressing rather than looping?* — that is the process
  dimension of Discernment, applied before the task is finished rather than after.
- *Continue, interrupt, or stop?* — that is Diligence: accepting responsibility for what
  happens next.

The tripwires decompose the same way (an irreversible action imminent is Diligence; a retry
loop or a run with no reviewable artifact is process Discernment; an attempt to edit gate
logic is a Delegation boundary). No question is a new *kind* of judgment; what is new is
*when* it is exercised. A discipline exercised only at intervals is a schedule, not a skill.
The framework's own teaching already groups the four by tempo — a strategic pair
(Delegation and Diligence) and a moment-to-moment pair (Description and Discernment) — so
adding a third tempo, "during", extends an axis the framework already has rather than
bolting a fifth column onto a model named for having four.

### Decision
**Stewardship is a cadence over the four competencies.** The four stay as they are; the
stewardship skill becomes the schedule on which they are re-run during an autonomous run:

- **Two speeds** — *fast* (per turn: intent read as intended, an assumption stated, nothing
  in `may_not` touched) and *full* (per task: re-read the charter, read the receipts, test
  each `done_when` predicate, run the trajectory audit).
- **Checkpoints with detectors** — a checkpoint fires only when a mechanism in this repo can
  detect its trigger: the Stop verdict flipping (`stop_gate.sh`, persisted verdict + history),
  three failed Stops (the hook's bounded retry escalation), a `stop_when` condition holding
  (`22_charter` validates and prints the list every run), compaction or resume (PreCompact
  snapshot + SessionStart brief, ADR-0053), a stakes or scope change (the committed
  `CHARTER.toml` diff; `22_charter` refuses `high` without its extras), and a missed rewrite
  contract (the Stop-time record, ADR-0059 — on branch `feat/rewrite-contract` until merged).
- **Back-edges** — a *product* failure at a checkpoint returns the work to Description; a
  *process* failure returns it to Delegation. Re-running the same step without taking the
  back-edge fixes the wrong layer.

### Consequences
- `docs/AI-FLUENCY.md`: Stewardship moves out of the competency list into a **Cadence**
  section; the intro no longer says "plus a fifth"; the mapping table names the detectors.
- `skills/ai-fluency-stewardship/SKILL.md` is rewritten as the cadence (canonical file;
  `install-global.sh` templates it, and the plugin branch symlinks only `.claude/skills/`
  — one source of truth). Growth was paid for by trims in the same file (context budget).
- `docs/specs/SPEC-ai-fluency.md`, `docs/MANIFESTO.md`: "4Ds plus a 5th" wording corrected.
- The attribution defect is closed: the extension is stated as this repo's own.
- Mechanizing the remaining tripwires (retry-loop, orphaned process) stays Tier C follow-up
  (`docs/specs/SPEC-collaboration.md`); this amendment changes docs and skill text only.
- **Revisit if** an in-flight obligation is found that does not reduce to Delegation,
  Discernment or Diligence. That would be evidence of a real fifth competency, and this
  amendment should be reopened rather than argued around.
