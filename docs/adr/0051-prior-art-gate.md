# ADR-0051 — Prior-art gate: look before building, on the record

**Status:** Accepted · **Spec:** `docs/specs/SPEC-prior-art.md` · **Closes:** #131

## Context

The maintainer's own workflow rules mandate a research-and-reuse step before any new
implementation. Nothing enforced it. Every agent, every session, had to be reminded — and
still wrote its own hash function instead of using the one the repo already had
(`docs/research/VIDEO-REVIEW.md`, Cherno). **Nothing in the 24 existing checks covered
reuse at all.** This is the practice the maintainer most often finds themselves
re-stating by hand, which is the precise signal that it should be a gate.

Research before building it (`docs/research/AGENT-TOOLING-SURVEY.md`) established three
facts that shape the design:

1. **"Is there already a library for this?" cannot be a gate.** No key-free package API
   supports free-text search — deps.dev, ecosyste.ms, PyPI and libraries.io were each
   probed. Python is the worst-served ecosystem for the question. A gate that cannot
   answer its own question deterministically is the hollow green `01_source_coherence`
   exists to prevent.
2. **Clone detectors catch copy-paste, not reinvention.** Fixture-tested: two identical
   functions → jscpd finds 1; rename the variables → 0. PMD CPD's `--ignore-identifiers`
   is a silent no-op for Python.
3. **Reimplementation-of-a-builtin *is* deterministic**, and Ruff ships the only rules of
   that kind anywhere: `PIE807`, `PERF401/402/403`, `PLR0402`.

## Decision

**Gate the *question*, not the *answer*.** `17_prior_art` clones the `13_adr` pattern
(ADR-0043): on a feature branch, a change that **adds public surface** — a new top-level
function or class not prefixed `_`, computed by diffing `api_diff.public_api` at the
merge-base against HEAD — must also add or modify a survey record under
`[prior_art].dir` (`docs/surveys/`). The record says what existed in the repo, in a
dependency, and in the ecosystem, and why building was still right. The gate checks
that it was written; it does not grade it. No new public surface ⇒ `noop`.

**Reuse Ruff for reimplementation**, selected as five individual rules. Measured on this
tree, enabling the `PIE`/`PERF`/`PL` *groups* brought 50 findings, 37 of them magic-value
nits and 3 `too-many-arguments` — a numeric threshold, the very thing this project
refuses. The five chosen rules are binary. The one finding they raised was fixed, not
suppressed.

**Keep the ecosystem half advisory**, by name, in the survey template and the check's
own header — so no one later "completes" the gate by bolting on a lookup that cannot be
trusted.

**Defer copy-paste detection** (jscpd, heavy lane). It is honest work but must be
described as *copy-paste* detection, and Node is not runnable in the maintainer's
environment today. Tracked on #131.

## Consequences

- A survey is now a first-class artifact with a template and a numbered directory, and
  the gate ships with its own (`docs/surveys/0001-prior-art-gate.md`) — dogfooded.
- A rename of a public symbol reads as new surface. That is accepted: a new public name
  deserves the same question.
- Non-feature branches, doc/test-only changes, and changes that touch a survey all pass;
  a branch with no merge-base is `noop`.
- Adoption is opt-in per project (`[checks].required`) and offered by `adopt.sh`.
