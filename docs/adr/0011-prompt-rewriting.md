# ADR-0011 — Prompt rewriting: enforced by borromeo, performed by the agent

**Status:** Accepted

## Context
The user identified prompt rewriting as a key feature: improve the user's in-the-moment prompt
(preserve + improve intent) using the declared context. Critically, the **wrapped agent** should do
the rewriting (its own intelligence), and borromeo should only **enforce** that it happens, the
right way — per best agentic + SE practices and the spine's declared context. This must respect
agent autonomy and be transparent.

## Decision
A **`UserPromptSubmit` hook** injects a directive (built by `meta_harness.prompt_rewrite`) from the
spine's `[context]`, instructing the agent to rewrite the user's request, honor the declared context,
and **show the rewrite before proceeding**. Toggle lives in `borromeo.toml`
(`[prompt_rewriting].enabled`). borromeo writes nothing into the prompt itself.

Chosen: **(a) transparent + toggle-able + config-driven.**

## Alternatives considered
- **Silently apply the rewrite (option b)** — rejected: less visibility; conflicts with the
  Manifesto's "show what it transforms to."
- **borromeo rewrites the prompt itself** — rejected: contradicts the user's clarification and the
  autonomy principle; borromeo enforces, the agent performs.
- **Always-on, not toggle-able** — rejected: the user should control it; config-driven on/off fits
  the spine.

## Consequences
- (+) The agent's own intelligence does the rewriting; borromeo guarantees the process + context.
- (+) Transparent (shown) and config-driven (declared once, applied every prompt).
- (+) Fails open *for the prompt path only*: missing/invalid config → hook does nothing, never
  blocks the user (distinct from the gate, which fails closed).
- (−) Substrate-specific (Claude Code `UserPromptSubmit`); other substrates need their own adapter
  (consistent with the Adapter seam). Multi-prompting and per-harness tuning deferred.
