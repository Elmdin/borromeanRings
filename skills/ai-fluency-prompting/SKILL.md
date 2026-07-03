---
name: ai-fluency-prompting
description: >
  Sharpen a prompt before acting on it — or diagnose why a previous one missed. Covers the six
  prompting techniques, a reusable pattern library, and a symptom→fix troubleshooting table.
  Applies the Description competency of the AI Fluency framework (see docs/AI-FLUENCY.md). Use
  when a prompt isn't producing what was intended, when crafting a request for a non-trivial
  task, or when output drifted and the cause isn't obvious. Triggers: "improve my prompt", "why
  didn't that work", "how do I ask this better", "prompt template".
---

# Prompting — Description made concrete

A better prompt is almost always faster than a retry. Description has three layers, and a
strong prompt covers all three: **Product** (what output), **Process** (how to approach it),
**Performance** (how to behave).

## The six techniques
1. **Provide context** — who you are, why you're asking, the situation. Shapes tone, depth,
   and format more than anything else.
2. **Show an example of "good"** — a sample output communicates a pattern more precisely than
   describing it.
3. **Specify output constraints** — format, length, sections, what to include/exclude.
4. **Break into ordered steps** — when the task has phases or order matters, or you want to
   review intermediate results.
5. **Ask it to think first** — request reasoning before the answer on complex or high-stakes
   work.
6. **Define the role** — role + audience + tone in one line calibrates vocabulary, depth, and
   structure.

**Secret weapon:** when you're unsure how to phrase a request, ask the agent to help you write
it — "I'm trying to get you to help me with X; help me craft an effective prompt for it."

## Pattern library
**Role + Context + Constraint opener** (start of any substantial task)
```
You are working on [project/context]. I am [role/background].
The goal is [specific output]. Constraints: [format, length, tone, what to avoid].
Do NOT [the specific thing the agent tends to get wrong here].
```
The **"Do NOT"** line is the single highest-leverage addition — it blocks default drift before
it starts.

**Draft + refine handoff** (long-form where voice/accuracy matter)
```
Draft [content] from [raw material]. This is a starting point, not a final product.
Optimize for accuracy to what is actually true — not for polish.
```
"Accuracy over polish" blocks the agent's pull toward making things sound better than they are.

**Self-check prompt** (before you review a significant output)
```
Before I review this, flag: anything factually shaky (Product), any assumption you made that I
didn't authorize (Process), anywhere you drifted from what I asked (Performance).
```

## Troubleshooting: symptom → fix
| Symptom | Likely cause | Fix |
|---|---|---|
| Too generic | Missing context | Technique 1 — who/why |
| Wrong format | No constraints | Technique 3 — structure, length, sections |
| Missed the point | Underspecified goal | Technique 2 — show a "good" example |
| Skipped steps | No process guidance | Technique 4 — ordered steps |
| Shallow reasoning | No thinking space | Technique 5 — think first |
| Wrong tone | No role | Technique 6 — role + audience |
| Still wrong | Fundamental ambiguity | Secret weapon — co-write the prompt |

## Under borromeanRings
The `UserPromptSubmit` hook (`.claude/hooks/prompt_rewrite.sh`) already enforces much of this:
on every prompt it directs the agent to preserve intent, apply best practices, and show the
improved request for the human to steer (see `docs/specs/SPEC-prompt-rewrite.md`). This skill
is the reference behind that mechanism — reach for it when the rewrite still isn't landing and
you need to diagnose *which* layer (Product / Process / Performance) is missing.
