# Hook-event inventory — where governance state can be lost or bypassed

Claude Code exposes many hook events; borromeanRings wires six. This is the inventory
the widening was decided from (#137, ADR-0053): for each event, what borromeanRings state
it could lose or should enforce, and the decision. Protocol facts are from the official
hooks reference (code.claude.com/docs/en/hooks) as read on 2026-09-08; re-verify before
relying on a detail.

| Event | Can inject context | Can block | borromeanRings state at risk | Decision |
|---|---|---|---|---|
| `UserPromptSubmit` | yes | yes | the rewrite directive (ADR-0002) | **wired** — `prompt_rewrite.sh` |
| `PreToolUse` (Bash) | yes | yes | identity policy, protected-branch pushes | **wired** — `pre_bash_guard.sh` |
| `PostToolUse` (Edit/Write) | yes | no | formatting drift | **wired** — `post_edit_format.sh` |
| `Stop` | yes | yes | the verdict itself (the gate runs here) | **wired** — `stop_gate.sh` |
| `PreCompact` | **no** | yes | last verdict, open obligations, identity policy — folded into a summary that may drop them | **wired** — `pre_compact.sh` snapshots the brief to `.meta-harness/compaction_brief.txt`; never blocks |
| `SessionStart` (`compact`, `resume`) | yes (plain stdout) | no | same state, after the summary replaced it | **wired** — `session_start.sh` re-injects a fresh brief |
| `SessionStart` (`startup`, `clear`, `fork`) | yes | no | none: CLAUDE.md and the status skill are already loaded | not wired (would duplicate) |
| `PostCompact` | yes | no | same as SessionStart(compact) | not wired — one re-injection point is enough; revisit if SessionStart(compact) proves unreliable |
| `SubagentStop` | yes | yes | a sub-agent's edits skip the Stop gate until the parent stops | **open** (#??): the parent's Stop gate still catches the tree; gating each sub-agent would multiply gate runs |
| `PostToolUseFailure` | yes | no | none owned by borromeanRings | not wired |
| `PermissionRequest` / `PermissionDenied` | yes | yes | none: the guard already decides at PreToolUse | not wired |
| `PreModelSwitch` / `PostModelSwitch` | yes | pre: yes | none: governance is model-agnostic by design | not wired |
| `TaskCreated` / `TaskCompleted` | yes | no | none | not wired |
| `ConfigChange` | yes | no | hooks being parked/disabled mid-session | candidate: could re-run the self-status enforcement classifier; deferred (advisory only, no evidence of need yet) |
| `Notification`, `TeammateIdle`, `UserPromptExpansion`, `PostToolBatch` | varies | varies | none identified | not wired |

Rules that held while deciding: a hook that fires where borromeanRings owns no state is
noise; every wired hook is inert outside a governed project; nothing here adds a model
call or an API key; the self-status view reports partial wiring when any of the six is
missing (`meta_harness.status_assess.HOOK_SCRIPTS` is the single source of that list).

## Other substrates

The six events above are the contract any other harness must carry. Which harnesses can
(Codex CLI, Gemini CLI, OpenCode, Hermes, Aider, Cline, Roo Code), on what stdin/stdout/exit
contract, and what degrades where they cannot: `docs/research/HARNESS-SUBSTRATES.md` (survey,
dated, every cell cites its doc URL) and `docs/specs/SPEC-substrate-adapter.md` (the
substrate-neutral contract the scripts implement, the `adapters/<name>/` wiring shape, the
capability matrix, degraded modes and the conformance test). Decision: ADR-0069; phase-1
target (Codex CLI): #194.
