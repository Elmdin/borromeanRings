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
grade. The reasoning, stated here in borromeanRings terms because that repository is
CC BY-NC-SA and this one is Apache-2.0: a grade is a claim about the agent that only the
agent can produce, so it is exactly the kind of green this project refuses — a signal with
nothing behind it that the gate could inspect (ADR-0049's hollow-green argument, applied to
a reply). It makes no difference whether the grade has two decimals, a percent sign or three
words: `Low` offered out of caution is as unbacked as `High` offered out of optimism, and
either one invites the reader to threshold on it instead of reviewing. What the gate *can*
inspect is whether the reply names checkable facts — a test suite that was not run, a
timezone that was assumed, the one claim the agent would bet against — because each of those
is something the reviewer can go and verify, which keeps Discernment with the human.

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
- **A grade derived from the four lines** (e.g. `Low` whenever `Unverified` is not `none`) —
  rejected for now. Nothing in a skill computes; the agent would emit the grade and then
  produce the four lines that justify it, so the "derivation" is a receipt the emitter
  wrote for itself — the hollow-check pattern ADR-0049 exists to reject. Revisit if
  `self_report.py` grows a validator that derives the grade from the recorded fields: then
  the hook, not the model, would own the number, and `present_fields` would be its evidence.
- **An ordinal in the skills, the block in the hook** — rejected: keeping both is the
  contradiction this ADR closes, and each artifact would keep pointing at the other.
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
