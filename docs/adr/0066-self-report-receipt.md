# ADR-0066: The agent's self-report is structural, taught by the skills, recorded at Stop

**Status:** Accepted · 2026-09-09 · closes #176 (sub-issue of #172) · extends ADR-0059

## Context
The `ai-fluency-*` skills (ADR-0020) state each 4D competency from the human's side: what to
delegate, how to describe, what to check, what to disclose. The other party to that contract
was silent. Nothing told the agent it must push back on a bad hand-off, ask before guessing,
expose what it left unchecked, or refrain from calling unverified work done — and one skill
actively contradicted the last point: the trajectory-audit template in
`ai-fluency-discernment` ended with `Confidence in output: High / Medium / Low`.

The 4D Fluency Compact work (#172) found this contradiction and resolved it against the
grade. Its reasoning, re-authored here because that repository is CC BY-NC-SA and this one is
Apache-2.0: an agent's estimate of its own reliability is not something a reader can check,
so a grade — a decimal, a percentage, *or* a three-word ordinal — gives the reader nothing
to do except defer. A defensive `Low` is as much a fabrication as an inflated `High`; the
objection is to the grade, not to how many decimal places it carries. What a reader *can*
check is a fact about the work: "I did not run the integration suite", "I assumed the
timestamps are UTC", "the claim most likely wrong is X". Those facts keep the judgement where
Discernment says it belongs: with the human.

ADR-0059 showed how to make a reply-shape request real: verify it from the transcript the
Stop hook receives, record the verdict, tally it in self-status, never block. This decision
applies the same machinery to the closing block.

## Decision
1. **Four AI-side obligations, one per competency, in the skill that owns it** (re-authored,
   Apache-2.0; SPEC-self-report.md §"The four AI-side obligations"): renegotiate a delegation
   it cannot honour (`ai-fluency-delegation`); surface ambiguity before generating
   (`ai-fluency-prompting`); make its work auditable (`ai-fluency-discernment`); never
   overstate completion (`ai-fluency-diligence`). Each skill paid for the new section with
   trims elsewhere in the same file, so the context-budget ratchet is respected.
2. **The reply convention is a block of facts, never a grade.** A substantive reply ends with
   `VERIFICATION STATUS` and exactly four labelled lines — `Verified`, `Unverified`,
   `Weakest claim`, `Assumed` — each free text, `none` allowed (an explicit `none` is a claim
   a reader can dispute; a missing block is silence). The `Confidence in output` line is
   removed from the trajectory audit. Any ordinal or numeric confidence inside the block —
   a grade word standing as a field's whole value, a percentage, an `N/10`, the word
   "confident/confidence" — violates the structural rule.
3. **A receipt, not a gate.** `meta_harness.self_report` finds the *final* assistant text of
   the last exchange (the block closes the reply where the rewrite marker opens it), decides
   `present` / `absent` / `malformed` / `graded` / `exempt` / `unknown` deterministically, and
   `stop_gate.sh` appends the verdict to `.meta-harness/self_report.jsonl` in the **same
   bounded Python step** as the rewrite verdict — one process, one stdin read, the same
   10 s wall-clock bound, never touching the hook's exit code. `status.sh` shows
   `Self-report: present N of M (G graded, U unknown)`.
4. **Reuse by import.** The transcript tail reader, entry parser, exchange finder, trivial-prompt
   exemption and prompt digest are `rewrite_contract`'s; `find_last_exchange` gains a
   `final=True` keyword rather than a copy. The record I/O sits in `verdict` beside the other
   `.meta-harness` records, so `status_assess` and `status` keep their fan-out at the
   coupling baseline.
5. **`[self_report].enabled` defaults to `[prompt_rewriting].enabled`.** The two reply-shape
   contracts travel together — a project that asked for the opening line has opted into the
   closing block — and a project can diverge explicitly.

## Alternatives considered
- **A derived grade computed from the four lines** (e.g. `Low` if anything is unverified) —
  rejected for now. In a skill — a markdown instruction with no runtime — the "derivation"
  would be performed by the model and rationalised after the fact: a self-assessment dressed
  as a computation, which is worse than either honest option because it looks checkable and
  is not. Revisit only if a runtime validates the block and computes the grade itself.
- **Keep the ordinal for humans, the block for machines** — rejected: two forms of the same
  thing citing each other is exactly the contradiction being closed.
- **A model judge of whether the block is *truthful*** — rejected: agent-only per ADR-0030,
  one call per Stop, and truthfulness is not what a hook can decide; presence and shape are.
- **Block the Stop on a missing or graded block** — rejected for v1, as in ADR-0059: nagging
  is what decays; a record plus a later ratchet is the borromeanRings way.
- **Flag grade words anywhere in the block** — rejected: `the high-water mark test` is not a
  grade. The rule targets the *answer being a level*, so a grade word counts only when it is a
  field's whole value; numeric forms and "confident" count anywhere.

## Consequences
- The skills now state both halves of every competency, and no skill asks for a grade.
- One more append per Stop from the process that already runs; no new process.
- Transcripts that hide the final text (older substrates, sidechain-only turns) yield
  `unknown`, honestly, exactly as for the rewrite contract.
- The next step, if the record shows decay, is a threshold-free ratchet on the present share,
  `noop` with no record — the same path ADR-0059 reserved for the opening line.
