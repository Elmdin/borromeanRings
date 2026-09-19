---
name: ai-fluency-diligence
description: >
  Take responsibility for AI-assisted work before it is shared, committed, published, or
  deployed — choosing the right tool, disclosing AI's role, and verifying you can vouch for
  the output. Provides a pre-share checklist, disclosure guidance, and the agent's
  VERIFICATION STATUS block. Applies the Diligence competency of the AI Fluency framework
  (see docs/AI-FLUENCY.md). Use before anything leaves the workspace. Triggers: "how should I
  disclose AI use", "am I being responsible here", "diligence check", "ready to ship".
---

# Diligence — owning the result

Diligence is taking responsibility for *what* you do with an agent and *how*; the bar rises
with stakes and audience.

## The three parts
- **Creation** — Right tool? Anything confidential shared that shouldn't be? Did the
  collaboration build your understanding, or bypass it?
- **Transparency** — Who needs to know AI was involved? Is the disclosure specific (which
  tool, which tasks) and fitted to the context?
- **Deployment** — High-stakes claims verified? Would you stand behind this as if you wrote
  it? For agentic output, did you review the *trajectory*, not just the result?

## Pre-share checklist
- [ ] Right tool; no unauthorized sensitive data.
- [ ] Those who need to know AI was involved are told, specifically.
- [ ] High-stakes claims verified independently.
- [ ] You can vouch for every part of the output.
- [ ] Agentic output: trajectory reviewed (`ai-fluency-discernment`).

## Disclosure — match the context
Research publication: full (tool, tasks, review). Public docs: note substantive AI help.
Committed code: the PR description says if an agent generated or heavily refactored it.
Personal drafts: none.

## The agent's side: never overstate completion
The agent reports what it did, skipped and left unchecked *in the same register* — "done"
for a claim it never tested is the failure this competency exists to catch. Every
substantive reply ends with:

```
VERIFICATION STATUS
Verified:      what was checked, and how
Unverified:    what the reply relies on but did not check
Weakest claim: the statement most likely to be wrong, and why
Assumed:       what was decided without being told
```
All four lines, always; `none` is an answer (it can be disputed; a missing block is
silence). **No grade of any kind** — not `high/medium/low`, a percentage, `7/10` or
"confident": a grade asks the reader to trust the agent's view of itself; a named unverified
claim gives them something to check. Bare yes/no replies are exempt. The Stop hook
records the block (`.meta-harness/self_report.jsonl`, ADR-0066); it never blocks.

## Under borromeanRings
The gate is **Deployment Diligence made deterministic**: nothing merges until it meets the
declared standard, and `merge.sh`'s explicit invocation means a human vouches for every
merge (ADR-0007). Receipts under `.meta-harness/receipts/` are **Transparency Diligence** —
every gate run is auditable. As autonomy grows, Diligence shifts from reviewing to
constraining. For non-code outputs, this skill is the same discipline: verify, disclose,
vouch.
