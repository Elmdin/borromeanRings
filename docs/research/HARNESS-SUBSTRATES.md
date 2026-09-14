# Harness substrates — can they carry borromeanRings's six hooks?

Issue #142 · ADR-0069 · spec `docs/specs/SPEC-substrate-adapter.md` · read on 2026-09-09/10

borromeanRings wires six events on Claude Code (`docs/HOOK-EVENTS.md`): prompt-submit,
pre-tool, post-tool, stop/turn-end, pre-compact, session-start. This survey asks, for each
other coding-agent harness the epic names, whether it has a mechanism that can carry those
six, and on what contract. **Every fact is from a public documentation page read on the date
above; every cell says which. Nothing was installed, no account was created. A cell reading
"not documented" means the page(s) read do not state it — it is not a guess either way.**
Re-verify before building: these products release weekly.

## What was read, and what could not be

| Substrate | Pages read | Could not be read |
|---|---|---|
| Codex CLI (OpenAI) | `https://developers.openai.com/codex/hooks` → 308 to `https://learn.chatgpt.com/docs/hooks` (read); `https://github.com/openai/codex` (README); `https://github.com/openai/codex/releases` | — |
| Gemini CLI (Google) | `https://geminicli.com/docs/hooks/`; `https://geminicli.com/docs/hooks/reference/`; `https://github.com/google-gemini/gemini-cli` (README); `.../releases` | a *stable* (non-nightly) release tag was not shown on the releases page read |
| OpenCode (anomalyco) | `https://opencode.ai/docs/plugins/`; `https://opencode.ai/docs/config/`; `https://github.com/anomalyco/opencode` (README); `.../releases` | — |
| Hermes Agent (Nous Research) | `https://hermes-agent.nousresearch.com/docs/` (index); `.../docs/user-guide/features/hooks`; `.../docs/user-guide/features/plugins`; `.../docs/user-guide/features/skills`; `https://github.com/NousResearch/hermes-agent` (README); `.../releases`; `.../issues/2817` | — |
| Aider | `https://aider.chat/docs/config/options.html`; `https://aider.chat/docs/usage/lint-test.html`; `https://github.com/Aider-AI/aider` (README); `.../releases` | — |
| Cline | `https://docs.cline.bot/features/hooks` and `https://docs.cline.bot/customization/hooks.md` (both only point to "SDK Plugins"); `https://docs.cline.bot/sdk/plugins`; `https://docs.cline.bot/customization/plugins.md`; `https://docs.cline.bot/sdk/reference/events.md`; `https://docs.cline.bot/llms.txt`; `https://github.com/cline/cline` (README); `.../releases` | the hook **wire contract** (payload fields, return type) is on none of the pages above; the releases page fetch returned a date ("Desktop v0.0.24, September 9, 2024") that could not be reconciled with the repo's activity — treat the release date as **unverified** |
| Roo Code | `https://docs.roocode.com/features/hooks` → 301 to `https://roocodeinc.github.io/Roo-Code/features/hooks` → **404**; `https://github.com/RooCodeInc/Roo-Code` (README); `.../releases` | the hooks page does not exist; the project is archived (below) |

## Summary matrix

Legend: **Y** = documented and usable for our purpose · **Y\*** = documented with a caveat in
the substrate's section · **obs** = an observer-only event fires (cannot block, cannot inject)
· **—** = not documented on the pages read.

| Capability | Claude Code (reference) | Codex CLI | Gemini CLI | OpenCode | Hermes | Aider | Cline | Roo Code |
|---|---|---|---|---|---|---|---|---|
| Hook/plugin mechanism | shell hooks, JSON stdin/stdout | shell hooks, JSON stdin/stdout | shell hooks, JSON stdin/stdout | in-process JS/TS plugin functions | Python plugins **and** shell hooks (JSON stdin/stdout) | none (lint/test commands only) | in-process TS plugin functions | none (archived) |
| prompt-submit | Y `UserPromptSubmit` | Y `UserPromptSubmit` | Y `BeforeAgent` | — | Y\* `pre_llm_call` | — | Y\* `before_agent_start` | — |
| pre-tool (Bash) | Y `PreToolUse` | Y `PreToolUse` | Y `BeforeTool` | Y `tool.execute.before` | Y `pre_tool_call` | — | Y\* `tool_call_before` | — |
| post-tool (Edit/Write) | Y `PostToolUse` | Y\* `PostToolUse` | Y `AfterTool` | Y `tool.execute.after` | Y `post_tool_call` | Y\* `--auto-lint` | Y\* `tool_call_after` | — |
| stop / turn-end | Y `Stop` | Y `Stop` | Y `AfterAgent` | obs `session.idle` | Y\* `pre_verify` | Y\* `--auto-test` | Y\* `turn_end` | — |
| pre-compact | Y `PreCompact` | Y `PreCompact` | Y\* `PreCompress` (async, advisory) | Y `experimental.session.compacting` | obs `session:compress` (gateway only, *post*) | — | — | — |
| session-start (after compact/resume) | Y `SessionStart` (`compact`,`resume`) | Y `SessionStart` (`compact`,`resume`) | Y\* `SessionStart` (`resume`; **no `compact`**) | obs `session.created` | Y\* `on_session_start` (return ignored) | — | Y\* `session_start` | — |
| Can inject context | Y | Y (`additionalContext`, plain stdout) | Y (`additionalContext`) | at compaction only (`output.context`) | Y (`pre_llm_call` return) | via command output only | Y\* | — |
| Can deny a tool call | Y | Y (`permissionDecision: deny`) | Y (`decision: deny`) | Y (throw) | Y (`action: block`; exit 2) | **no** | Y\* | — |
| stdin/stdout/exit contract | JSON / JSON or text / 0, 2 | JSON / JSON or text / 0, 2, other | JSON / JSON / 0, 2, other | n/a (function args) | JSON / JSON / 0, 2 | n/a | n/a (function args) | — |
| Six-event coverage | 6/6 | **6/6** | 6/6 (two degraded) | 3/6 + 2 observer | 4/6 (two degraded) + 1 observer | 0/6 (two analogues) | 4–5/6 unverified | 0/6 |

## Codex CLI (OpenAI)

Source: `https://learn.chatgpt.com/docs/hooks` (the canonical `developers.openai.com/codex/hooks`
308-redirects there), `https://github.com/openai/codex`, `https://github.com/openai/codex/releases`.

- **Mechanism.** Shell command hooks. Events: `SessionStart`, `SessionEnd`, `SubagentStart`,
  `SubagentStop`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, `PreCompact`,
  `PostCompact`, `UserPromptSubmit`, `Stop`, `Interrupt`. "Hooks are enabled by default";
  `[features] hooks = false` disables them.
- **Our six.** All six, under the same names Claude Code uses: `UserPromptSubmit`,
  `PreToolUse` (matcher `"Bash"`; `tool_input.command`), `PostToolUse` (file edits are
  `apply_patch`; matcher values `apply_patch`, `Edit`, `Write` are documented), `Stop`
  (`stop_hook_active`, `last_assistant_message`), `PreCompact` (`trigger`: `manual` | `auto`),
  `SessionStart` (`source`: `startup`, `resume`, `clear`, `compact`).
- **stdin.** "Every command hook receives one JSON object on `stdin`" with `session_id`,
  `transcript_path`, `cwd`, `hook_event_name`, `model`, `permission_mode`; turn-scoped
  events add `turn_id`. "Commands run with the session `cwd` as their working directory."
  Environment variables passed to hooks: not documented (no `CLAUDE_PROJECT_DIR` analogue).
- **stdout / exit.** Exit 0 = continue, stdout parsed (plain text on `UserPromptSubmit` and
  `SessionStart` "is added as extra developer context"; JSON `hookSpecificOutput.additionalContext`
  likewise). Exit 2 = "Blocking decision; reads reason from stderr". Other = "Hook failure
  reported; operation continues". `Stop` also accepts JSON `decision: "block"` + `reason`
  ("using your `reason` as that prompt text"). Context injection default limit ~2,500 tokens
  (`additionalContextLimit`).
- **Deny.** `PreToolUse` → `{"hookSpecificOutput": {"permissionDecision": "deny",
  "permissionDecisionReason": "..."}}`; `"ask"` is "parsed but not supported yet";
  `updatedInput` only with `allow`.
- **Caveat (post-tool).** Edits arrive as `apply_patch` with `tool_input.command` (the patch),
  not a `file_path`; `post_edit_format.sh` reads `tool_input.file_path`, so the shim must
  derive paths from the patch text or the hook degrades to a no-op.
- **Install / config.** `npm install -g @openai/codex` or `brew install --cask codex`.
  Hooks in `~/.codex/hooks.json`, `~/.codex/config.toml` (`[hooks]` tables),
  `<repo>/.codex/hooks.json`, `<repo>/.codex/config.toml`. "Project-local hooks load only when
  the project `.codex/` layer is trusted" and "Codex requires you to review and trust the exact
  hook definition" before a non-managed hook runs. Timeout default 600 s.
- **License / release.** Apache-2.0. Latest release read: `0.154.0`, 2026-09-09.

## Gemini CLI (Google)

Source: `https://geminicli.com/docs/hooks/`, `https://geminicli.com/docs/hooks/reference/`,
`https://github.com/google-gemini/gemini-cli`, `.../releases`.

- **Mechanism.** Shell command hooks in `settings.json` under `"hooks"`. Events:
  `SessionStart`, `SessionEnd`, `BeforeAgent`, `AfterAgent`, `BeforeModel`, `AfterModel`,
  `BeforeToolSelection`, `BeforeTool`, `AfterTool`, `PreCompress`, `Notification`.
- **Our six.** prompt-submit = `BeforeAgent` (`prompt`; can deny; `additionalContext`
  "appended to prompt"). pre-tool = `BeforeTool` (`tool_name`, `tool_input`; deny; may modify
  `tool_input`; **cannot** add context). post-tool = `AfterTool` (`tool_response`;
  `additionalContext`). stop/turn-end = `AfterAgent` (`prompt_response`, `stop_hook_active`;
  `decision: "deny"` + `reason` — "This text is sent to the agent as a new prompt to request a
  correction"). pre-compact = `PreCompress` (`trigger`: `auto` | `manual`) — **"runs
  asynchronously"** and "cannot block or modify the compression process". session-start =
  `SessionStart` (`source`: `startup` | `resume` | `clear` — **no `compact` source**;
  `additionalContext` "injected as first turn or prepended").
- **stdin.** `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `timestamp` plus
  per-event fields. Built-in tool names include `run_shell_command`, `read_file`, `write_file`;
  the shell tool's `tool_input` carries `command`. Environment variables: not documented.
- **stdout / exit.** Exit 0: stdout parsed as JSON (`decision`, `reason`, `systemMessage`,
  `continue`, `suppressOutput`, `hookSpecificOutput`). Exit 2: "System Block; action blocked;
  `stderr` used as rejection reason". Other: non-fatal warning. Plain-text stdout as context:
  not documented (JSON is the documented channel).
- **Deny.** `BeforeTool` → `{"decision": "deny", "reason": "..."}`.
- **Install / config.** `npm install -g @google/gemini-cli` (also `npx`, `brew`, MacPorts).
  Config precedence `.gemini/settings.json` (project) → `~/.gemini/settings.json` (user) →
  `/etc/gemini-cli/settings.json` (system) → extension hooks. Timeout in **milliseconds**,
  default 60000; per-matcher `sequential` flag.
- **License / release.** Apache License 2.0. Latest tag shown on the releases page read:
  `v0.61.0-nightly.20260910.ged2ac40df` (2026-09-10); a stable tag was not shown.

## OpenCode (anomalyco)

Source: `https://opencode.ai/docs/plugins/`, `https://opencode.ai/docs/config/`,
`https://github.com/anomalyco/opencode`, `.../releases`.

- **Mechanism.** In-process JavaScript/TypeScript plugins: an async function receiving
  `project, directory, worktree, client, $` that returns a hooks object. Loaded from
  `.opencode/plugins/` (project), `~/.config/opencode/plugins/` (global), or npm via the
  `"plugin"` array in `opencode.json` ("npm plugins are installed automatically using Bun at
  startup"). No stdin/stdout/exit-code contract exists — hooks are function calls, so an
  adapter is a plugin that **spawns** our scripts.
- **Our six.** pre-tool = `tool.execute.before` (`input.tool`, mutable `output.args`; blocking
  by `throw new Error(...)`). post-tool = `tool.execute.after`. pre-compact =
  `experimental.session.compacting` (`output.context.push(...)` "inject additional context
  into compaction prompt", or replace `output.prompt`) — the only substrate that lets a hook
  shape the *summary itself*. stop/turn-end = `session.idle` via the generic `event` hook
  (observer; blocking the turn: not documented). session-start = `session.created` (observer;
  context injection at that point: not documented). prompt-submit: **not documented** on the
  plugins page (`chat.message` and the `experimental.chat.*.transform` hooks were looked for
  and are absent from the page read).
- **Deny.** Yes — throw inside `tool.execute.before`.
- **Install / config.** `curl -fsSL https://opencode.ai/install | bash`, `npm i -g
  opencode-ai@latest`, `brew install anomalyco/tap/opencode`. Config `opencode.json` /
  `opencode.jsonc` at project root or `~/.config/opencode/opencode.json`; `"permission"`
  (`edit`/`bash`: `"ask"`), `"instructions"` (paths/globs for model context).
- **License / release.** MIT. Latest release read: `v1.18.30`, 2026-09-09.

## Hermes Agent (Nous Research)

Source: `https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks`,
`.../features/plugins`, `.../features/skills`, `https://github.com/NousResearch/hermes-agent`,
`.../releases`, `.../issues/2817`.

- **Mechanism.** Two: Python plugins (`~/.hermes/plugins/<name>/plugin.yaml` + module with
  `register(ctx)`; `ctx.register_hook("event", cb)`) and **shell hooks** declared in
  `~/.hermes/config.yaml` under `hooks:` (`matcher` regex — `pre/post_tool_call` only —
  `command`, `timeout` seconds default 60 max 300, `fail_closed`), scripts by convention in
  `~/.hermes/agent-hooks/`. Shell hooks use a "JSON wire protocol on stdin/stdout" and accept
  **both** the Hermes form (`{"action": ...}`) and the "Claude-Code compatible"
  `{"decision": ...}` form. First use requires consent (`hooks_auto_accept`, `--accept-hooks`,
  `HERMES_ACCEPT_HOOKS=1`); the allowlist persists to `~/.hermes/shell-hooks-allowlist.json`.
- **Our six.** pre-tool = `pre_tool_call` (`tool_name`, `args`, `session_id`, ...; return
  `{"action": "block", "message"}` "short-circuits the tool with that text as the error";
  "Exit code 2 blocks `pre_tool_call` even without JSON output"; timeouts **fail closed** for
  this hook only). post-tool = `post_tool_call` (observer). prompt-submit ≈ `pre_llm_call`
  (`user_message`, `is_first_turn`; a returned string or `{"context": ...}` "appends to user
  message") — fires before **every** LLM call, not once per prompt, so the shim must dedupe
  (our `prompt_rewrite.sh` already claims per `(session, prompt)`). stop/turn-end ≈
  `pre_verify` ("blocking gate at code-edit verification": `attempt`, `final_response`,
  `changed_paths`; `{"decision": "block", "reason"}` is accepted as "Claude-Code compatible
  (block = continue)") — fires on coding turns that changed files, which is exactly when our
  gate matters; whether it is exposed to *shell* hooks is not stated. session-start =
  `on_session_start` ("fires once when a brand-new session is created. Does not fire on
  session continuation"; return ignored → **no context injection**; Python plugins have
  `ctx.register_system_prompt_section` instead). pre-compact: **none**; `session:compress` is
  gateway-only, fires after "Context compression completed", return ignored.
- **Reliability caveat.** Issue #2817 (opened 2026-03-24, closed "not planned") reported
  `pre_llm_call`, `post_llm_call`, `on_session_start`, `on_session_end` "documented but never
  invoked" — only the tool-call hooks were wired at that time. The current docs say
  `on_session_start` now fires "in the agent loop and CLI/gateway". An adapter must verify
  each event fires with a live fixture before claiming it.
- **Install / config.** `curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash`.
  Config `~/.hermes/config.yaml` (`plugins.enabled/disabled`, `plugins.hook_callback_timeout`
  default 30 s, max 600).
- **License / release.** MIT. Latest release read: `v2026.9.7` ("Hermes Agent v0.21.1"),
  2026-09-07.

## Aider

Source: `https://aider.chat/docs/config/options.html`, `https://aider.chat/docs/usage/lint-test.html`,
`https://github.com/Aider-AI/aider`, `.../releases`.

- **Mechanism.** No hook, plugin or event system is documented. What exists: `--lint-cmd`
  with `--auto-lint` (default on; "aider will lint any files which it edits"; "expects the
  command to print [errors] on stdout/stderr and return a non-zero exit code"; "Aider will
  try and fix any errors if the command returns a non-zero exit code"), `--test-cmd` with
  `--auto-test` (default off; same feedback loop), `--auto-commits`, `--git-commit-verify`,
  `--notifications-command`.
- **Our six.** post-tool ≈ `--auto-lint` per edited file (could run `ruff format`, i.e. our
  `post_edit_format.sh` body); stop/turn-end ≈ `--auto-test` running `verify.sh` (a failing
  gate's output is fed back for a fix attempt — the loop is aider's, not ours; the retry cap
  and escalation in `stop_gate.sh` are not reproducible). prompt-submit, pre-tool, pre-compact,
  session-start: **none**. Cannot deny a command (no pre-execution point exists). Context
  injection only through what the lint/test command prints.
- **Install / config.** `python -m pip install aider-install && aider-install`. Config
  `.aider.conf.yml` (git root, cwd or home), `.env`.
- **License / release.** Apache-2.0. Latest release read: `v0.86.0`, 2025-08-09 — thirteen
  months before this survey.

## Cline

Source: `https://docs.cline.bot/sdk/plugins`, `https://docs.cline.bot/customization/plugins.md`,
`https://docs.cline.bot/customization/hooks.md`, `https://docs.cline.bot/sdk/reference/events.md`,
`https://github.com/cline/cline`.

- **Mechanism.** Plugins (`~/.cline/plugins/_installed/{npm,git,remote,local}/` or
  `.cline/plugins/`; manifest = `package.json` `"cline"` field with `"capabilities":
  ["tools", "hooks"]`) written in TypeScript, in-process. The SDK page lists lifecycle stages
  `input, runtime_event, session_start, run_start, iteration_start, turn_start,
  before_agent_start, tool_call_before, tool_call_after, turn_end, stop_error, iteration_end,
  run_end, session_shutdown, error` and hook names `beforeRun, afterRun, beforeModel,
  afterModel, beforeTool, afterTool, onEvent`; policies carry `timeoutMs`, `retries`,
  `failureMode`, `mode`. The user-facing hooks page contains only a pointer to the SDK page.
- **Our six.** prompt-submit ≈ `before_agent_start` ("Inject context or modify
  prompt/messages"); pre-tool = `tool_call_before` ("Audit or block tool calls"); post-tool =
  `tool_call_after`; stop/turn-end ≈ `turn_end`; session-start = `session_start`;
  pre-compact: **not documented**. Payload fields, return types and whether a hook can spawn a
  shell command are **not documented** on any page read — the mapping above is by stage name
  only and is unverified.
- **Install / config.** VS Code Marketplace `saoudrizwan.claude-dev`; `npm i -g cline`;
  desktop app from GitHub releases; JetBrains Marketplace.
- **License / release.** Apache 2.0. Latest release: tag `Desktop v0.0.24` was shown; the
  date returned by the fetch is not trusted (see the table above).

## Roo Code

Source: `https://github.com/RooCodeInc/Roo-Code`, `.../releases`; the hooks docs URL 404s.

- "This repository was archived by the owner on May 15, 2026. It is now read-only." README:
  "The Roo Code Extension was shut down on May 15th"; it points users to "ZooCode (a fork
  started by the Roo Code community) and Cline (from where Roo Code originated)". Latest
  release `v3.54.0`, 2026-05-15. Apache-2.0. **Not a candidate.** ZooCode was not surveyed.

## Reading of the results

1. **Codex CLI is a near-copy of the Claude Code hook contract** — same six event names,
   same `session_id`/`cwd`/`hook_event_name` stdin envelope, same exit-0/exit-2-with-stderr
   semantics, same `hookSpecificOutput.permissionDecision` deny and `additionalContext`
   injection, and a `SessionStart` with `source: compact`. The only translations an adapter
   needs are the absent `CLAUDE_PROJECT_DIR` (derive from `cwd`) and the `apply_patch` edit
   shape. It is the phase-1 target in ADR-0069.
2. **Gemini CLI carries all six** but under different names, with millisecond timeouts, an
   async advisory `PreCompress`, and no `compact` source on `SessionStart` — so the brief can
   be re-injected only on `resume`, or on the *next* `BeforeAgent`.
3. **OpenCode and Cline have the events but not the wire**: their hooks are in-process
   functions, so the adapter is a small JS/TS plugin that spawns our scripts with a
   synthesised payload. OpenCode documents no prompt-submit hook and no way to block the turn
   at `session.idle`; Cline documents no payload at all.
4. **Hermes is the only one with a documented Claude-Code-compatible output form**, but its
   coverage is partial (no pre-compact, no context injection at session start) and its
   non-tool hooks have a history of being documented before they fired.
5. **Aider has no hook surface** and has not released in thirteen months; **Roo Code is
   archived.** Neither can host the gate as a hook; aider can at most run `verify.sh` as its
   `--test-cmd`.
