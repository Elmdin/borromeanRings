# SPEC — Rewrite contract (verifying the prompt-rewrite directive)

Issue #81 · ADR-0059 · module `meta_harness.rewrite_contract` · record I/O in
`meta_harness.verdict` · hook `.claude/hooks/stop_gate.sh` · view `status_assess.render_rewrite_line`

## User story
As the maintainer, I want to *know* — not hope — that the prompt-rewrite directive
(SPEC-prompt-rewrite.md) is being honoured: when the `UserPromptSubmit` hook asked the agent
to open its reply with `Reading this as: …`, did it? The answer must come from evidence
(the session transcript), be decided deterministically without a model call, and be visible
in the project's own status — so a standard that decayed into a suggestion becomes a record.

## Contract
- **Marker.** `prompt_rewrite.MARKER == "Reading this as:"` is the single source for both the
  directive text and the verification. The directive text is unchanged by this feature.
- **`prompt_hash(prompt) -> str`** — 16 hex chars of SHA-256, identical to the dedupe digest
  `prompt_rewrite.sh` computes, so a directive injection and its verdict can be joined.
- **`is_trivial(prompt) -> bool`** — the directive's own exemption ("a bare yes/no/continue"),
  made exact: lower-cased, trimmed, trailing `.!?` stripped, then membership in
  `TRIVIAL_PROMPTS` (`y n yes no ok okay k go "go ahead" continue proceed sure "yes please"
  "yes, please" "do it" yep yeah nope`) or empty. `"yes, and also …"` is **not** trivial.
- **`assess_reply(prompt, reply, line) -> RewriteVerdict`** (pure, immutable):
  - trivial prompt ⇒ `exempt`;
  - reply's first non-blank line, leading markdown decoration (`*_#>` `` ` `` `~`) stripped,
    starts with the marker (case-insensitive) ⇒ `honoured`;
  - otherwise `not_honoured` (`reply opened with something else`, or `reply had no text`).
  - Evidence: `line` (1-based transcript line of the judged assistant entry) and `matched`
    (the opening line, capped at 200 chars).
- **`find_last_exchange(entries) -> Exchange | None`** — the last *human* prompt and the
  first assistant text after it. A human prompt is a `type: user` entry with
  `origin.kind == "human"`, not `isMeta`, whose content is a string or text-only blocks.
  Tool results, injected skill text, slash commands, task notifications and post-compaction
  summaries are not prompts the directive fired on. The reply is the first non-sidechain
  `type: assistant` entry after it with a non-empty text block (thinking/tool_use-only
  entries are skipped).
- **`read_tail(path, max_bytes=8 MiB) -> (first_line_no, lines)`** — bounded: only the tail
  is decoded; the skipped prefix is streamed in 1 MiB chunks solely to count newlines so
  line numbers are exact. A cut that does not provably start a line drops the first line.
  Refuses (`TranscriptRefused`, before reading a byte) anything not a `.jsonl` path, anything
  whose *resolved* path is not under the substrate's transcript root (symlink escapes and
  `..` traversal included), or a symlink; missing ⇒ `OSError`. The root
  (`default_transcript_root`) is `$CLAUDE_CONFIG_DIR/projects`, else `~/.claude/projects` when
  it exists, else the user's home; undeterminable ⇒ refuse. Nothing but the substrate-supplied
  `transcript_path` is ever read, whatever the payload says.
- **`evaluate_transcript(path) -> RewriteVerdict`** — never raises: unreadable/refused path,
  no human prompt in the tail, or a prompt with no assistant text ⇒ `unknown` with the
  reason.
- **`record_from_payload(project, payload_json) -> RewriteVerdict`** — parses the Stop
  payload, evaluates, appends. Garbage payload ⇒ `unknown: hook payload unreadable`; no
  `transcript_path` ⇒ `unknown: no transcript_path in the hook payload`. Both are recorded:
  the absence of evidence is evidence.
- **Record** (`verdict.append_rewrite_record`, append-only, one JSON object per line in
  `.meta-harness/rewrite_contract.jsonl`):
  `{"ts": "<UTC ISO-8601 Z>", "session_id": str, "prompt_hash": str, "honoured": true|false|null,
  "status": "honoured"|"not_honoured"|"exempt"|"unknown", "reason": str, "line": int|null,
  "matched": str}`.
- **Tally** (`verdict.read_rewrite_tally -> RewriteTally`): counts per status; malformed lines
  skipped; an unrecognised status counts as `unknown`, never as honoured (fail-closed).
  `judged = honoured + not_honoured`.
- **Self-status line** (`status_assess.render_rewrite_line`): `Rewrite: contract honoured N of M
  in this project (E exempt, U unknown)` or `contract no record`.
- **Hook.** `stop_gate.sh` records once per Stop, after the duplicate-registration claim and
  *before* the no-op guard (a reply that only answered a question is where the reading
  matters most), only when `[prompt_rewriting].enabled` is true, and never on a re-stop
  (`stop_hook_active`). It cannot change the hook's exit code.

## What is and is not verified
- Verified: that the reply to the last human prompt **opened** with the marker line.
- Not verified: that the reading is *faithful* (that needs judgement — a critic, agent-only per
  ADR-0030, deliberately not wired here); that confirmation was sought before irreversible
  actions; anything about prompts earlier than the last one in a multi-prompt turn.
- Not gated: v1 records and reports. The ratchet (`checks/shared/20_rewrite_contract.sh`,
  honoured share may not regress vs a seeded baseline, `noop` with no record) is the next step
  in ADR-0059, not part of this change — the issue asks for visibility, not a block.

## Edge cases
- Transcript missing, unreadable, not `.jsonl`, a symlink, or outside the transcript root ⇒
  `unknown` (reason `transcript path outside the substrate's transcript directory` for the
  last), hook exit 0.
- Malformed JSON lines anywhere ⇒ skipped; a wholly malformed tail ⇒ `unknown`.
- Last prompt older than the tail window ⇒ `unknown` ("no human prompt found").
- Reply opens with `**Reading this as:**` ⇒ honoured; opens with "Sure." then the marker ⇒
  not honoured (the contract is the *opening* line).
- Rewriting disabled in the spine ⇒ nothing recorded (no promise was made).
- Older transcripts without `origin` on user entries ⇒ no human prompt ⇒ `unknown` (honest).

## Constraints
- No model calls, no network, no API keys; stdlib only. Advisory: never blocks the Stop.
- Bounded memory (tail only) and bounded time: the hook step runs under
  `borromeanrings_bounded` (`BORROMEANRINGS_REWRITE_TIMEOUT`, default 10 s), so a stalled
  filesystem can never park the Stop hook; the gate's 600 s budget is untouched.
- Coupling ratchet (fan-out ≤ 2): `rewrite_contract` imports `prompt_rewrite` and `verdict`;
  `status_assess`/`status` gain no new sibling import (the record reader lives in `verdict`).

## Acceptance
Unit: `tests/unit/test_rewrite_contract.py` (honoured / not honoured / exempt / malformed /
missing / tail bounds), `tests/unit/test_verdict.py` (record + tally), `tests/unit/test_self_status.py`
(rendering). Integration (stdin protocol): `tests/integration/test_rewrite_contract_hook.py`.
