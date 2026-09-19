# SPEC — session charter gate (`22_charter`)

Issue #173 (sub-issue of #172) · ADR-0063 · module `meta_harness.charter` · check
`checks/shared/22_charter.sh` · reminder in `.claude/hooks/prompt_rewrite.sh`

## User story
As a maintainer, I want the terms of a delegation — what the agent is working toward, how
much is at stake, what counts as finished, when it must stop, and what it may never do —
written down and validated fail-closed before governed work starts, so the delegation is
negotiated on the record instead of assumed from the conversation.

## The charter file
A committed `CHARTER.toml` at the governed project's root (path configurable). Committed, so
it is reviewed like code and versioned with the code it governs; TOML, so it parses with the
stdlib and reads like the spine. One table, no nesting:

| Key | Type | Meaning |
|---|---|---|
| `goal` | string | What the work is for — one paragraph, not a task list |
| `stakes` | `"low"` \| `"high"` | The tier; selects which further keys are required |
| `done_when` | list of strings | Checkable predicates; the work is finished when every one holds |
| `stop_when` | list of strings | Conditions under which the agent stops and hands back |
| `may_not` | list of strings | Actions the agent is never authorized to take |
| `owner` | string | Who answers for the delegation |

**High-stakes extras** (required when `stakes = "high"`; the key set is `[charter].high_stakes_fields`,
default `rollback`, `reviewer`, `blast_radius`): each a non-empty string. They may also appear
at `low` (declaring more than required is never a violation).

### Stakes are two opt-in tiers, never a dial
`low` and `high` are the only values. A severity scale (1–5, three named levels, …) invites
the author to pick the number that makes the fewest fields required; two tiers make the
question binary: *does this delegation need a rollback plan, a named reviewer and a stated
blast radius, or not?* Anything else is rejected — `medium` is not rounded to either tier.

## Validation rules (each yields a `Violation(field, reason)`)
1. `goal`, `owner`, and every high-stakes extra that is required: missing, empty, or
   whitespace-only ⇒ violation.
2. `stakes`: missing ⇒ violation; any value other than `low`/`high` ⇒ violation naming the
   value (fail closed — never coerced).
3. `done_when`, `stop_when`, `may_not`: missing or empty list ⇒ violation; any item empty or
   whitespace-only ⇒ violation naming the item index.
4. `done_when` hedge rule: an item whose normalized text is one of the hedge phrases
   (`works`, `it works`, `done`, `looks good`, `good enough`, `seems fine`, `should work`,
   `mostly done`, `basically done`) or that contains one of the hedge words
   (`probably`, `mostly`, `basically`, `roughly`, `seems`, `hopefully`, `largely`, `somewhat`)
   ⇒ violation. The list is small and local to this module; the general predicate lint is
   #174's. Hedge words are taken from Matt Might's weasel-word list (see module docstring).
5. Any key not in the six core keys or `high_stakes_fields` ⇒ violation `<key> — unknown key`
   (fail closed: a typo like `done_wen` must not silently make the real key "missing").
6. Type errors (a string where a list is expected, a non-string list item, a table) are
   reported as violations on that field, never coerced.

Violations are reported all at once, sorted by field then reason, so the author fixes the
file in one pass.

## Spine
```toml
[charter]
enabled = true                                            # default false ⇒ rule off
path = "CHARTER.toml"                                     # relative to the project root
high_stakes_fields = ["rollback", "reviewer", "blast_radius"]  # default
```

## Check `22_charter` (shared lane)
| State | Receipt | Log |
|---|---|---|
| `[charter].enabled` false/absent | `pass` | `charter gate not enabled ([charter].enabled=false) — rule off` |
| enabled, file missing | `fail` | `file — charter not found at <path>` |
| enabled, file unparseable | `fail` | `file — not valid TOML: <reason>` |
| enabled, violations | `fail` | one line per violation: `<field> — <reason>` |
| enabled, valid | `pass` | the rendered charter (goal, stakes, counts, owner) |

Never `noop`: once a project declares a charter, the file is either valid or it is not — there
is no "nothing to inspect" state.

## UserPromptSubmit reminder
When `[charter].enabled` is true and the file is missing, `prompt_rewrite.sh` appends exactly
one line (under 120 bytes; the context-budget ratchet measures injected text):

```
borromeanRings: [charter] is enabled but CHARTER.toml is missing — write it before governed work
```

Independent of `[prompt_rewriting].enabled`. Nothing is appended when the file exists (even
if it is invalid — that is the gate's job, not the prompt hook's). Advisory: exit 0 always.

## Edge cases
- No `[charter]` table ⇒ off; the check passes with the rule-off message.
- `[charter]` present but `enabled` absent ⇒ off (opt-in, like `[changelog]`).
- `path` pointing at a directory or an unreadable file ⇒ `file — …` violation, fail.
- A top-level TOML value that is not a table for a core key (e.g. `goal = 3`) ⇒ type violation.
- A `stakes = "high"` charter with `rollback = ""` ⇒ `rollback — required at stakes "high"; empty`.
- A `stakes = "low"` charter carrying `rollback = "git revert"` ⇒ valid.
- `done_when = ["it works"]` ⇒ `done_when[0] — hedge, not a predicate: "it works"`.

## Constraints
- Pure module: no I/O beyond `load_charter` reading one file; no model calls, no network.
- 100% line + branch coverage on `meta_harness.charter`; every rule has an exact-message test.
- Threshold-free: presence and shape facts only.
- License: the mechanism is inspired by a CC BY-NC-SA source; everything here is re-authored
  (ADR-0063). No sentence, code, or non-generic field name is copied.

## Acceptance
Unit: `tests/unit/test_charter.py`, `tests/unit/test_spine.py` (`[charter]` defaults).
Integration: `tests/integration/test_charter_gate.py` (off / valid / missing / hedged /
unknown stakes via `verify.sh`) and the reminder hook over its stdin protocol.
