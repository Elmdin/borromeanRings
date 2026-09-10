---
name: ai-fluency-discernment
description: >
  Critically evaluate what an agent produced — and, for multi-step runs, how it got there —
  before using, sharing, or building on it. Provides an output-review checklist, an agentic
  trajectory-audit format, and the Description→Discernment diagnosis loop. Applies the
  Discernment competency of the AI Fluency framework (see docs/AI-FLUENCY.md). Use after any
  significant output and after every autonomous run. Triggers: "review this output", "is this
  right", "audit what you just did", "trajectory check".
---

# Discernment — evaluating output, process, and behavior

Discernment is the flip side of Description: judging what came back, in three dimensions.
It gets *harder* as agents get better, because polished output removes the obvious error
signals — "it looks right" is never sufficient.

## The three dimensions (check before using an output)
- **Product** — accuracy (claims verifiable or flagged?), fit for audience and format, no
  internal contradiction, answers the actual question, complete.
- **Process** — followed the steps in order, or improvised? logical gaps? assumptions stated,
  not hidden? no silent scope expansion? In an agentic run: what did it do, in what order?
- **Performance** — uncertainty surfaced, or guesses presented as fact? good questions, or
  barrelled ahead? checked in at the right moments?

**Coherence and accuracy are independent.** Something can be well-written, internally
consistent, and still wrong. Fluent-but-wrong is the common failure; only domain knowledge
catches it, so the human is the essential check.

## The agent's side: make the work auditable
The agent owes the reviewer the raw material for that judgement: say what it did *not*
verify, name the claim it would bet against first, keep a position under pushback unless
given a reason to move (agreeing to be agreeable is a Performance failure), and show its
reasoning when asked. This is filed per reply in the `VERIFICATION STATUS` block
(`ai-fluency-diligence`).

## Agentic trajectory audit (after an autonomous run)
```
TRAJECTORY AUDIT
Steps taken:                   [what the agent did, in order]
Decisions made without review: [list]
Assumptions made:              [list]
Recommended human verification:[specific claims/sections to check]
```
followed by the `VERIFICATION STATUS` block — never a confidence level. A grade is the
agent's opinion of itself and invites the reader to skip their own review; a named
unverified claim can be checked. Evaluate the **trajectory, not just the final artifact**.

## The Description→Discernment loop
When output disappoints, don't just re-run — **diagnose first**:
1. Identify which dimension failed.
2. Trace it back to the Description that produced it.
3. Fix that layer, then retry. (Re-prompting with the same gap fixes the wrong thing.)

## Under borromeanRings
The gate is automated **Process Discernment**: `verify.sh` confirms output is importable,
formatted, linted, typed, tested (coverage ratchet), and security-scanned before it counts as
done, and the receipts under `.meta-harness/receipts/<run-id>/` are the recorded trajectory.
This skill covers what the gate can't: semantic correctness, design, scope creep, honest
commit messages. **A green gate is necessary, not sufficient** — pair it with human
Discernment on anything that will be shared or shipped.
