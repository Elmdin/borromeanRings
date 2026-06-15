# ADR-0015 — Per-language check sets (borromeo adjusts the gate to the project)

**Status:** Accepted

## Context
borromeo shipped a Python-only check set (ADR-0004: prove one stack first). But borromeo must
**adjust to the project's context** — a JS project needs JS checks, a Go project needs Go checks.
The uniform check contract (ADR-0005) always allowed this; this ADR makes it config-driven.

## Decision
Checks are organized as:
- **`checks/shared/`** — language-agnostic checks that run for every project (e.g. `05_hygiene`).
- **`checks/<language>/`** — the per-language tool checks (e.g. `checks/python/` = build/format/lint/
  typecheck/test/security via ruff/mypy/pytest/bandit).

`verify.sh` reads **`[project].language`** (default `python`) from the project's `borromeo.toml` and
runs `checks/shared/` **plus** `checks/<language>/`. The language value is **sanitized** to
`[a-z0-9_-]` (no path traversal / injection). Fail-closed: if a declared language has no check set,
its required checks produce no receipts and the gate fails.

Per-project *requirements* stay config-driven and independent of language: `[checks].required`,
`[hygiene].requires`, `[context]`, `[prompt_rewriting]`. **Adding a language** = drop in
`checks/<lang>/NN_*.sh` behind the uniform contract (run → emit a receipt); nothing else changes.

## Alternatives considered
- **Tag each check with the languages it applies to** (flat dir) — rejected: messier discovery than
  one dir per language.
- **Auto-detect the language** from the repo — deferred: explicit `[project].language` first (clear,
  steerable); detection can be layered on later.

## Consequences
- (+) borromeo runs the *right* checks per project — it adjusts to context (language) as the
  Maintainer wanted; other languages are purely additive (no core change).
- (+) Security: the language value is sanitized before being used as a path.
- (−) Only the **Python** set ships today; TS/Go/etc. are follow-ups (each a `checks/<lang>/` set).
  A project that declares a language with no check set fails closed (correct, but needs the set built).
