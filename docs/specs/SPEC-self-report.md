# SPEC — Self-report receipt (the agent's structural verification block)

Issue #176 (sub-issue of #172) · ADR-0066 · module `meta_harness.self_report` · record I/O in
`meta_harness.verdict` · hook `.claude/hooks/stop_gate.sh` · view
`status_assess.render_self_report_line` · skills `skills/ai-fluency-*`

## User story
As the maintainer, I want the AI side of each 4D competency stated as an obligation the agent
actually reads, and the reply's `VERIFICATION STATUS` block recorded from evidence — the session
transcript — so that "the agent said it checked" becomes a record I can tally, and so that the
block is *structural* (what was and was not verified) and never a confidence grade. Record,
don't nag: nothing here blocks the Stop.

## The four AI-side obligations
The human side of each competency is already in the skills. This adds the agent's half, one
obligation per competency, each living in the skill that already owns the competency:

| Competency | The agent must | Lives in |
|---|---|---|
| Delegation | **Renegotiate a delegation it cannot honour**: say so when a task is misrouted, needs a person or a different tool, or was handed over at the wrong grain — before doing a bad job of it. | `skills/ai-fluency-delegation/SKILL.md` |
| Description | **Surface ambiguity before generating**: restate the reading, name the assumptions it had to invent, and ask the one question that decides the shape of the work rather than guessing. | `skills/ai-fluency-prompting/SKILL.md` |
| Discernment | **Make its work auditable**: say what it did *not* verify, name its own weakest claim, hold a position under pushback unless given a reason, and show its reasoning on request. | `skills/ai-fluency-discernment/SKILL.md` |
| Diligence | **Never overstate completion**: report what was done, what was skipped and what is unverified in the same register, ground claims in something checkable, and end every substantive reply with the `VERIFICATION STATUS` block below. | `skills/ai-fluency-diligence/SKILL.md` |

The `Confidence in output: High / Medium / Low` line of the trajectory-audit template in
`ai-fluency-discernment` is **removed** — it is the grade the structural rule forbids — and the
audit points at the block instead.

## The reply-block convention
A substantive reply ends with a section headed `VERIFICATION STATUS` carrying exactly four
labelled lines, in this order, each free text (a line may say `none`):

```
VERIFICATION STATUS
Verified:      <what was checked, and how>
Unverified:    <what the reply relies on but did not check>
Weakest claim: <the statement most likely to be wrong, and why>
Assumed:       <what was decided without being told>
```

An empty answer is still an answer: `Unverified: none` is a claim the reader can dispute,
whereas a missing block is silence. Trivial prompts (the same bare yes/no/continue set the
rewrite contract exempts) do not need the block.

## The structural rule
The block reports *facts a reader can go and check*, never a self-graded level. Any ordinal or
numeric confidence inside the block is a violation, whatever the wording around it:

- a grade word standing alone as a field's value — `high`, `medium`, `med`, `low` (case-insensitive,
  trailing `.`/`!` ignored);
- a percentage (`85%`, `85 %`, `0.9%`);
- an `N/10`-style score (`7/10`, `9 / 10`);
- the words `confident` / `confidence` anywhere in the block.

A grade word used *inside* a sentence (`Weakest claim: the high-water mark is untested`) is
not a grade and is not flagged — the rule targets the answer being a level, not the vocabulary.

## Detection (pure, deterministic, no model call)
`find_block(text) -> Block | None`:
- Lines inside a fenced code block (a line starting with ```` ``` ```` toggles the fence) are
  ignored — a reply that *quotes* the template is not filing one.
- The heading is a line whose text, after stripping markdown decoration (`*_#>` `` ` `` `~`
  and whitespace) and one optional trailing `:`, equals `verification status`
  case-insensitively. **If the heading appears more than once, the last one is the block**
  (the final section is the report; an earlier one is superseded).
- Every line after the heading is read to the end of the text. A line that starts with one of
  the four labels (decoration stripped, case-insensitive) followed by `:` sets that field's
  value; a later line for the same label replaces the earlier one (last wins). A line that
  starts with no label continues the previous field's value (joined with a space). Lines
  before the first label are ignored.
- The `Block` is immutable: an ordered tuple of `(label, value)` pairs in canonical label
  spelling (`Verified`, `Unverified`, `Weakest claim`, `Assumed`), plus `present` (the labels
  found) and `text` (the block's raw lines, bounded to 400 chars, kept as evidence).

`classify(block) -> SelfReportVerdict` (pure):
- `block is None` ⇒ `absent`;
- any of the four labels missing ⇒ `malformed` (`present_fields` says which were there);
- all four present and the structural rule is violated ⇒ `graded`, `violation` naming the
  first offending fragment (bounded to 80 chars);
- otherwise ⇒ `present`.

`evaluate_transcript(path, max_bytes=8 MiB, allowed_root=None) -> SelfReportVerdict` reuses
the rewrite contract's machinery *by import* — `read_tail` (bounded, refuses anything outside
the substrate's transcript root), `parse_entries`, `find_last_exchange(..., final=True)`,
`is_trivial`, `prompt_hash` — never a copy:
- the judged reply is the **last** assistant text after the last human prompt (the block is
  the reply's *final* section, where the rewrite marker is its *opening* line, so
  `find_last_exchange` gains a keyword `final=True` selecting the last text instead of the
  first; the default is unchanged);
- trivial prompt ⇒ `exempt` (regardless of the reply);
- refused / unreadable / promptless transcript, or a prompt with no reply ⇒ `unknown` with
  the reason, never a guess and never an exception.

Outcomes, exhaustively: `present`, `absent`, `malformed`, `graded`, `exempt`, `unknown`.

## Record
One JSON object per line, append-only, in `.meta-harness/self_report.jsonl`
(`verdict.SELF_REPORT_FILE`, written by `verdict.append_self_report_record`):

```
{"ts": "<UTC ISO-8601 Z>", "session_id": str, "prompt_hash": str,
 "status": "present"|"absent"|"malformed"|"graded"|"exempt"|"unknown",
 "present_fields": [str, ...], "violation": str, "line": int|null}
```

`prompt_hash` is `rewrite_contract.prompt_hash` — the same 16-hex digest as the rewrite
record, so the two receipts for one prompt can be joined. `line` is the 1-based transcript
line of the judged reply. `violation` is `""` unless the status is `graded`.

## Tally and self-status
`verdict.read_self_report_tally -> SelfReportTally(present, absent, malformed, graded, exempt,
unknown)`; malformed record lines are skipped and an unrecognised status counts as `unknown`
(fail-closed — never as present). `judged = present + absent + malformed + graded`.

`status_assess.render_self_report_line`: `present N of M` followed, when non-zero, by
`(A malformed, G graded, E exempt, U unknown)`; `no record` when the file is missing or empty.
The report line is `  Self-report:  present N of M (…)`, directly under the `Rewrite:` line.
`status_assess` and `status` reach the record through the existing `verdict` seam only — their
fan-out stays at the coupling baseline.

## Hook and configuration
`stop_gate.sh` records the self-report verdict in the **same bounded Python step** as the
rewrite verdict (one process, one stdin read, `BORROMEANRINGS_REWRITE_TIMEOUT`, default 10 s),
after the duplicate-registration claim and before the no-op guard, never on a re-stop
(`stop_hook_active`). It cannot change the hook's exit code.

Recording is on when `[self_report].enabled` is true. **The default follows
`[prompt_rewriting].enabled`**: a project that asked for the rewrite directive has opted into
the reply-shape contract, and the skills that teach the block install alongside it; a project
that turned rewriting off has said it wants no reply-shape obligations. `[self_report]` is
therefore optional and only needed to diverge (`spine.Config.self_report_enabled`).

## Edge cases
- Heading appears twice ⇒ last wins. Heading only inside a code fence ⇒ `absent`.
- Heading spelled `## Verification Status:` or `**VERIFICATION STATUS**` ⇒ recognised.
- Labels in another order ⇒ still `present` (order is a convention, presence is the contract).
- A label repeated inside the block ⇒ the last value counts.
- Block has three of four lines ⇒ `malformed`, `present_fields` lists the three.
- `Weakest claim: medium` ⇒ `graded`; `Unverified: coverage is 95% on this module` ⇒ `graded`
  (a percentage inside the block is a level, whatever it measures — the block is for naming
  claims, not scoring them); `Verified: the high-water mark test` ⇒ `present`.
- Reply that only *quotes* the template inside ``` fences ⇒ `absent`.
- Multi-entry turn (text, tool use, more text) ⇒ the last text entry is judged.
- Everything the rewrite contract lists (missing / refused / symlinked / malformed transcript,
  no human prompt, no reply) ⇒ `unknown`, hook exit 0.
- Self-report off in the spine ⇒ nothing recorded.

## Constraints
- No model calls, no network, stdlib only. Advisory: never blocks the Stop.
- Bounded I/O (transcript tail only; via `read_tail`) and bounded time (the shared hook step).
- Coupling ratchet (fan-out ≤ 2): `self_report` imports `rewrite_contract` and `verdict`;
  `status_assess` and `status` gain no new sibling import.
- Skills are measured by the context-budget ratchet: every byte added to a skill is paid for by
  a trim in the same file, and the deltas are reported with the change.
- Licence: the mechanism is re-authored under Apache-2.0; no text is copied from the
  CC BY-NC-SA source that motivated it.

## Acceptance
Unit: `tests/unit/test_self_report.py` (every outcome, exact values, fixture transcripts;
100 % line and branch), `tests/unit/test_verdict.py` (record + tally), `tests/unit/test_self_status.py`
(rendering), `tests/unit/test_spine.py` (default follows rewriting), `tests/unit/test_rewrite_contract.py`
(`final=True`). Integration (stdin protocol, excluded from mutation runs like its sibling):
`tests/integration/test_self_report_hook.py` — present / graded / absent, and the off switch.
