# SPEC — Prompt rewriting (Layer 1)

> Status: implemented. Approved approach: transparent (show the rewrite), toggle-able, config-driven.

## 1. Purpose
Improve the **user's in-the-moment prompt** — preserve its intent and make it better — so the agent
acts on a stronger request. borromeo does **not** rewrite the prompt; the **wrapped agent** does.
borromeo **enforces** that the rewrite happens, and happens well.

## 2. Mechanism (Claude Code substrate)
- A **`UserPromptSubmit` hook** (`.claude/hooks/prompt_rewrite.sh`) runs when the user submits a prompt.
- It reads the spine (`borromeo.toml`): the `[context]` and the `[prompt_rewriting].enabled` toggle.
- If enabled, it prints a **directive** (built by `meta_harness.prompt_rewrite.build_directive`) into
  the agent's context, instructing the agent to: keep the user's intent; apply best agentic + SE
  practices; honor the declared account + value priorities; **propose the improved prompt (and what
  changed) and — unless trivial — ask the user to confirm or edit before acting** (don't silently
  treat the rewrite as the user's words; the user steers).
- The agent performs the rewrite and shows it. borromeo enforced the process; it wrote nothing itself.

## 3. Principles honored
- **Agent autonomy.** The directive asks the agent to *refine the prompt*, not to follow a fixed
  plan — `how` it proceeds stays with the agent (VISION §6 red line).
- **Transparency (option a).** The agent shows the rewritten request, matching the Manifesto's
  "render what it's looking at / show what it transforms to."
- **Config-driven.** On/off lives in `borromeo.toml` (`[prompt_rewriting].enabled`); declared once,
  applied every prompt. Missing/invalid config → hook does nothing (never blocks the user).

## 4. Contract / tests
- `build_directive(context) -> str` — tested with and without declared context (`tests/test_prompt_rewrite.py`).
- `spine.Config.prompt_rewriting_enabled: bool` — tested toggle (`tests/test_spine.py`).
- Hook is a thin adapter; logic is in tested Python (information hiding).

## 5. Deferred
- Multi-prompting (multiple passes/variants), agent-specific directive tuning per harness, and using
  the rewritten prompt as an explicit artifact/receipt.
