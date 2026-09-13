# ADR-0059: The prompt-rewrite directive is a verified contract, recorded at Stop

**Status:** Accepted · 2026-09-08 · closes #81 · amends ADR-0011

## Context
ADR-0011 made prompt rewriting *performed by the agent, enforced by borromeanRings* — but
"enforced" meant a directive injected on every `UserPromptSubmit`. Nothing checked that the
agent's reply actually opened with the `Reading this as:` line the directive asks for, and in
real sessions it decayed: the mechanism fired, the observable contract was inconsistently
honoured, and the maintainer concluded the feature was not in effect (#81). That is the
failure class this project exists to eliminate — a standard that is a suggestion, not a gate.
The hooks-hygiene work already cheapened the contract to one line; this decision verifies it.

The Stop hook receives `transcript_path` (official hooks reference, re-read 2026-09-08): the
session's JSONL transcript, in which human prompts are marked `origin.kind == "human"` and
assistant turns carry text blocks. That is enough evidence to decide the contract
deterministically, without a model call.

## Decision
1. A pure module `meta_harness.rewrite_contract` finds the assistant turn that answered the
   last human prompt and decides `honoured` / `not_honoured` / `exempt` (the directive's own
   trivial-prompt exemption, made exact) / `unknown` (no evidence), returning an immutable
   verdict with its evidence (transcript line, matched opening text). No nonce: the marker is
   stable, so the directive text — measured by the context-budget ratchet — is unchanged.
2. **Record, don't nag.** `stop_gate.sh` appends the verdict to
   `.meta-harness/rewrite_contract.jsonl` (append-only, one JSON object per line) on every
   Stop where the directive was on, after the dedupe claim and before the no-op guard.
   Advisory: it never blocks and can never fail the hook. The self-status view reports the
   tally (`Rewrite: contract honoured N of M in this project`, or `no record`).
3. Robustness is fail-honest: a missing, unreadable, non-`.jsonl`, symlinked or malformed
   transcript, or a payload without the path, records `unknown` — never a guess, never a
   crash. Reads are bounded to the transcript's tail (8 MiB); the prefix is only streamed to
   keep line numbers exact. Nothing but the substrate-supplied path is read, and only when
   it resolves under the substrate's transcript directory (`$CLAUDE_CONFIG_DIR/projects`,
   else `~/.claude/projects`, else home) — defense in depth against a crafted payload. The
   hook step is wall-clock bounded (10 s default).
4. The record I/O lives in `meta_harness.verdict` beside the other persisted `.meta-harness`
   records, so `status_assess` and `status` keep their fan-out at the coupling baseline
   instead of growing a third import.
5. Not a gate in v1. The issue asks that failures become *visible* (a receipt), and a block
   here would fight the very autonomy the directive respects. The next step, if the record
   shows decay, is a threshold-free **ratchet** `checks/shared/20_rewrite_contract.sh`: the
   honoured share may not regress against a seeded baseline; `noop` when there is no record.

## Alternatives considered
- **Per-prompt nonce in the directive** — rejected: the marker is already unambiguous, and a
  nonce changes the directive every prompt (context-budget churn, harder to read).
- **A model judge of the reading's faithfulness** — rejected for now: agent-only per ADR-0030,
  costs a call per Stop, and faithfulness is not what decayed; the *opening line* did.
- **Block the Stop when the contract is broken** — rejected for v1: nagging is the ceremony
  that got rationalised away; a record plus a ratchet is the borromeanRings way.
- **Verify in `UserPromptSubmit`** — impossible: the reply does not exist yet.

## Consequences
- The rewrite feature now has a truth: `status.sh` says how often the contract held here.
- One more sub-second Python step per Stop (tail read of the transcript).
- Transcripts from substrates that do not mark human prompts yield `unknown`, honestly.
- SPEC-prompt-rewrite.md now states what is enforced (the opening line) vs requested
  (faithfulness, confirmation-first).
