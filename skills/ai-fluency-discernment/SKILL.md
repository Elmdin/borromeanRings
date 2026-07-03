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

## The three dimensions
- **Product** — accuracy (verifiable?), appropriateness (fits audience/purpose?), coherence
  (internally consistent?), relevance (addresses what was asked, or drifted?), completeness.
- **Process** — did it follow the steps, or improvise? logical gaps? unauthorized assumptions?
  did it stay in scope? In an agentic run: what did it actually do, in what order?
- **Performance** — did it flag uncertainty or present guesses as fact? ask good questions or
  barrel ahead? behave consistently with what was asked?

**Coherence and accuracy are independent.** Something can be well-written, internally
consistent, and still factually wrong. The most common failure is accepting a fluent output
that doesn't reflect reality — only domain knowledge catches it, so the human is the essential
check; the agent cannot fully self-evaluate.

## Output review (run before using a significant output)
- Product: factual claims verifiable or flagged? matches the requested format/audience? no
  internal contradiction? answers the actual question?
- Process: followed the steps in order? no silent scope expansion? assumptions stated, not
  hidden?
- Performance: uncertainty surfaced? checked in at the right moments rather than over-running?

## Agentic trajectory audit (after a multi-step autonomous run)
```
TRAJECTORY AUDIT
Steps taken:                   [what the agent did, in order]
Decisions made without review: [list]
Assumptions made:              [list]
Recommended human verification:[specific claims/sections to check]
Confidence in output:          High / Medium / Low
```
For an agentic run, evaluate the **trajectory, not just the final artifact**.

## The Description→Discernment loop
When output disappoints, don't just re-run — **diagnose first**:
1. Identify which dimension failed (Product / Process / Performance).
2. Trace it back to the Description that produced it.
3. Fix that layer, then retry. (Re-prompting with the same gap fixes the wrong thing.)

## Under borromeanRings
The gate is automated **Process Discernment**: `verify.sh` confirms output is importable,
formatted, linted, typed, tested (coverage ratchet), and security-scanned before it counts as
done, and the receipts under `.meta-harness/receipts/<run-id>/` are the recorded trajectory.
This skill covers what the gate deliberately doesn't: semantic correctness, design soundness,
scope creep, and whether a commit message tells the truth. **A green gate is necessary, not
sufficient** — pair it with human Discernment on anything that will be shared or shipped.
