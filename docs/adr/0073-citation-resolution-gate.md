# ADR-0073 — Citations must resolve on the branch that carries them

**Status:** Accepted
**Spec:** `docs/specs/SPEC-citations.md`
**Realized by:** `src/meta_harness/citations.py`, `checks/shared/26_citations.sh`

## Context

Across one review cycle, the single largest defect class was **doc overclaim** — prose
asserting something the branch does not contain. Thirteen findings across eleven PRs, more
than any other class, including every category of code defect.

Read closely, most of those findings are not judgements about whether a document
*describes* the code correctly. They are **path-resolution facts**:

- a doc citing `docs/HANDOFF.md` (lands with #147) for a rule, on a base where that file
  exists only on an unmerged branch — three templates in one PR, twice in another;
- `ADR-0057` (lands with #166) and `ADR-0061` (lands with #170) cited bare in a table, on
  a base whose `docs/adr/` stops at 0047, while the *same document* labels both correctly
  a hundred lines earlier;
- `docs/CHECKS.md` named as one of "the two documents [that] disagree **on this base**"
  when it is not on that base at all;
- a section reference into a survey document absent from the branch citing it.

Nobody needs a model to settle any of those. The repository already had the shape twice
over: `13_adr` (ADR-0043) gates *that a decision was recorded*, and `01_source_coherence`
(ADR-0049) gates *that the gate is looking at real code*. What was missing was the same
move applied to prose.

## Decision

**A new fast-lane check, `26_citations`.** On a branch that changed Markdown under
`[citations].paths`, every citation those documents make must resolve against this branch.
A citation is a repo-relative path (optionally with a `#anchor` or `:line`), a heading
anchor, an `ADR-NNNN` reference, or a check id. Resolution is against **git-tracked**
paths, not the working tree: an untracked scratch file is not "on this branch". Off unless
`[citations].enabled`; `noop` when the branch changed no documentation.

**The decision logic is a pure module with an injected resolver.**
`src/meta_harness/citations.py` performs no I/O at all, and `unresolved()` takes
`resolve` as a parameter. Every recognition rule is therefore testable with a dictionary,
and the filesystem lives in one place — the check.

### Why offline-only, permanently

The two exclusions are not gaps to be closed later; they are the boundary of what this
gate can honestly claim.

**External URLs are never checked.** Resolving one requires a network call. This check
runs on every Stop-hook gate, and a gate whose verdict depends on the network is a gate
that is red when the wifi is, green when a site is briefly up, and different in CI from
what the author saw. Worse, it would leak the repository's reading list to third parties
on every keystroke-driven run. Determinism and privacy both point the same way, so link
liveness stays a human-review concern — as does the more interesting question of whether
the *cited page still says what was claimed*, which no status code answers.

**Issue and PR numbers are never checked.** `#188` resolves only against GitHub's state,
which is off-machine *and* mutable after the fact: issues get renumbered in transfers,
closed, retitled. One review caught exactly this defect — an ADR citing issue `#53` for a
fix that shipped in PR `#82` — and it is deliberately still out of scope. A gate that
implies more than it verifies is the very failure being fixed, so the SPEC and the check's
header both say plainly that this instance is not covered.

### Why the forward-reference hatch is narrow

Work here lands as a stack of branches, so a document legitimately needs to name something
that arrives with a later PR. The convention already existed in prose ("lands with #166").
Making it machine-recognised is what keeps the check from punishing honest sequencing.

But an escape hatch in a fail-closed gate is the gate's weakest point, so it is drawn as
tight as it can be while still being writable:

- it must sit **immediately after** the citation — a closing backtick, spaces, at most one
  `,` or `;` — not merely somewhere in the sentence;
- it is a **parenthesised** `(lands with X)` / `(on X)`, nothing else;
- `X` must be `#<digits>` or a branch-shaped name containing `/`.

That last clause is what stops ordinary prose from suppressing a finding by accident:
`(on line 5)`, `(on request)` and `(on the heavy lane)` are all rejected. A hatch that
prose could open by coincidence is not a hatch, it is a hole. The narrowness costs an
author one re-word; the alternative costs the check its meaning.

### What stays a human-review concern

Stated so nobody reads this check as more than it is:

- **whether prose describes the code correctly.** "The check derives ADR citations per
  check" is false even when every path in the sentence resolves. That is the dormant
  `55_doc_drift` critic's territory (ADR-0030) and the reviewer's.
- **whether a citation is the *right* one.** A resolvable pointer to the wrong document
  passes.
- **external link liveness and issue/PR correctness**, per the section above.
- **contradictions between two documents** (the ✅/❌ disagreement one review found):
  both halves resolve; only the claims conflict.

## Alternatives considered

**Scan the whole tracked tree, not just changed files.** Rejected for the gate: it makes
every branch responsible for prose it never touched, which is how a check gets suppressed
rather than obeyed. The changed-file scope matches `13_adr` and `11_changelog`. The
whole-tree sweep was still run once by hand while building this, and the 24 dead citations
it found were fixed on this branch rather than deferred — so the tree starts clean and the
per-branch rule keeps it that way.

**Treat every backticked span as illustrative.** Rejected: backticks are precisely how
this repository writes its real citations, so that rule would exclude nearly all of them.
What separates illustration from claim is *shape* — a glob, a placeholder, a non-repo
root, a bare directory — not formatting. The one formatting rule kept is that a Markdown
link written inside backticks is not a link (it renders as literal text, so it cannot be a
dead one).

**A `<!-- citations: ignore -->` suppression comment.** Rejected outright. A suppression
marker that takes no argument is a permanent silencer; the forward label at least names
where the thing actually is, which makes it self-expiring and reviewable.

**A model judge.** Rejected as the wrong tool for a decidable question, at per-run cost,
with a non-deterministic verdict. The judgement half of doc overclaim already has a home.

## Consequences

- The four dead-reference defects named in issue #188 would each have been red on the fast
  lane, at `file:line`, before review ever saw them.
- **Migration:** opt-in per project like every check, and deliberately **not** added to
  `adopt.py`'s `RECOMMENDED` set. A project adopting it mid-life will go red on its
  accumulated dead references, and that redness should be a choice its maintainer makes,
  not a surprise from running `adopt.sh`.
- Applying it here surfaced 24 unresolved citations in the existing tree — moved test
  paths (`tests/` was regrouped into `unit/` and `integration/` and the docs never
  followed), two genuinely broken relative links in one spec, a planned check id
  whose number had already been taken by `11_changelog`, and several historical or illustrative
  paths written in citation shape, plus a per-check template in `PLAN-v0.md` written
  without that document's own `<placeholder>` convention. Each was fixed in the
  document; none was suppressed.
- One recognition rule earned its place from a false positive found during that sweep: a
  file extension must start with a letter, or the prose `checks/00..50` reads as a file.
- Two rules came from adversarial review of the PR, both in the same direction — a false
  positive on a *good* citation is the worst failure this check can have. Anchor slugs
  now reproduce GitHub's duplicate-heading disambiguation, so the real anchor for a second
  "Setup" section (`#setup-1`) resolves instead of reading as dead. And indented code
  blocks are skipped alongside fenced ones, list-aware: four spaces inside a list is
  continuation text, and thirteen live citations in this repository's own changelog sit
  at exactly that indent, so a blanket rule would have silently dropped every one. The
  list tracking is a stated simplification of CommonMark whose only failure mode is
  under-scanning, recorded in the SPEC rather than left for a reader to discover.
- The gate now says something new about a document: not that it is right, but that
  everything it points at is here.
