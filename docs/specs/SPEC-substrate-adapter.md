# SPEC — substrate adapter (one gate, one hook set, per-substrate wiring)

**Status:** Specified, not built (research epic #142; build only on an explicit go) ·
**Decision:** ADR-0069 · **Survey:** `docs/research/HARNESS-SUBSTRATES.md` ·
**Hooks:** `.claude/hooks/*.sh` · **Gate:** `verify.sh` (unchanged by this spec)

## User story

As a user of a coding agent that is not Claude Code, I want the same gate, the same six
hooks and the same receipts to govern my sessions, so that borromeanRings's guarantee does
not depend on one vendor's hook system — and so that when a substrate *cannot* carry a
hook, the gate says so instead of pretending.

## 1. The contract our hooks already implement

Derived from the scripts, not from Claude Code's documentation. This is what any substrate
must deliver to, and accept from, the six scripts. It is the seam ADR-0005 named and
ADR-0013 made portable; the scripts do not change.

### 1.1 Environment

| Variable | Read by | Meaning |
|---|---|---|
| `CLAUDE_PROJECT_DIR` | every hook (`PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"`), `verify.sh` | the governed project root. Fallback `$PWD`. A shim on a substrate with no equivalent MUST export it from the payload's `cwd`. |
| `BORROMEANRINGS_HOME` | derived (`$HERE/../..`), never passed | where the hooks, `src/` and `verify.sh` live. A shim must invoke the scripts **in place** — never copy them — so this derivation holds. |
| `BORROMEANRINGS_HOOK_STDIN_TIMEOUT`, `BORROMEANRINGS_HOOK_DEDUPE_WINDOW`, `BORROMEANRINGS_GATE_TIMEOUT` | `_lib.sh`, `stop_gate.sh` | tuning; a shim passes them through untouched. |

Every hook is **inert** without `$PROJECT_DIR/borromeanrings.toml` (exit 0, no output). A shim
must preserve this: it may not add output or side effects of its own before that check.

### 1.2 Per-event stdin (JSON object, one per invocation, bounded read of 5 s)

| Our event | Script | Fields read | Everything else |
|---|---|---|---|
| `prompt-submit` | `prompt_rewrite.sh` | `session_id` (default `default`), `prompt` — only for the dedupe key | ignored |
| `pre-tool` | `pre_bash_guard.sh` | `tool_input.command` | ignored; the shim is responsible for only routing **shell** tool calls here |
| `post-tool` | `post_edit_format.sh` | `tool_input.file_path` | ignored; the shim routes **file-edit** tool calls here |
| `stop` | `stop_gate.sh` | `stop_hook_active` (bool; `true` ⇒ exit 0 immediately), `session_id` | ignored |
| `pre-compact` | `pre_compact.sh` | `trigger` (default `unknown`) | ignored |
| `session-start` | `session_start.sh` | `trigger` (**`compact` or `resume`** act; anything else ⇒ exit 0), `session_id` | ignored |

An empty or unparseable payload never fails a hook: each script falls back to defaults
(`prompt_rewrite.sh` emits without a dedupe key; `stop_gate.sh` treats it as a real Stop).

### 1.3 Per-event stdout / stderr / exit code

| Our event | Output the script produces | Meaning the substrate must give it |
|---|---|---|
| `prompt-submit` | plain text on stdout, exit 0 | **inject into the model's context** for this turn |
| `pre-tool` | exit 0 with **either** nothing, **or** `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"…"}}` | nothing ⇒ allow; the JSON ⇒ **the tool call must not run**, reason shown to the model |
| `post-tool` | nothing, exit 0 (side effect: `ruff format` on the file) | none |
| `stop` | exit 0 ⇒ gate passed, skipped, or escalated (stderr carries the escalation text); **exit 2 with the failure summary on stderr** ⇒ the turn must **continue**, stderr shown to the model as the reason | exit 2 = "do not stop; here is why" |
| `pre-compact` | nothing, exit 0 (side effect: `.meta-harness/compaction_brief.txt`) | none; must never block compaction |
| `session-start` | plain text on stdout (the brief), exit 0 | **inject into the model's context** |

Dedupe: `prompt_rewrite`, `stop_gate` and `session_start` claim `(event, key)` via
`meta_harness.hook_dedupe` so a double registration yields. A shim that registers a script
once per event inherits this for free; a substrate that fires an event more often than
Claude Code does (Hermes `pre_llm_call` fires per LLM call, not per prompt) relies on it.

## 2. Adapter shape

```
adapters/
  <substrate>/
    manifest.json     # declares coverage: our event -> substrate event or null, + degraded modes
    <wiring>          # the substrate's native registration file(s), e.g. hooks.json, plugin.ts
    shim.sh | shim.ts # translates payload in / output out, then execs ../../.claude/hooks/<x>.sh
    fixtures/         # one recorded substrate payload per carried event (for the conformance test)
    README.md         # install steps for that substrate, with the doc URLs the wiring was read from
```

Rules:

1. **Wiring only.** An adapter holds a manifest, the substrate's registration file, thin
   shims and fixtures. It never contains a copy of a hook script, a check, or `verify.sh`.
   Check `35_architecture` (or a layout rule) should fail the gate if `adapters/**` contains
   a file named like any `HOOK_SCRIPTS` entry or `verify.sh`.
2. **A shim does exactly three things:** (a) build our stdin JSON from the substrate's
   payload (rename fields, derive `trigger`/`stop_hook_active`, export `CLAUDE_PROJECT_DIR`
   from `cwd`); (b) exec the script in place; (c) translate the script's stdout/stderr/exit
   into the substrate's expected form. It contains **no policy**: no deny-lists, no gate
   calls, no retry counters. If a translation is the identity (Codex CLI), the shim may be
   the script itself referenced directly from the wiring file.
3. **`manifest.json`** is the single source self-status reads:

   ```json
   {
     "substrate": "codex",
     "docs_read_on": "2026-09-10",
     "events": {
       "prompt-submit":  {"native": "UserPromptSubmit", "mode": "full"},
       "pre-tool":       {"native": "PreToolUse",       "mode": "full"},
       "post-tool":      {"native": "PostToolUse",      "mode": "degraded", "note": "apply_patch carries a patch, not file_path"},
       "stop":           {"native": "Stop",             "mode": "full"},
       "pre-compact":    {"native": "PreCompact",       "mode": "full"},
       "session-start":  {"native": "SessionStart",     "mode": "full"}
     }
   }
   ```

   `mode` ∈ `full` | `degraded` | `absent`. `absent` MUST carry a `note` naming the degraded
   behaviour from §4.
4. **Self-status** (`SPEC-self-status.md`) gains one line per detected adapter:
   `substrate: codex — hooks 5/6 full, 1 degraded (post-tool), 0 absent`. Detection is by the
   presence of the substrate's wiring file in the governed project (`.codex/hooks.json`,
   `.gemini/settings.json`, …) naming a borromeanRings script — the same *script-name*
   matching ADR-0049 chose for Claude Code, so a self-governing checkout is not misreported.

## 3. Capability matrix (from the survey; re-verify at build time)

| Our event | Codex CLI | Gemini CLI | OpenCode | Hermes | Cline | Aider |
|---|---|---|---|---|---|---|
| prompt-submit | full `UserPromptSubmit` | full `BeforeAgent` (`additionalContext`) | absent | degraded `pre_llm_call` (per LLM call; dedupe) | unverified `before_agent_start` | absent |
| pre-tool | full `PreToolUse` (deny) | full `BeforeTool` (deny) | full `tool.execute.before` (throw) | full `pre_tool_call` (`action: block` / exit 2) | unverified `tool_call_before` | **absent — no deny primitive** |
| post-tool | degraded (`apply_patch` shape) | full `AfterTool` | full `tool.execute.after` | full `post_tool_call` | unverified `tool_call_after` | degraded `--auto-lint` |
| stop | full `Stop` (exit 2 + stderr) | full `AfterAgent` (`decision: deny` + `reason`) | absent (`session.idle` observer) | degraded `pre_verify` (coding turns only; shell exposure unstated) | unverified `turn_end` | degraded `--auto-test` (aider's own loop; no cap/escalation) |
| pre-compact | full `PreCompact` | degraded `PreCompress` (async, advisory) | full `experimental.session.compacting` | absent | absent | absent |
| session-start | full `SessionStart` (`compact`,`resume`) | degraded `SessionStart` (`resume` only) | absent (`session.created` observer) | degraded `on_session_start` (no injection) | unverified `session_start` | absent |
| **Adapter kind** | shell (identity) | shell (rename) | JS plugin spawning scripts | shell hooks in `config.yaml` | TS plugin spawning scripts | config flags only |

Roo Code: archived — no adapter. `unverified` means the stage name exists but no wire
contract is documented; it counts as `absent` until a fixture proves it.

## 4. Degraded modes (what happens when an event cannot be carried)

| Missing event | Degraded behaviour | What self-status reports |
|---|---|---|
| prompt-submit | The rewrite directive (ADR-0011) is not injected per turn. The shim MAY inject it once at session-start instead, or the project's instructions file (`AGENTS.md`, `GEMINI.md`, `opencode.json` `instructions`) carries it statically. | `prompt-submit: absent — rewrite directive static` |
| pre-tool (no deny primitive) | The PreToolUse guard **cannot** host. Destructive-command and wrong-identity commits are not prevented; they are still **caught**: `06_git_identity` fails the gate on wrong authorship, `08_branch` on a protected branch, and the receipts record it. Prevention degrades to detection. | `pre-tool: absent — guard is detect-only (gate backstop)` |
| post-tool | Formatting drift is not fixed per edit; `10_format` catches it at the gate, so the only cost is a possible extra retry. | `post-tool: absent — format fixed at gate` |
| stop | **The gate does not run on the agent's turn boundary.** The substrate cannot be made to retry. Fallbacks, in order: the substrate's own verify loop (aider `--test-cmd`, Hermes `pre_verify`) running `verify.sh` with the retry cap **not** enforced; otherwise CI (ADR-0008) is the only automatic gate and the session is `MANUAL` enforcement. | `stop: absent — enforcement MANUAL (CI only)` |
| pre-compact | No snapshot at compaction. The brief is re-injected at session-start only; if that is also absent, the brief is available on demand via the status skill / `status.sh`. | `pre-compact: absent — brief re-injected at session-start only` |
| session-start | No re-injection after compaction/resume. The `pre-compact` snapshot file still exists (if that event is carried) and the shim MAY inject it on the next `prompt-submit`. | `session-start: absent — brief on demand` |

A substrate carrying **neither** `pre-tool` nor `stop` cannot be reported as AUTO
enforcement under any wiring; self-status reports `MANUAL` and names the two gaps.

## 5. Conformance test (every adapter must pass before it is merged)

`tests/integration/test_adapter_conformance.py`, parametrised over `adapters/*/manifest.json`.
For each event whose `mode` is not `absent`:

1. **Inbound fidelity.** Feed `adapters/<s>/fixtures/<event>.json` (a payload recorded from
   the substrate's documented shape) to the shim with `BORROMEANRINGS_HOOKS_DIR` pointed at
   a **recorder** directory whose six scripts merely dump their stdin and environment.
   Assert the recorded stdin is a JSON object containing exactly the fields §1.2 lists for
   that event with the expected values (e.g. Gemini `source: "resume"` → `trigger:
   "resume"`; Codex `apply_patch` → `tool_input.file_path` derived, or the shim documents the
   degradation and the recorder receives an empty `file_path`), and that
   `CLAUDE_PROJECT_DIR` equals the fixture's `cwd`.
2. **Outbound fidelity.** Point the shim at a **stub** directory whose scripts emit our
   canonical outputs (§1.3): the deny JSON for `pre-tool`; exit 2 + stderr for `stop`; plain
   text for `prompt-submit` / `session-start`. Assert the shim's own stdout/exit is the
   substrate's documented form (Codex: identical; Gemini `BeforeTool`: `{"decision":"deny",
   "reason":…}`; Gemini `AfterAgent`: `{"decision":"deny","reason":…}`; Hermes
   `pre_tool_call`: `{"action":"block","message":…}` or exit 2; OpenCode: the plugin throws).
3. **Inertness.** With no `borromeanrings.toml` in the fixture's `cwd`, every shim exits 0
   with empty stdout — the plugin may write nothing to the project.
4. **No second copy.** No file under `adapters/` has the basename of any `HOOK_SCRIPTS`
   entry, `_lib.sh`, `verify.sh`, or anything under `checks/`.
5. **Manifest honesty.** Every event in `manifest.json` marked `full`/`degraded` has a
   fixture; every `absent` has a `note`; the set of keys equals the six events.
6. **Adversarial corpus unchanged** (issue #142 AC 3): the ADR-0025 corpus run through the
   adapter's `pre-tool` path yields the same accept/deny set as through the Claude Code path
   — by construction, since the script is the same, but the test proves the shim did not
   drop or mangle `tool_input.command`.

A fixture is recorded from the substrate's documentation, never hand-invented; its header
comment cites the URL and date. Live verification against an installed substrate is a
separate, manual step recorded in the adapter's README — the conformance test is what CI
can run without installing anything.

## 6. Honest limits

- **No deny primitive ⇒ no guard.** Aider has no pre-execution hook. On such a substrate the
  gate still guarantees what it guarantees everywhere: a wrong-identity commit fails
  `06_git_identity`, a protected-branch commit fails `08_branch`, a secret fails
  `12_secrets`, and every verdict is a receipt. What it does *not* guarantee is that the
  harmful command never ran. This is the ADR-0017 two-layer design with one layer missing,
  and self-status must say so.
- **No stop hook ⇒ no retry loop.** The generate → verify → retry cap → escalate loop is a
  property of the Stop hook, not of the gate. Without it the gate is a CI/status-check
  fact, not a session fact.
- **Advisory pre-compaction** (Gemini `PreCompress` "runs asynchronously") can lose the race
  with the summariser; the snapshot may post-date the summary. Harmless — the snapshot is
  evidence, the re-injection reads fresh state — but the session-start re-injection is the
  load-bearing half, and Gemini fires `SessionStart` only on `startup|resume|clear`, never
  `compact`. Degraded mode there: inject the brief on the next `BeforeAgent`.
- **In-process substrates** (OpenCode, Cline) run our scripts as child processes of a
  Bun/Node plugin; the plugin's own timeout, not ours, bounds them. A plugin timeout shorter
  than `BORROMEANRINGS_GATE_TIMEOUT` (540 s) would kill the Stop gate silently — the adapter
  README must state the substrate's timeout and the conformance test must assert the wiring
  file's timeout ≥ ours where the substrate has one (Codex default 600 s ✓; Gemini default
  60 000 ms ✗ — must be raised in the wiring).
- **Trust prompts.** Codex requires the user to "review and trust the exact hook
  definition"; Hermes asks consent on first shell-hook use. Per-project opt-in
  (`borromeanrings.toml`) remains ours; the substrate's consent is additional, never
  replaced. `init.sh --substrate <name>` writes the wiring; it never auto-accepts.
- **Documentation drift.** Every fact here is dated; an adapter that lands must re-read its
  substrate's docs the day it lands and update `manifest.json.docs_read_on`.

## 7. Out of scope

A daemon or proxy substrates talk to (rejected in ADR-0069); MCP-based governance (#141);
the executor seam (#143); ZooCode and any harness not in the survey; building any adapter —
phase 1 is a follow-up issue referenced from ADR-0069.
