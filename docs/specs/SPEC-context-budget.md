# SPEC — Context-budget ratchet

**Status:** Implemented · **Realized by:** `src/meta_harness/context_budget.py`,
`checks/shared/19_context_budget.sh`, `.borromeanrings-context-baseline` · ADR-0055 · issue #135

## Problem

Governance is paid for on every turn. Each hook line, skill file and directive
borromeanRings injects into the wrapped agent's context is a line item in the user's
token bill, and nothing measured it — so it could only grow (issue #135; evidence in
`docs/research/AGENT-TOOLING-SURVEY.md`: a popular skill benchmarked at +5% tokens for
*worse* results).

## Contract

`19_context_budget` measures the **always-loaded weight** borromeanRings adds and
**ratchets** it: the total may not regress above the recorded baseline, and there is
no absolute cap (non-regression, consistent with the project's stance against number
gates).

- **Sources**, per governed project root, in a stable order (rows sorted by path
  within each kind):
  | kind | what | when it enters context |
  |---|---|---|
  | `directive` | `prompt_rewrite.build_directive([context])`, only if `[prompt_rewriting].enabled` | every prompt |
  | `instructions` | `CLAUDE.md`, `AGENTS.md` at the root | every session |
  | `skill` | `skills/*/SKILL.md`, `.claude/skills/*/SKILL.md` | frontmatter every session; body on invocation (whole file counted — the upper bound) |
  | `hook` | the quoted literal on each line of `.claude/hooks/*.sh` whose first word is `echo`, `printf` or `deny` (the PreToolUse guard's helper, whose argument becomes `permissionDecisionReason`) | when the hook speaks to the agent (template weight; zero-literal scripts have no row) |
- **Units:** bytes (exact, UTF-8) and tokens **≈ ceil(bytes / 4)** — the prose rule
  of thumb, chosen over a tokenizer dependency; a ratchet needs a *consistent* measure,
  not an exact one. The ratchet keys on **bytes**.
- **Ratchet:** `fail iff total_bytes > baseline`, logged as
  `CONTEXT-BUDGET REGRESSION: N is above baseline M — trim what borromeanRings injects,
  or accept the new baseline deliberately`. At/below ⇒ pass; the log lists every row and
  the total. The receipt records `context_bytes` and `context_baseline`.
- **Baseline** `.borromeanrings-context-baseline`: one non-negative integer. Absent ⇒
  vacuous pass ("no baseline recorded"), like every other ratchet, until `adopt.sh`
  seeds it from current state (seeded even when `[project].package` is unset — this
  ratchet measures the tree, not the package). Present but unparseable ⇒ **fail closed**.
- **Nothing measurable** (no skills, hooks, instruction files, or directive) ⇒ `noop`
  (exit 3 from the python step), never a hollow pass (ADR-0049).

### borromeanRings's baseline

`31690` B (~7928 tokens): the directive (862), `AGENTS.md` (1230), nine `SKILL.md`
files (29110), and the `pre_bash_guard.sh` + `stop_gate.sh` templates (281 + 207). A
new or longer skill that pushes the total up fails the gate until trimmed — or the
baseline is raised on purpose, in a reviewed commit.

## Out of scope (deliberate)

- **Messages composed at run time** — `deny "$reason"` with a reason built from the
  branch/config, and the verdict table the Stop hook feeds back on failure: they vary
  per run, so ratcheting them would jitter; auditing it is the separate
  "gate output trimmed to what a reader acts on" item in #135.
- **Exact tokenization**: would add a model-specific dependency for no ratchet benefit.
- **The MCP-vs-CLI advisory** and the enhancement-catalog entry from #135: advisory
  recommender work (ADR-0037), not a gate.

## Design

Pure `measure_context_budget` / `format_report` / `hook_message_bytes` /
`estimate_tokens` (100% line+branch covered, frozen dataclasses `ContextSource` /
`ContextBudget`); the check is thin bash mirroring the complexity/coupling/docstring
ratchets. The module imports nothing from the package — the check composes it with
`spine.load_config` and `prompt_rewrite.build_directive`, so the directive is measured
exactly as the hook would inject it.
