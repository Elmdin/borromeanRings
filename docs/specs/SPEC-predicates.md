# SPEC — Predicate lint (hedge words + graph integrity in acceptance predicates)

Check `23_predicates` · module `meta_harness.predicates` · ADR-0064 · issue #174 (sub-issue
of #172). Opt-in per project via `[predicates].enabled`; fail-closed; threshold-free.

## Problem
This repo's own container SPEC once promised not to judge "whether a HEALTHCHECK command
is meaningful". *Meaningful* has no yes/no answer — "whether the HEALTHCHECK command probes
the service" does. Such qualifiers pass review because they *sound* like requirements.
This repo's own contracts live in SPEC `Contract`/`Guarantees` bullets, ADR `Consequences`
bullets phrased as obligations, and issue-form acceptance checkboxes — none of which any
gate reads today. A SPEC can also be written that no check, test, or issue ever points back
to — a contract with no enforcement path. Both defects are mechanical to detect.

## Contract
`23_predicates` extracts **predicates** from the documents under `[predicates].paths`,
lints each for **hedge words**, and — when `require_reference` is on — reports every SPEC
that names nothing verifiable (an **orphan**). Any finding fails the gate.

### What counts as a predicate
Documents are classified by filename, never by content:

| Kind | Filename rule | Predicates |
|------|---------------|------------|
| SPEC | `SPEC*.md` | every markdown list item (`-`, `*`, `+`, `N.`, `N)`, any nesting) under a heading whose normalized title is one of `acceptance`, `acceptance criteria`, `contract`, `contracts`, `guarantees` |
| ADR | `NNNN-*.md` (four digits, hyphen) | list items under a `consequences` heading **that state an obligation** — the item contains the word `must`, `never`, or `shall` |
| issue form | `*.yml` / `*.yaml`, or any `*.md` inside a directory named `ISSUE_TEMPLATE` | every task-list line `- [ ] text` / `- [x] text`, anywhere in the file; placeholder items whose text is only dots (`...`, `…`) are skipped |
| anything else | — | no predicates |

Heading normalization: strip the leading `N.`/`N.N` numbering, lower-case, and keep only the
text before the first ` — `, ` (`, `: ` (a colon followed by whitespace or ending the
title) or ` / ` — so `## 3. Contract (the seam)` and
`## 7. Contract / definition of "done"` both select. A predicate section ends at the next
heading of the same or a higher level. A list item's continuation lines (indented, non-blank)
are joined into the item; the reported line is the item's first line. Inside an item, an
indented line that starts with a number other than 1 (``0047) had …``) is a continuation,
not a new ordered item (CommonMark's interruption rule). Fenced code blocks are
skipped. A predicate is the item text with inline markdown left as-is; matching is
case-insensitive on whitespace-normalized text.

### Hedge words
`hedged(predicate) -> str | None` returns the first offending term, or `None`. A term matches
as a whole word or phrase: not preceded or followed by a word character or a hyphen, so
`best-effort` (a technical term here) is not `best effort`, and `properly` inside
`improperly` is not a hit. The built-in list is grouped by the ambiguity categories in
**ISO/IEC/IEEE 29148:2018 §5.2.7** ("Requirements language criteria": loopholes, vague
adjectives/adverbs, open-ended and non-verifiable terms, superlatives) and the
**INCOSE Guide for Writing Requirements** (rules on vague, subjective and open-ended terms);
the words themselves are this repo's own instantiation, chosen against its own documents:

```text
# loopholes
as appropriate · as applicable · as needed · when needed · as necessary · when necessary
if necessary · if possible · where possible · if feasible · where feasible · where relevant
where applicable · as required
# vague qualifiers
appropriate · appropriately · reasonable · reasonably · adequate · adequately · sufficient
sufficiently · suitable · suitably · proper · properly · acceptable · timely · minimal
meaningful · robust · user-friendly · intuitive · easy · easily · seamless · seamlessly
efficient · efficiently · quickly · significant · significantly
# approximations
approximately · roughly · mostly · generally · typically · usually · normally · often
sometimes · several · various
# open-ended
etc · and so on · and/or · and more
# judgment calls
best judgment · best effort · carefully · thoroughly · optimal · optimally
```

`[predicates].hedges` **adds** project terms (never replaces the built-ins). The fix for a
finding is to replace the qualifier with the yes/no fact it stands for — the rewrites made
in this repo: "whether a HEALTHCHECK command is *meaningful*" → "whether a HEALTHCHECK
command probes the service" (SPEC-container); "write a *minimal* Keep-a-Changelog file" →
"a file containing only the header and an `## [Unreleased]` section" (SPEC-adopt);
"*robust* to the variance in license strings" → the concrete spellings that must match
(SPEC-licenses). Prose that is genuinely advisory belongs outside the predicate section,
not hedged inside it. **Quoted third-party text** (a verbatim quotation of another
document, standard or tool output) is not one of this repo's predicates and is exempt from
the rule — but the lint has no quote detection, so keep such quotations outside the
predicate section or inside a fenced block (which is skipped).

### Graph integrity (orphans)
`orphans(documents, known_checks, known_tests)` returns the SPEC paths that name **no
existing check id**, **no existing test file** and **no issue**. A reference may appear
anywhere in the SPEC (a `Verified by: test_x.py` line is the convention):

- check id — a token `NN_name` that is one of `known_checks` (every `checks/*/NN_*.sh`
  the governing borromeanRings ships);
- test file — a token `test_*.py` whose basename is one of `known_tests` (every
  `test_*.py` under the project's `tests_dir`);
- issue — `#N` with N ≥ 1 (syntactic only: there is no network on the gate, so an issue
  reference is accepted as written and recorded as unverified in the ADR).

**Non-vacuity rule (learned from 4D):** only *resolvable* references count. A check id that
matches the shape but is not shipped, a test file that does not exist, or a wildcard such as
"all checks" does not rescue a SPEC — otherwise every SPEC would trivially reference
something and the orphan set would be empty by construction. The test suite contains a mutation-driven
test (`test_predicates.py::test_orphan_detector_is_not_vacuous`) that replaces the detector
with one returning nothing and asserts the orphan assertions then fail; the heavy lane's
`60_mutation` ratchet covers the rest of the module.

### Config `[predicates]`
| Key | Default | Meaning |
|-----|---------|---------|
| `enabled` | `false` | off unless true (per-project opt-in) |
| `paths` | `["docs/specs", "docs/adr", ".github/ISSUE_TEMPLATE"]` | directories (relative to the project root) scanned recursively; a missing directory is skipped |
| `hedges` | `[]` | extra hedge terms, appended to the built-ins |
| `require_reference` | `true` | run the orphan rule over SPEC documents |

### Statuses
- `enabled = false` ⇒ **noop** ("rule off"), never pass.
- no document under `paths` yields a predicate **and no SPEC is an orphan** ⇒ **noop** (exit
  code 3 from the embedded step, per ADR-0049) — the check inspected nothing and says so. A
  SPEC with no predicate section *and* no reference is still an orphan and still fails: no
  gate, test run or ticket can reach it, whatever it says.
- a file under `paths` that cannot be read or decoded ⇒ **fail**, naming the file (never
  skip a file and call the rest clean).
- any hedged predicate or orphan SPEC ⇒ **fail**. Each hedge is reported as
  `file:line — predicate — hedge`; orphans are listed by path with the three accepted
  reference kinds spelled out.
- otherwise **pass**, logging the counts (documents, predicates, SPECs checked for
  references).

### Report
`lint(documents, *, known_checks, known_tests, extra_hedges, require_reference) -> Report`
where `Report(predicates, findings, orphans)`; `Finding(predicate, hedge)`;
`Predicate(path, line, text, kind)`. `render(report)` produces the log text above.
Deterministic: output order is document order, then line order; orphans sorted by path.
The module is pure (no I/O); `23_predicates.sh` reads files and gathers the known sets.

## Guarantees
- **Threshold-free** — a hedge is present or it is not; a SPEC references something or
  it does not. No counts, no scores.
- **Deterministic & native** — stdlib regex over text; no markdown library, no network,
  no model.
- **Honest** — `noop` when nothing was inspected; `fail` when a file could not be read.
- **Dogfooded** — `23_predicates` is in this repo's `[checks].required` with
  `enabled = true`; every hedge it found in this repo's SPECs/ADRs was rewritten as a
  checkable statement, and every previously orphan SPEC now names its unit-test file.
- **Verified by** `tests/unit/test_predicates.py` (extraction, hedges, orphans,
  non-vacuity) and `tests/integration/test_predicates_gate.py` (off / noop / hedge /
  orphan / unreadable / pass through the real `verify.sh`).
