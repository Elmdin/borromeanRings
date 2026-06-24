# SPEC — Gated, explicitly-requested merge (`borromeanRings merge`)

> Status: spec for the "command now" half of the auto-merge feature (the user chose
> "command now, CI/GitHub-native next"). Plan → approve → implement; delivered via PR.

## 1. Purpose
Let a human merge the current branch into the base **with one command**, instead of clicking
merge in GitHub — but only when borromeanRings's gate is green. It mechanizes the human's merge
decision; it does not make one.

## 2. The safety invariant (non-negotiable)
A merge is permitted **iff both** hold:
1. **Explicitly requested** — a human ran the command. borromeanRings never originates a merge on its own.
2. **Gate passed** — `./verify.sh` exited 0 on the branch being merged (fail-closed).

There is **no standing/blanket auto-merge mode** — that would cross from self-*extension* into
self-*rewriting* (PLAN-v0 §12.5). Every merge is individually invoked by the human. This invariant
is encoded and unit-tested in `meta_harness.merge_policy` (the policy), separate from the git
plumbing in `merge.sh` (the mechanism) — information hiding: policy is testable, mechanism is thin.

## 3. Contract
`./merge.sh [base]` (default base = `main`), run while on the feature branch.

| Precondition | Behavior if violated |
|---|---|
| Not already on `base` | exit 1, "nothing to merge" |
| Working tree clean (no uncommitted changes) | exit 1, "commit or stash first" |
| Gate `./verify.sh` exits 0 | exit 1, "REFUSED — gate did not pass; nothing merged" |
| Policy `decide_merge(...)` allows | exit 1, "REFUSED by policy: <reason>" |

On success: merge the branch into `base` (prefer `gh pr merge` to keep the PR trail; else local
`git merge --no-ff` + push), write an audit receipt under `.meta-harness/merges/<ts>.json`
(`action, branch, base, gate, timestamp, merged_sha`), exit 0.

## 4. Edge cases
- Merge conflict → abort the merge, exit 1, report (never leave a half-merged tree).
- No `gh` / no PR for the branch → local merge + push fallback.
- Gate fails → no git mutation happens at all (gate runs before any merge step).

## 5. Test plan (derived from §2)
`tests/test_merge_policy.py` — truth table for `decide_merge`:
| explicitly_requested | gate_passed | expected |
|---|---|---|
| False | True | deny (not requested) |
| True | False | deny (gate failed) |
| False | False | deny |
| True | True | **allow** |
Covers both branches of the policy → keeps coverage at the ratchet baseline.

## 6. Deferred to the next step (CI / GitHub-native)
A GitHub Action running `verify.sh` on every PR, branch protection requiring it, and
`gh pr merge --auto` so GitHub merges when the required check passes. That makes the gate run
server-side too and is the more robust path; this command is the local-first version.
