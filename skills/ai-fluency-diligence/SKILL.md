---
name: ai-fluency-diligence
description: >
  Take responsibility for AI-assisted work before it is shared, committed, published, or
  deployed — choosing the right tool, disclosing AI's role appropriately, and verifying you can
  vouch for the output. Provides a pre-share checklist and context-appropriate disclosure
  guidance. Applies the Diligence competency of the AI Fluency framework (see
  docs/AI-FLUENCY.md). Use before anything leaves the workspace. Triggers: "how should I
  disclose AI use", "am I being responsible here", "diligence check", "ready to ship this".
---

# Diligence — owning the result

Diligence is taking responsibility for *what* you do with an agent and *how*. It has three
parts, and the bar rises with the stakes and the audience.

## The three parts
- **Creation diligence** — Is this the right tool for the task? Did you share anything
  confidential or sensitive that you shouldn't have? Did the collaboration build your
  understanding, or bypass it? (If you can't explain what the agent did and why, you haven't
  understood it.)
- **Transparency diligence** — Who needs to know AI was involved? Is the disclosure specific
  enough to be meaningful (which tool, which tasks), and appropriate to the context?
- **Deployment diligence** — Did you verify the factual claims where stakes are high? Are you
  prepared to stand behind this as if you wrote it yourself? For agentic output, did you review
  the *trajectory*, not just the final result?

## Pre-share checklist
- [ ] Appropriate tool for the task; no unauthorized sensitive data shared.
- [ ] Everyone who needs to know AI was involved is identified.
- [ ] Disclosure is specific (not just "AI helped") and context-appropriate.
- [ ] High-stakes factual claims verified independently.
- [ ] You can personally vouch for every part of the output.
- [ ] For agentic output: the trajectory was reviewed (see `ai-fluency-discernment`).

## Disclosure — match the context
| Context | Disclosure level |
|---|---|
| Academic / research publication | Full: which tool, which tasks, what review process |
| Public documentation | Note AI assistance where substantive |
| Code committed to a repo | PR description notes if an agent generated or significantly refactored the change |
| Internal notes / personal drafts | None required |

## Diligence evolves with autonomy
As agents act more autonomously, Diligence shifts from *reviewing outputs after* to *designing
constraints before*. The question changes from "is this output okay?" to "did I set up the
right guardrails from the start?" — which is where Delegation's authority scope and
Stewardship's tripwires come in.

## Under borromeanRings
The gate is **Deployment Diligence made deterministic**: nothing merges until it meets the
declared standard, and `merge.sh`'s explicit-invocation requirement means a human vouches for
every merge (ADR-0007). The receipts under `.meta-harness/receipts/` are **Transparency
Diligence** — every gate run is auditable. For non-code outputs (docs, ADRs, analyses), this
skill is the equivalent discipline: verify, disclose, and vouch before it leaves the
workspace.
