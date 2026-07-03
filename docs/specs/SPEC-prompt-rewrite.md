# SPEC — Prompt rewriting (Layer 1)

> Status: implemented. Approved approach: transparent (visible reading line), toggle-able, config-driven.

## 1. Purpose
Improve the **user's in-the-moment prompt** — preserve its intent and make it better — so the agent
acts on a stronger request. borromeanRings does **not** rewrite the prompt; the **wrapped agent** does.
borromeanRings injects the directive deterministically; the agent's *compliance* is not yet
verified (an injected directive is a request, not a gate) — making the contract verifiable is
tracked in issue #81.

## 2. Mechanism (Claude Code substrate)
- A **`UserPromptSubmit` hook** (`.claude/hooks/prompt_rewrite.sh`) runs when the user submits a prompt.
- It reads the spine (`borromeanrings.toml`): the `[context]` and the `[prompt_rewriting].enabled` toggle.
- If enabled, it prints a **directive** (built by `meta_harness.prompt_rewrite.build_directive`) into
  the agent's context, instructing the agent to: keep the user's intent; apply best agentic + SE
  practices; honor the declared account + value priorities; **open its reply with one line —
  `Reading this as: <sharpened request>` — so the user can correct course**, skipping it only for
  trivial follow-ups; and **stop for confirmation first** when the reading changes scope or the
  action is irreversible (merge, publish, delete, deploy). The original show-and-confirm ceremony
  on every prompt proved too expensive to survive real sessions — agents rationalized it away
  (issue #81); the contract is now cheap, visible, and reserved-confirmation.
- The agent performs the rewrite and surfaces its reading. borromeanRings wrote nothing itself.
- **Bounded payload read:** the hook reads its stdin payload under a wall-clock bound
  (`BORROMEANRINGS_HOOK_STDIN_TIMEOUT`, default 5s; `.claude/hooks/_lib.sh`) — an unclosed pipe
  must not orphan the hook's shell (the orphaned-shell regression; `tests/test_hook_stdin_timeout.py`).
- **Duplicate-registration dedupe:** the same hook can be registered at project level *and* user
  level (`install-global.sh`), so it runs twice per prompt. The directive is emitted once per
  (session, prompt): first-writer-wins claim via `meta_harness.hook_dedupe` on markers under
  `.meta-harness/hook_markers/`, freshness window `BORROMEANRINGS_HOOK_DEDUPE_WINDOW` (default 5s).
  Fail-open: an empty/unparseable payload or marker error emits the directive rather than lose it.

## 3. Principles honored
- **Agent autonomy.** The directive asks the agent to *refine the prompt*, not to follow a fixed
  plan — `how` it proceeds stays with the agent (VISION §6 red line).
- **Transparency (option a).** The agent shows the rewritten request, matching the Manifesto's
  "render what it's looking at / show what it transforms to."
- **Config-driven.** On/off lives in `borromeanrings.toml` (`[prompt_rewriting].enabled`); declared once,
  applied every prompt. Missing/invalid config → hook does nothing (never blocks the user).

## 4. Contract / tests
- `build_directive(context) -> str` — tested with and without declared context, and for the
  cheap-contract text (`tests/test_prompt_rewrite.py`).
- `spine.Config.prompt_rewriting_enabled: bool` — tested toggle (`tests/test_spine.py`).
- `hook_dedupe.claim(...)` — unit-tested semantics + hook-level integration: duplicate invocation
  emits no second directive; a new prompt gets a fresh one; empty payload fails open
  (`tests/test_hook_dedupe.py`).
- No hook may hang on an unclosed stdin pipe (`tests/test_hook_stdin_timeout.py`).
- Hook is a thin adapter; logic is in tested Python (information hiding).

## 5. Deferred
- **Verifying compliance** — deterministically checking that the agent's reply actually opened
  with the reading line on non-trivial prompts (a receipt/Stop-gate assertion): issue #81.
- Multi-prompting (multiple passes/variants), agent-specific directive tuning per harness, and using
  the rewritten prompt as an explicit artifact/receipt.
