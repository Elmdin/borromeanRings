# SPEC — Prior-art gate (`17_prior_art`)

**Status:** Implemented · **Realized by:** `src/meta_harness/prior_art.py`,
`checks/python/17_prior_art.sh` · ADR-0051 · Closes #131

## Problem

Nothing enforces looking for existing solutions before building. The maintainer restates
the rule to every agent by hand. Coverage of *reuse* in the check suite: none.

## Contract

`17_prior_art` fails closed when feature work adds public surface without a survey:

1. **Trigger** — branch name starts with a `[prior_art].require_prefixes` entry (default
   `["feat/"]`). Other branches pass.
2. **Diff** — changed paths via `git diff --relative --name-only <merge-base>...HEAD`
   against `origin/dev` → `dev` → `origin/main` → `main`. No merge-base ⇒ `noop`.
3. **New surface** — for each changed `.py` under `src_dir`, public top-level symbols
   (via `api_diff.public_api`) at HEAD minus those at the merge-base; a file absent at
   the merge-base contributes all of its public symbols. Unparseable source contributes
   nothing (syntax is `20_lint`'s job).
4. **Rule** — `survey_violation(branch, new_symbols, changed)`: new symbols and **no**
   changed path under `[prior_art].dir` (default `docs/surveys/`, boundary-safe) ⇒
   **fail**, naming every new symbol and its file. No new symbols ⇒ **`noop`**.

| Situation | Status |
|---|---|
| Feature branch, new public symbol, no survey touched | `fail` |
| Feature branch, new public symbol, survey added/modified | `pass` |
| Feature branch, no new public symbols | `noop` |
| Non-feature branch | `pass` (rule off) |
| No merge-base | `noop` |

## Two consequences of committed-only diffing

Like `13_adr`, the gate diffs **committed** changes against the merge-base:

- **The survey must be committed with the change.** During development the Stop-hook
  gate will fail until it is — the check's first act on its own branch was to refuse
  it until `docs/surveys/0001-prior-art-gate.md` was committed. That is the intended
  shape: the survey is part of the recorded change, not a note beside it.
- **A stacked branch inherits its base's surface.** A branch cut from another unmerged
  branch is held to account for every public symbol added since the merge-base with
  `dev`, including the base's. A survey on the stacked branch satisfies the rule for
  all of it. Consistent with how `13_adr` treats an ADR.

## What is deliberately not here

- **Ecosystem lookup** — advisory only; no deterministic key-free search exists.
- **Copy-paste clones** — deferred to the heavy lane (jscpd), to be described honestly.
- **Judging the survey's content** — the gate checks presence, not quality.

## Config `[prior_art]`

| Key | Default | Purpose |
|---|---|---|
| `dir` | `docs/surveys` | where survey records live |
| `require_prefixes` | `["feat/"]` | branches held to the rule |

## Verification

- Unit: every branch of `new_public_symbols` and `survey_violation`.
- Integration: fixture repo — new symbol without survey ⇒ red; with survey ⇒ green;
  refactor with no new surface ⇒ `noop` and `inspected NOTHING` in the gate output.
- Each test verified to fail when its behaviour regresses.
