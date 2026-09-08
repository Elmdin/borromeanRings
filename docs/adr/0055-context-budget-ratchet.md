# ADR-0055 — Context-budget ratchet (what borromeanRings itself costs per turn)

**Status:** Accepted

## Context
Every hook line, skill file and directive borromeanRings injects into the wrapped
agent's context is paid for on every turn, by the user. Nothing measured that weight,
so governance could only grow — the "token budget" concern in issue #135, backed by
`docs/research/AGENT-TOOLING-SURVEY.md` (a GitHub MCP server measured at 3× the tokens
of the `gh` CLI; a 177K★ skill at +5% tokens for worse results). The project's own
skills alone are ~30 KB.

## Decision
Add `19_context_budget` + `meta_harness.context_budget`: measure the prompt-rewrite
directive, root `CLAUDE.md`/`AGENTS.md`, every `SKILL.md`, and the hook message
templates as bytes (+ tokens ≈ bytes/4), and **ratchet the byte total** against
`.borromeanrings-context-baseline` — non-regression, no absolute cap. Nothing measurable
⇒ `noop`; an unreadable baseline fails closed. Register it in the recommended adoption
set, seeded even for package-less projects. borromeanRings's own baseline: `31893`.

## Alternatives considered
- **An absolute token cap** — rejected: an arbitrary number to game, and the right cap
  differs per project; the ratchet enforces "never worse than today" and makes growth a
  deliberate, reviewed decision (the same reasoning as ADR-0029/0031/0038).
- **A real tokenizer (`tiktoken`, a model-specific counter)** — rejected: a dependency
  tied to one vendor for a signal that only needs to be *consistent*. bytes/4 is stated
  in the docstring and the report.
- **Prompt-compression tools that need a local model** — rejected explicitly: ADR-0003
  (no local model) and the agent-only rule (no independent model calls).
- **Anything BSL / non-OSI licensed as a core dependency** — rejected explicitly:
  incompatible with this Apache-2.0 gate's own license policy (ADR-0035).
- **Ratcheting the dynamic gate output too** — deferred: it varies per run and would
  jitter; trimming it is a separate audit item in #135.

## Consequences
- (+) borromeanRings's own context weight is visible per source on every gate run and
  cannot creep upward silently; adding a skill is a conscious trade.
- (+) Zero new dependency; language-agnostic (shared lane); 100% covered pure module;
  integration-tested pass / regression / noop / unseeded / unreadable.
- (−) Tokens are approximate and the skill bodies are counted at their invocation
  upper bound; the MCP-vs-CLI advisory and the gate-output trim remain open in #135.
