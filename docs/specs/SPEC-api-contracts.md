# SPEC — API-usage contracts (`18_api_contracts`, `[api_contracts]`)

Issue #130 · ADR-0054 · module `meta_harness.api_contracts` · check
`checks/python/18_api_contracts.sh` · hook layer in `post_edit_format.sh` · packs in
`contracts/*.toml`

## User story
As a maintainer whose project targets a specific API (a HAL, a driver, an SDK, a
library with usage rules), I want that API's rules enforced deterministically on the
code an AI agent writes, so I stop re-explaining them every session and hoping.

## Shape
`35_architecture` (ADR-0027) already enforces **project-declared structural invariants**
with native AST analysis, fail-closed, opt-in. Import direction is one predicate; API
usage is the same shape with different predicates. No LLM, no thresholds: every rule is
binary.

## Rules (`[[api_contracts.rules]]`, or a pack under `[api_contracts].packs`)
| `kind` | fields | violation |
|---|---|---|
| `banned` | `symbol` | any call to `symbol` |
| `forbidden_in` | `symbol`, `within` (function-name glob) | a call to `symbol` lexically inside a function matching `within` |
| `must_check` | `symbol` | a call to `symbol` whose value is discarded (bare expression statement) |
| `required_arg` | `symbol`, `arg` (keyword name) | a call to `symbol` without keyword `arg` |
| `paired` | `symbol`, `pair` | a function body calling `symbol` with no call to `pair` |
| `requires_before` | `symbol`, `before` | a function body where `symbol` is called with no earlier call to `before` |

Common fields: `symbol` (dotted call target; `fnmatch` globs allowed, e.g.
`HAL_*_Init`), `message` (shown on violation), `source` (provenance: a URL or document
section — **required in packs**, optional for project rules). Matching is on the call's
dotted name as written (`asyncio.create_task`, `loop.create_task`, `create_task` are
three different spellings; a glob covers them: `*create_task`).

## Contract (pure core)
- `parse_rules(raw: Sequence[Mapping]) -> tuple[Rule, ...]`: validates kind and required
  fields; unknown kind or missing field ⇒ `ValueError` (fail closed at config time).
- `check_source(source, rules, path="") -> Report`: `Report.violations` (rule, path,
  line, message) and `Report.references` = number of calls that matched ANY rule's
  symbol, whether or not they violated. Unparseable source ⇒ one violation of kind
  `syntax` (a file the gate cannot read is not a pass).
- `check_tree(files, rules) -> Report`: fold over files.
- `load_pack(name, packs_dir) -> tuple[Rule, ...]`: reads `contracts/<name>.toml`; a pack
  rule without `source` ⇒ `ValueError`.

## Gate `18_api_contracts`
- No rules declared (no `rules`, no `packs`) ⇒ rule off, exit 0 (like `35_architecture`).
- Rules declared but `references == 0` across the tree ⇒ **`noop`** (exit 3): the rules
  matched nothing, and a green that inspected nothing must say so (ADR-0049).
- Any violation ⇒ fail, listing `path:line [kind] symbol — message (source)`.
- Unreadable config / unparseable file ⇒ fail.

## Preventive layer
`post_edit_format.sh` (PostToolUse on Edit/Write) runs `check_source` on the edited
`.py` file when rules are declared and prints violations to stdout so the agent is told
at the point of writing. Advisory there (exit 0); the gate is the backstop (ADR-0017).

## Packs
`contracts/python-asyncio.toml`: rules with sources from docs.python.org. A pack is data
(a PR adds one); the loader refuses a pack rule without provenance.

## Honest limits
- Python only in v1 (native `ast`). C/C++ needs `ast-grep` (survey-verified, MIT, no
  key); the rule vocabulary is designed to map onto it (ADR-0054 records the path, #67).
- `paired` / `requires_before` are per-function, lexical, statement-ordered: no
  inter-procedural or control-flow analysis. A pair across two functions is reported;
  that is the conservative (fail-closed) reading and is documented on the rule.
- Provenance is asserted, not verified: a cited section can still be misread.

## Acceptance
Unit: `tests/unit/test_api_contracts.py` (each rule kind: violation caught, compliant
code passes, references counted; parse/pack validation). Integration:
`tests/integration/test_api_contracts_gate.py` (fixture project: fail / pass / noop).
Hook: `tests/integration/test_api_contracts_hook.py`. Pack: `contracts/python-asyncio.toml`.
