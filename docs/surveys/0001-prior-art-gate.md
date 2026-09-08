# Survey — a gate that enforces looking before building

**Question.** Is there an existing tool that deterministically checks "did you look for
prior art before adding this?" — so borromeanRings can adopt it instead of writing one?

## What already exists

| Where | What was found | Fit |
|---|---|---|
| This repo | `13_adr` / `adr_discipline.adr_violation` — "feature branch touching src must add an artifact under a directory" | **Extend.** Same shape exactly; only the trigger (new public symbol) and artifact dir differ. `api_diff.public_api` already extracts public symbols. |
| This repo | `34_api_diff` — diffs public surface vs merge-base | **Reuse** its `public_api` for symbol extraction; its diff direction (removals) is the inverse of what is needed (additions). |
| Ecosystem — reimplementation | Ruff `PIE807`, `PERF401/402/403`, `PLR0402` (verified on the installed 0.15.8) | **Reuse.** The only shipping "you reimplemented this" rules anywhere. One config line. |
| Ecosystem — clones | jscpd 6.1K★ MIT; PMD CPD | **Defer.** Catches copy-paste only — renaming variables evades it (fixture-verified); CPD's `--ignore-identifiers` is a silent no-op for Python. Also needs Node, broken in this environment. Heavy-lane follow-up, described honestly as copy-paste detection. |
| Ecosystem — "is there a library?" | deps.dev, ecosyste.ms, PyPI, libraries.io | **Not gateable.** None offers key-free free-text search (all probed). Advisory lane only. |
| Ecosystem — survey-required gates | spec-kit 133K★, Superpowers 280K★ | **Not a fit.** Prompt-level persuasion; nothing fails closed. |

## Decision

**Build the survey-required gate; reuse everything else.** The deterministic half is a
thin clone of `13_adr` over `api_diff.public_api`; the reimplementation half is a Ruff
config line; the ecosystem half is explicitly advisory because it cannot be answered
deterministically. Nothing existing does the first part.

## Sources
- `docs/research/AGENT-TOOLING-SURVEY.md` §4 and §"corrections" (API probes, jscpd fixtures)
- `docs/research/VIDEO-REVIEW.md` (Cherno: agents rewrite existing API; ranked rec #1)
- `ruff rule PIE807` / `PERF401` / `PLR0402`; `ruff check --select PIE,PERF,PL` on this tree
