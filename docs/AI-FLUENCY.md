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

The framework has four competencies (the "4Ds"), plus a fifth that borromeanRings takes
seriously because it governs autonomous runs: **Stewardship**.

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

## Stewardship — governing the run while it happens
*The competency that applies while an autonomous agent is in motion: continue, interrupt, or
stop?*

Delegation, Description, Discernment, and Diligence are mostly setup-and-review. Stewardship
is **real-time**. borromeanRings has the seed of it already — the Stop gate's bounded retry
(it will not loop forever) is a tripwire — and the `ai-fluency-stewardship` skill describes the
rest: watch for an agent retrying the same failure, taking many steps without a reviewable
artifact, attempting to edit gate logic, or leaving an orphaned process behind. Turning those
tripwires into gated checks/hooks is active follow-up work, not yet shipped.

## The mapping at a glance

| AI Fluency concept | borromeanRings mechanism |
|---|---|
| Delegation boundary | `borromeanrings.toml` + explicit `merge.sh` invocation |
| Description (process/behavior) | `borromeanrings.toml`, `AGENTS.md` |
| Description (in-the-moment) | `prompt_rewrite.sh` `UserPromptSubmit` hook |
| Automated Process Discernment | `verify.sh` (the 8 required checks) |
| Automated Product Discernment | coverage ratchet (`40_test`), security scan (`50_security`) |
| Human Discernment | PR review, ADR reasoning, semantic correctness |
| Deployment Diligence | explicit `merge.sh`; declared standards in the spine |
| Transparency Diligence | `.meta-harness/receipts/`, PR descriptions |
| Stewardship | bounded Stop-gate retry (shipped); tripwire monitoring (planned) |

## Skills
Five skills make these disciplines actionable in a session. They install user-level via
`install-global.sh`, so they are available in any workspace borromeanRings governs:

| Skill | Use it to |
|---|---|
| `ai-fluency-delegation` | Scope an agent's authority before a multi-step task; run a 4D kickoff |
| `ai-fluency-prompting` | Sharpen a prompt (the six techniques, pattern templates, troubleshooting) |
| `ai-fluency-discernment` | Review an output / audit an agentic trajectory before building on it |
| `ai-fluency-diligence` | Check disclosure and responsibility before sharing AI-assisted work |
| `ai-fluency-stewardship` | Govern a long autonomous run — when to continue, interrupt, or stop |
