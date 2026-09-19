# SPEC — compaction brief (PreCompact snapshot + SessionStart re-injection)

Issue #137 · ADR-0053 · module `meta_harness.compaction_brief` · hooks
`.claude/hooks/pre_compact.sh`, `.claude/hooks/session_start.sh`

## User story
As the maintainer, I want the governance state a session knows — last verdict, open
obligations, enforcement mode, identity policy — to survive context compaction, so a
failing gate or a pending ADR/survey obligation does not vanish when the transcript is
summarised.

## Contract
- `obligations(verdict) -> list[str]`: failing checks first (`is_failing`), then hollow
  (`noop`) ones; `[]` for a clean pass or no verdict. Pure.
- `render_brief(*, project, verdict, enforcement, identity, harness_home) -> str`: plain
  text, honest on every missing fact ("never run here", "no [git] identity declared"),
  bounded (at most `MAX_LISTED` obligations listed, the rest counted). Pure.
- `gather_brief(project, harness_home) -> str`: the only I/O; reads the same evidence the
  self-status view reads (`read_last_verdict`, `classify_enforcement`, `[git]`).
- `pre_compact.sh`: on any trigger, writes `.meta-harness/compaction_brief.txt` with a
  timestamp + trigger header and the brief. Exit 0 always. Inert if no `borromeanrings.toml`.
- `session_start.sh`: on trigger `compact` or `resume`, prints the brief to stdout (which
  Claude Code adds to context); any other trigger prints nothing. Exit 0 always. Inert
  outside a governed project. Reads fresh state, not the snapshot.

## Edge cases
- Garbage or empty stdin ⇒ trigger `unknown`; the hook still completes (exit 0).
- Unreadable or non-object `settings.json` ⇒ enforcement reported MANUAL, never AUTO.
- 40 failing checks ⇒ 10 listed + "… and 30 more"; brief under 2.5 kB.
- A gate that ran between PreCompact and SessionStart ⇒ the re-injected brief shows it.

## Constraints
- Advisory: neither hook blocks compaction or startup (`blockCompaction` never emitted).
- No model calls, no network, no API keys. Shell hooks time out at 30 s.
- `HOOK_SCRIPTS` (status_assess) is the single list of wired events; partial wiring is
  reported by the self-status view.

## Acceptance
Unit: `tests/unit/test_compaction_brief.py`. Integration (stdin protocol):
`tests/integration/test_compaction_hooks.py`. Inventory: `docs/HOOK-EVENTS.md`.
