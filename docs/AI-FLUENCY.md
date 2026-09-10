# borromeanRings and the AI Fluency 4D framework

> **Attribution.** This document applies the **AI Fluency** framework — *Delegation,
> Description, Discernment, Diligence* — created by Rick Dakan, Joseph Feller, and Anthropic
> (licensed CC BY-NC-SA 4.0), to borromeanRings. The framework is credited here as prior art;
> the text below is borromeanRings's own (Apache-2.0) and describes the framework's *ideas*,
> not its original wording. See ADR-0020.

borromeanRings was built as a deterministic, fail-closed gate over AI coding agents. The AI
Fluency framework turns out to name, almost one-for-one, the disciplines that gate already
enforces. This doc makes that mapping explicit — partly because the vocabulary is useful to
contributors, and partly because naming what the gate *is* sharpens the project's own thesis:
**standards become gates, not suggestions.**

The framework has four competencies (the "4Ds"). borromeanRings adds no fifth: governing an
autonomous run *while it runs* — **Stewardship** — is a **cadence** on which the four are
re-exercised, not a new kind of judgment (ADR-0020, amendment). The framework's authors
never proposed a fifth competency; the cadence is this repo's own extension.

## Delegation — deciding what the agent is authorized to do
*Setting goals and deciding whether, when, and how to engage an agent.*

In borromeanRings the delegation boundary is **declared, not improvised**:
- `borromeanrings.toml` is the authority declaration — `[checks].required`, `[layout]`,
  `[hygiene]`, `[git]` define what "passing" means and what the agent is held to.
- `verify.sh` enforces the scope: it exits 0 only when every required check passes.
- `merge.sh` requires explicit human invocation — the agent never merges autonomously
  (ADR-0007).

The one thing a human must **not** delegate is the definition of "passing." If the spine is
wrong, everything that passes it is worthless.

### Charter — the delegation, written down
A project that opts in (`[charter].enabled`) commits a `CHARTER.toml` naming the goal, the
stakes tier (`low` or `high` — a binary, never a severity dial), what "done" means
(`done_when`, real predicates — a hedge like "it works" is rejected), when the agent must stop
(`stop_when`), what it may never do (`may_not`), and who owns the delegation. Check
`22_charter` validates it fail-closed on every gate run, and the prompt hook reminds the
session when the file is missing. This is Delegation made reviewable: the terms live in a
diff, not in a conversation. See `docs/specs/SPEC-charter.md` and ADR-0063.

## Description — communicating intent well enough to act on
*Telling the agent what you want, how to approach it, and how to behave.*

borromeanRings mechanizes Description at the prompt boundary:
- The `UserPromptSubmit` hook (`.claude/hooks/prompt_rewrite.sh`) injects a directive that
  asks the agent to preserve the user's intent, apply best practices, honor the declared
  account and value priorities, and **show the improved request and let the user steer**
  (ADR-0011, `docs/specs/SPEC-prompt-rewrite.md`). borromeanRings does not rewrite the prompt;
  it *enforces that the agent does, and shows its work*.
- `AGENTS.md` is the persistent behavioral description for any agent in the repo.
- `borromeanrings.toml` is the persistent process description (which checks run, in what
  shape).

## Discernment — critically evaluating what the agent produced
*Judging the output, the process that made it, and the behavior along the way.*

The gate is **automated Process Discernment**: it checks that output is importable, formatted,
linted, typed, tested (with a coverage ratchet), and security-scanned before anything counts
as done. The receipts under `.meta-harness/receipts/<run-id>/` record the trajectory, not just
the final state.

What the gate deliberately does **not** judge — and where human Discernment stays essential:
- whether a check tests the *right* thing (semantic correctness),
- whether an architecture decision is sound,
- whether the agent quietly expanded scope beyond what was asked,
- whether a commit message accurately describes the change.

**A green gate is necessary, not sufficient.** It means the code is clean and safe; it does
not mean it is correct or the right thing to build.

## Diligence — taking responsibility for the result
*Owning what is shipped and being honest about how it was made.*

- The gate is **Deployment Diligence** made deterministic: nothing merges until it meets the
  declared standard.
- `merge.sh`'s explicit-invocation requirement means a human vouches for every merge.
- The receipt system is **Transparency Diligence**: every gate run is documented and
  auditable — consistent with the project's thesis that its own claims must be evidence-backed.

## Cadence — Stewardship, or when the four are re-run
*Not a fifth competency: the schedule on which the four apply while an agent is in motion.*

The four competencies read as before-and-after disciplines. A long autonomous run inserts a
*during*, and every question asked there is one of the four at a different moment: "still in
scope?" is Delegation re-checked against `CHARTER.toml`; "trajectory coherent?" is process
Discernment before the task ends; "continue, interrupt, or stop?" is Diligence for what
happens next. The `ai-fluency-stewardship` skill is that schedule:

- **Two speeds.** *Fast*, every turn: intent read as intended, an assumption stated, nothing
  in `may_not` touched. *Full*, per task: re-read the charter, read the receipts, test each
  `done_when` predicate, audit the trajectory.
- **Checkpoints, each with a detector.** The Stop verdict flips (`stop_gate.sh`; verdicts
  persist under `.meta-harness/`); the gate fails three Stops running (bounded retry escalates
  to the human); a `stop_when` line holds (`22_charter` validates and prints the charter every
  run); context is compacted or resumed (PreCompact snapshot, SessionStart brief); stakes or
  scope change (the committed `CHARTER.toml` diff, re-validated by `22_charter`); the rewrite
  contract is missed (the Stop-time record, ADR-0059, once merged).
- **Back-edges.** A product failure at a checkpoint sends the work back to Description; a
  process failure sends it back to Delegation.

Mechanizing the remaining tripwires (retry loops, orphaned processes) is follow-up work, not
yet shipped.

## The mapping at a glance

| AI Fluency concept | borromeanRings mechanism |
|---|---|
| Delegation boundary | `borromeanrings.toml` + explicit `merge.sh` invocation |
| Delegation terms | `CHARTER.toml`, gated by `22_charter` |
| Description (process/behavior) | `borromeanrings.toml`, `AGENTS.md` |
| Description (in-the-moment) | `prompt_rewrite.sh` `UserPromptSubmit` hook |
| Automated Process Discernment | `verify.sh` (the 8 required checks) |
| Automated Product Discernment | coverage ratchet (`40_test`), security scan (`50_security`) |
| Human Discernment | PR review, ADR reasoning, semantic correctness |
| Deployment Diligence | explicit `merge.sh`; declared standards in the spine |
| Transparency Diligence | `.meta-harness/receipts/`, PR descriptions |
| Cadence (Stewardship) | Stop-gate verdict + bounded retry, `22_charter`, PreCompact/SessionStart brief (shipped); retry-loop and orphan tripwires (planned) |

## Skills
Five skills — four competencies and the cadence — make these disciplines actionable in a
session. They install user-level via `install-global.sh`, so they are available in any
workspace borromeanRings governs:

| Skill | Use it to |
|---|---|
| `ai-fluency-delegation` | Scope an agent's authority before a multi-step task; run a 4D kickoff |
| `ai-fluency-prompting` | Sharpen a prompt (the six techniques, pattern templates, troubleshooting) |
| `ai-fluency-discernment` | Review an output / audit an agentic trajectory before building on it |
| `ai-fluency-diligence` | Check disclosure and responsibility before sharing AI-assisted work |
| `ai-fluency-stewardship` | Run the cadence over a long autonomous run — two speeds, checkpoints, back-edges |
