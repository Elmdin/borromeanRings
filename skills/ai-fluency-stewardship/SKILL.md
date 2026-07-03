---
name: ai-fluency-stewardship
description: >
  Govern an AI system *while it runs* — decide, in real time, whether to let an autonomous
  agent continue, interrupt it, or stop it. Provides the three stewardship questions, a tripwire
  list, and a run protocol. Stewardship is the proposed fifth competency of the AI Fluency
  framework, for autonomy over longer horizons than Delegation/Discernment/Diligence cover (see
  docs/AI-FLUENCY.md). Use before granting extended autonomy and at every checkpoint of a long
  run. Triggers: "is this still on track", "should I let it keep going", "review the agent's
  progress", "trajectory check", "is the agent stuck".
---

# Stewardship — governing the run in motion

Delegation, Description, Discernment, and Diligence are mostly *setup* and *review*.
Stewardship is the competency that applies **while the agent is running**: being a responsible
principal in real time. Its core question is simply **"should it keep going?"**

| Competency | When it applies | Core question |
|---|---|---|
| Delegation | Before the run | How much authority to grant? |
| Description | Before the run | What to specify? |
| Discernment | After a step/run | Was it good? |
| Diligence | Before & after | Disclosed and vouched-for? |
| **Stewardship** | **During the run** | **Continue, interrupt, or stop?** |

## The three questions (ask at every checkpoint)
1. **Still in scope?** Is the agent doing what was authorized, or has it expanded scope or
   crossed a "MUST NOT" from the authority-scope declaration?
2. **Trajectory coherent?** Are the steps logically connected to the goal? Is it making
   progress, or looping / stuck?
3. **Continue, interrupt, or stop?**
   - **Continue** — on-scope, coherent, progressing.
   - **Interrupt** — drifting, an unexpected decision was made, or a checkpoint was reached:
     pause, review, redirect.
   - **Stop** — a hard constraint was crossed, an irreversible action is imminent, or the
     behavior is no longer understandable.

## Tripwires (interrupt regardless of where the run is)
- Attempts to modify gate logic (`verify.sh`, check scripts) or the spine
  (`borromeanrings.toml`).
- Attempts to invoke `merge.sh` or any merge/push operation.
- About to take an irreversible action (delete, publish, deploy, force-push).
- Retrying the same failing step more than a few times instead of fixing the cause.
- Many steps with no reviewable artifact produced.
- A process, server, or shell left running with nothing consuming it (orphaned process).

## Run protocol
- **Before:** declare the authority scope (`ai-fluency-delegation`); name the tripwires; set
  explicit checkpoints.
- **During:** at each checkpoint, read receipts under `.meta-harness/receipts/`; watch the
  tripwires; if a loop or drift appears, interrupt rather than wait.
- **After:** full trajectory audit (`ai-fluency-discernment`); note any stewardship decision
  made and why ("interrupted at X because Y").

## Mindset
The hard skill is **knowing when to let go and when to pull back**. Too much interruption
defeats the point of autonomy; too little leaves an unmonitored system making consequential
decisions. You don't need to understand every step — only enough to know whether to stop it.
Stewardship is calibrated trust: earned by track record, bounded by stakes, always revocable.

## Under borromeanRings
borromeanRings already has the seed of mechanized stewardship: the Stop gate's **bounded
retry** won't loop forever (ADR-0016 governs when it skips), and `merge.sh`'s explicit
invocation is a hard tripwire against autonomous release. Turning the rest of the tripwire list
above into deterministic, gated checks/hooks (retry-loop and orphaned-process detection in
particular) is **active follow-up work, not yet shipped** — tracked with the
collaboration-governance Tier C effort. Until then, this skill is the human-run protocol.
