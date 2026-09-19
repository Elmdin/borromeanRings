# ADR-0070 — Provenance gate: binary shingle overlap against a declared source, classified by a human allowlist

**Status:** Accepted
**Spec:** `docs/specs/SPEC-provenance.md`
**Relates to:** ADR-0020 (re-author, never copy), ADR-0049 (honest `noop`), epic #172, issue #189

## Context

ADR-0020 decided that material from the maintainer's CC BY-NC-SA sibling project is
**re-authored** into this Apache-2.0 repository — ideas port, expression does not. During
the 4D merge (epic #172) that rule was enforced by review only. Of five ports, two came
back with copied or clause-for-clause passages and a third with near-paraphrases, each
after the builder had declared the port clean. What caught them was a reviewer's
scratchpad script: 5- and 6-word shingle overlap between the PR's added lines and the
sibling's full text, followed by a *human* reading of every hit to separate generic
overlap (a license identifier, `from pathlib import Path`) from authorial phrasing.

Two facts about that sweep decide the design:

1. **An overlap count is a number, and this repo forbids number gates.** "More than N
   overlaps fails" would be exactly the arbitrary threshold the maintainer rejects; any
   N is gameable and means nothing on its own.
2. **The generic/distinctive split was made by a person.** No heuristic a gate could
   apply — word frequency, stop-word ratio, phrase length — is anything but a hidden
   threshold with a different name. The sweep's value came from the reader, and the
   sweep's weakness was that the reader had to remember to run it.

## Decision

**1. The gate is binary and about facts.** A six-word run of normalized text that occurs
both in a changed file and in a declared source is an *overlap*. An overlap not covered by
`[provenance].allow` is a *finding*. **Any finding fails.** There is no count, ratio, or
score anywhere in the verdict. The shingle size (6) is the unit of evidence — the same
one the review used — not a pass mark; it is a constant, not a knob.

**2. The human classifies; the gate remembers.** The allowlist *is* the reviewer's
generic/distinctive judgement, made once and made durable: every unlisted overlap fails,
and the person either re-authors the passage or adds the phrase to `allow` with a comment
saying why. That comment lands in the config diff, where the next reviewer sees it. The
gate never decides that something "looks generic" — it cannot, and pretending otherwise
would be the threshold in disguise. Matching is contiguous: a short entry covers every
shingle containing it, a long acknowledged passage covers every shingle inside it, and a
scattered subset never matches. An entry that normalizes to nothing fails closed, because
it would match everything.

**3. Sources are declared, read-only, and machine-local by environment.** The sibling
project sits at an absolute path on one machine. Committing that path would leak it and
break every other clone, so the committed config declares `sources = []` and the check
appends `BORROMEANRINGS_PROVENANCE_SOURCES` (colon-separated) after the config. On a
machine without the sibling the check is honestly `noop` ("no provenance sources
declared"), never a hollow pass (ADR-0049). Sources are never fetched, copied, or
modified; the receipt carries no more of a source than the overlapping six words.

**4. Fail closed on everything that is not "nothing to compare".** An absent, unreadable,
or text-less source; a git error inside a repository; an empty allow entry — all fail.
Only these are `noop`: no `[provenance]` table (rule off), no effective sources, no base
branch, no changed file under `paths`. Self-quotes — overlap among this repo's own files,
or a source that resolves inside the project — are never findings.

**5. Fast lane, opt-in.** Issue #189 proposed the heavy lane. With `sources = []` the
check costs one config read, and with sources it costs one shingle index of the sibling,
which is seconds — so it runs on every gate where declared, and a port cannot reach a PR
without it. `adopt.sh`'s RECOMMENDED set is unchanged: most projects have no declared
source to protect.

## Alternatives considered

- **A threshold on the overlap count or ratio** — rejected: an arbitrary number, and the
  sweep showed the count carries no signal (106 overlaps, all generic, on the cleanest
  PR; two overlaps, one a blocker, on another).
- **A built-in stop-word / boilerplate heuristic** to auto-classify generic overlaps —
  rejected: a threshold by another name, and wrong in both directions (a sentence built
  from common words sails through it, while `Path.mkdir(parents=True)` is flagged).
- **Five- and six-word shingles both** (the sweep's setting) — rejected for the gate:
  every 5-word overlap inside a 6-word overlap is already reported, and a lone 5-word hit
  is the reviewer's paraphrase territory, not a mechanical finding. Six is the constant.
- **Committing the sibling's path** — rejected: machine-local, and a privacy leak on a
  public repository.
- **Fetching or vendoring the source text** — rejected: the source is CC-licensed and
  must never enter this repository, and the gate is offline by rule.
- **`emit_noop` when a source path is missing** — rejected: "cannot read the source" is
  not "there is nothing to compare"; the 12_secrets doctrine (ADR-0042) applies.

## Consequences

- (+) The re-author rule is enforced by the gate, on the record, with both locations
  for every finding; a port can no longer be reported clean without the comparison.
- (+) The generic/distinctive judgement is versioned and reviewed like code instead of
  re-made from memory at every review.
- (+) Nothing about the sibling — path or text — enters the repository.
- (−) The first run against a real source produces boilerplate findings that must be
  allowlisted by hand. That is the design: the human classifies, once, visibly.
- (−) Paraphrase below six shared words is not detected. That remains the reviewer's
  reading, as HANDOFF §9 rule 1 already states; the gate removes the mechanical half.
- (−) A generous `allow` entry weakens the gate. Entries are reviewed in the diff; a
  short common phrase (`is a`) would be a visible mistake, not a silent one.
