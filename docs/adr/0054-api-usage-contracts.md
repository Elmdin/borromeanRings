# ADR-0054: API-usage contracts are deterministic AST rules, not LLM judgement

**Status:** Accepted · 2026-09-08 · closes #130

## Context
A project that targets a specific API (an embedded HAL, a driver, an SDK, a library
with usage rules) has rules like "never allocate in an ISR", "check every `HAL_x_Init`
return", "acquire is paired with release". The only way to make an AI agent honour them
was to remind it every session — prompt-level persuasion, the thing borromeanRings exists
to replace. `35_architecture` (ADR-0027) already enforces project-declared structural
invariants (import direction) with native AST analysis, fail-closed, opt-in. API usage is
the same shape with different predicates.

## Decision
1. **A rule taxonomy, each rule binary.** `banned`, `forbidden_in`, `must_check`,
   `required_arg`, `paired`, `requires_before` — declared in `[api_contracts]` or in a
   pack shipped inside the package (`src/meta_harness/contracts/`, so a by-reference install finds it next to the loader). A violation is a fact about a call site, so there is no
   threshold to tune (the threshold-free rule holds).
2. **Deterministic, AST-level, no LLM.** An LLM judge could be asked "does this code
   respect the HAL rules?", and would answer differently on different days, with no
   evidence trail, and at a token cost per file. The stdlib `ast` answers the same way
   every time, offline, and the receipt names the line.
3. **Honest about nothing.** Rules declared that matched no call site ⇒ `noop`, never
   `pass` (ADR-0049). A vacuous contract is the exact failure a "we have gates" claim
   hides.
4. **Provenance for packs.** A pack rule without a `source` is refused by the loader. A
   vendor's API rules asserted from memory are folklore with a gate attached; a cited
   section can still be misread, and that is the honest limit.
5. **Two layers** (ADR-0017): the PostToolUse hook reports violations in the file just
   edited (advisory, at the point of writing); `18_api_contracts` is the gate backstop.

## Consequences
- Python only in v1. Embedded targets are C/C++; `ast-grep` (survey-verified: MIT, no
  key, offline, machine-readable) covers both, and the rule vocabulary here maps onto
  its pattern language. That is the route for #67; adding it now would have made this
  the multi-language change rather than the contracts change.
- `paired` / `requires_before` are per-function, lexical, statement-ordered. No
  inter-procedural or path analysis; a pair split across functions is reported. This is
  the conservative reading and is documented on the rule so a false positive is a
  known trade, not a surprise.
- One shipped pack (`python-asyncio`, three rules, each citing docs.python.org). More
  packs are data PRs.
- `18_api_contracts` is in this repo's required set (rule off until rules are declared)
  and in adopt's RECOMMENDED, so governed projects can opt in by declaring rules.
