# ADR-0063: Session charter gate — delegation terms written down and validated fail-closed

**Status:** Accepted · 2026-09-09 · closes #173 (sub-issue of #172)

## Context
Every governed run assumes a delegation: what the work is for, how much is at stake, what
"done" means, when the agent must stop, and what it may never do. Until now those terms lived
in the conversation — the prompt-rewrite directive asks the agent to sharpen the *request*,
but nothing records the *terms* — so a session that expanded scope, kept looping, or took an
irreversible step had violated nothing that was written down. AI-Fluency names this the
Delegation competency (ADR-0020); borromeanRings had the vocabulary and no artifact.

A sibling project of the maintainer's (the 4D fluency compact, `/3MagicLabs/4D`, licensed
**CC BY-NC-SA**) has a working charter mechanism whose two load-bearing ideas are worth
carrying over: the validator has no lenient path (an invalid charter is refused whole, with every problem listed), and the fields
carrying over: a charter is never repaired, defaulted, or partially accepted, and the fields
it requires grow with the stakes it declares. That project's license is incompatible with
this Apache-2.0 repository, so its text and code cannot be carried over.

## Decision
1. **A committed `CHARTER.toml`** at the project root (path configurable via
   `[charter].path`) with six generic keys — `goal`, `stakes`, `done_when`, `stop_when`,
   `may_not`, `owner` — is the record of the delegation. Committed, so it is reviewed and
   versioned with the code it governs.
2. **Stakes are two opt-in tiers, `low` and `high`, never a dial.** `high` additionally
   requires `[charter].high_stakes_fields` (default `rollback`, `reviewer`, `blast_radius`).
   A severity scale invites picking the number that requires the least; a binary asks one
   honest question. Any other value fails closed — `medium` is not rounded.
3. **Pure module `meta_harness.charter`**: frozen dataclasses, `load_charter` /
   `parse_charter`, `validate(charter, config) -> tuple[Violation, ...]`, `render`. Every
   rule yields a `Violation(field, reason)`; all are reported at once, sorted. Unknown keys
   and wrong types fail closed. A `done_when` item that is a hedge phrase or contains a hedge
   word (a small list local to the module, sourced from Matt Might's weasel-word list) is not
   a predicate; the general predicate lint is #174's module, deliberately separate.
4. **Check `22_charter`** (shared lane): rule off ⇒ pass with the rule-off message; enabled
   ⇒ the file is valid (pass, rendered) or it is not (fail, one `field — reason` line each).
   Never `noop` — a declared charter has no "nothing to inspect" state.
5. **UserPromptSubmit reminder**: when `[charter].enabled` and the file is missing, the
   existing `prompt_rewrite.sh` appends one line under 120 bytes. Advisory; validity stays
   the gate's job.
6. **This repository declares `[charter] enabled = true`** with a `stakes = "high"` charter
   (it is the gate every governed project trusts) and adds `22_charter` to its required set.
   `adopt.RECOMMENDED` is **not** changed: a charter must be written by a person, so it is
   opt-in per project, never seeded.

## License rule (recorded, not just followed)
The 4D mechanism was read to understand *what* it enforces; nothing under `4D/canon/` was
read. `SPEC-charter.md`, `meta_harness.charter`, `22_charter.sh`, the tests and this ADR are
re-authored: no sentence, code, or non-generic field name is copied. The charter's own
keys (`goal`, `stakes`, `done_when`, `stop_when`, `may_not`, `owner`) were chosen here; the
source's charter uses a different and larger field set, and the one name the two share
(`stakes`) is the generic word for the concept. Same resolution as ADR-0020.

## Alternatives considered
- **Charter in `borromeanrings.toml`** — rejected: the spine says what is *enforced*; the
  charter says what is *delegated*, changes per line of work, and deserves its own diff.
- **Front matter in a `CHARTER.md`** — rejected: two parsers (YAML front matter + prose),
  and the layout gate would need a new root-doc exception; TOML is the spine's format.
- **Three or more stakes tiers** — rejected: a dial. See decision 2.
- **Inferring a charter from the conversation** — rejected: the owner must name what they
  keep; if the gate filled in `may_not` on the author's behalf, the one field that records what the agent must not do would be the one field the agent wrote.
  keep; an inferred `may_not` is exactly the drift the gate exists to catch.
- **Failing the prompt hook when the charter is invalid** — rejected: prompt hooks are
  advisory; a blocking prompt hook in a governed project would stop the user from writing
  the very charter that is missing.

## Consequences
- (+) Delegation terms are on the record, diffed, and gated; a hedged "done" is rejected
  before it can be claimed.
- (+) Threshold-free, deterministic, stdlib-only; no model calls, no network.
- (−) One more file to write before governed work starts. Mitigated: the low tier is six
  short fields; the reminder line says exactly what is missing.
- (−) The hedge list is small by design and will miss most vague predicates; that is #174's
  job, and this module must not grow into it.
- (−) A `stakes = "high"` charter can be honest and still be wrong; the gate checks shape,
  not truth. Human Discernment stays essential (docs/AI-FLUENCY.md).
