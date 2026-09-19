---
name: ai-fluency-delegation
description: >
  Decide what an AI agent should do, what the human should own, and how much autonomy to
  grant — before a multi-step or ambiguous task. Produces an explicit authority-scope
  declaration and, at project/feature kickoff, a short 4D alignment. Use when the right
  division of labor isn't obvious, when starting a sprint or feature, or before handing an
  agent a long autonomous run. Applies the Delegation competency of the AI Fluency framework
  (see docs/AI-FLUENCY.md). Triggers: "should I delegate this", "plan this work", "scope the
  agent", "4D kickoff", "authority scope".
---

# Delegation — scoping authority before the work starts

Delegation is deciding *whether, when, and how* to engage an agent — and making that decision
**explicit before** the agent acts, not correcting it after something unexpected.

## The three components
1. **Problem awareness** — the actual goal (not just the ticket), its subtasks, the stakes,
   and how reversible each decision is.
2. **Platform awareness** — what this agent does well here, where human judgment is
   irreplaceable, the relevant limits.
3. **Task division** — which subtasks run autonomously, which are collaborative, which the
   agent governs over many future interactions — and where the human checkpoints are.

Drive autonomy by **stakes × reversibility**: low-stakes and reversible → more autonomy;
high-stakes or irreversible → more checkpoints.

## The three modes
- **Automation** — the agent executes a well-defined task; the human checks the output.
- **Augmentation** — human and agent work back and forth (design, tradeoffs, architecture);
  judgment stays with the human.
- **Agency** — the agent governs future interactions on the human's behalf (recurring
  workflows, long runs); needs the most Description and Discernment.

## Authority-scope declaration (use before any multi-step agentic task)
```
For this task:
- You MAY:            [authorized actions]
- Check with me before: [decision points needing review]
- You MUST NOT:       [hard constraints — never cross these]
- Checkpoint:         after [milestone], pause and show me before continuing.
```
The highest-leverage line is **MUST NOT**: negative constraints prevent costly surprises.

## The agent's side: renegotiate what it cannot honour
A delegation is a two-party agreement. Handed work it cannot do well — it needs a person, a
different tool, or authority the scope withholds; the task was cut at the wrong grain; the
goal conflicts with a MUST NOT — the agent says so *before* doing a poor job and proposes
the split that would work. Pushing back on a bad hand-off honours the delegation; silently
doing something else is the breach.

## 4D kickoff (at kickoff)
Align on all four first: **Delegation** — what runs autonomously vs. needs review?
**Description** — what must the human specify so the agent doesn't guess? **Discernment** —
what will the human check when it's done? **Diligence** — anything needing disclosure or
extra care?

## Under borromeanRings
The harness makes Delegation deterministic: `borromeanrings.toml` declares the authority
scope, `verify.sh` enforces it, and `merge.sh` requires explicit human invocation, so the
agent can suggest but never merges on its own. Treat any change to the spine, the gate
logic, or the check contract as **MUST NOT without explicit approval**. For a run already
in motion, hand off to `ai-fluency-stewardship`.
