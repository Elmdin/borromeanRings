# ADR-0036 — Wave-2 critic rubric family (advisory)

**Status:** Accepted (extends ADR-0030)

## Context
Doc-drift (ADR-0030) proved the live-judge critic pattern. The rest of the T2
matrix — test-smell, error-handling, boundary-value, naming, AI-security-review —
is the *same* mechanism (a model judge external to the generator, fail-closed,
advisory) differing only in the **question asked** and **which functions** it
judges. Building six near-identical modules/checks would duplicate the plumbing.

## Decision
Add `meta_harness.critic_rubrics`: a **registry** (`RUBRICS`) of `Rubric(id,
question, scope)` entries over the shared doc-drift machinery (`extract_functions`
→ `evaluate_rubric` with an injected judge). One advisory check `56_critics`
runs the rubrics named in `[critic].rubrics` using `[critic].judge_command`. A new
semantic check is a **data entry**, not new plumbing (Single Choice).

All **advisory** and **opt-in**: `56_critics` is not in `[checks].required` and is
a no-op unless both a judge command and rubrics are configured. borromeanRings
enables the rubrics but leaves them dormant (`judge_command` empty).

## Alternatives considered
- **One module + check per rubric** — rejected: six copies of the same
  extract→judge→report plumbing. A registry keeps the mechanism in one place; the
  rubrics are data.
- **Make them required/gating now** — rejected: a non-deterministic model call must
  not gate until trusted (the seam's doctrine), and they belong on the CI heavy
  lane behind a judge secret. Advisory-first collects signal safely.
- **A grammar/lint for each concern (e.g. AST rule for bare-except)** — partly
  valid (some overlap with `ruff`/`bandit`), but the *semantic* judgment ("does
  this swallow an error that matters?", "is this test vacuous?") is exactly what a
  mechanical rule can't make — the reason the critic exists.
- **Drop `traceability` (story→test)** — done: it isn't a per-function judgment
  (it needs a requirements↔test mapping), so it doesn't fit this family; left for a
  dedicated design.

## Consequences
- (+) The Wave-2 critic family exists and is testable (100% covered with stub
  judges); wiring a judge command activates all rubrics at once.
- (+) Adding a rubric is a one-line registry entry.
- (+) Reuses doc-drift's `command_ask` adapter and fail-closed aggregation — no new
  trust surface.
- (−) Dormant on borromeanRings until a judge is wired (needs a model endpoint /
  CI secret) — shipped mechanism, not yet live enforcement (honestly advisory).
- (−) Per-function model calls are expensive at scale; acceptable because it runs
  only when opted in, and belongs on the heavy lane when promoted.
