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
**explicit before** the agent acts, not correcting it after something unexpected. It has three
parts.

## The three components
1. **Problem awareness** — What is the actual goal (not just the immediate ticket)? What
   subtasks does it require? What are the stakes and how reversible is each decision?
2. **Platform awareness** — What does this agent do well here? Where is human judgment
   irreplaceable? What are the relevant limits (hallucination, scope drift, context length)?
3. **Task division** — Which subtasks run autonomously, which are collaborative, which the
   agent governs over many future interactions — and where are the human checkpoints?

Drive autonomy by **stakes × reversibility**: low-stakes and reversible → more autonomy;
high-stakes or irreversible → more checkpoints.

## The three modes
- **Automation** — the agent executes a well-defined task; the human checks the output
  (format code, write a test, add a check under contract).
- **Augmentation** — human and agent work back and forth (design decisions, tradeoffs,
  architecture). Judgment stays with the human; breadth comes from the agent.
- **Agency** — the agent governs future interactions on the human's behalf (recurring
  workflows, long-running runs). Needs the most upfront Description and the most ongoing
  Discernment.

## Authority-scope declaration (use before any multi-step agentic task)
```
For this task:
- You MAY:            [authorized actions]
- Check with me before: [decision points needing review]
- You MUST NOT:       [hard constraints — never cross these]
- Checkpoint:         after [milestone], pause and show me before continuing.
```
The highest-leverage line is **MUST NOT**. Positive permissions are easy; the negative
constraints are what prevent costly surprises.

## 4D kickoff (use at project/feature start — five minutes that saves rework)
Align on all four before any work begins:
- **Delegation** — what runs autonomously vs. what needs review?
- **Description** — what must the human specify upfront so the agent doesn't guess?
- **Discernment** — what will the human check when it's done?
- **Diligence** — anything needing disclosure or extra care?

## Under borromeanRings
The harness makes Delegation deterministic. `borromeanrings.toml` declares the authority scope
(what the agent is held to); `verify.sh` enforces it; `merge.sh` requires explicit human
invocation, so the agent can suggest but never merges on its own. Treat any change to the
spine, the gate logic, or the check contract as **MUST NOT without explicit approval** — that
is the boundary the human keeps. For governing a run already in motion, hand off to
`ai-fluency-stewardship`.
