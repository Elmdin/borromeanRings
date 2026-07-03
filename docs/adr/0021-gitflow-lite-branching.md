# ADR-0021 — Gitflow-lite branching: feature branches → `dev` (default) → `main`

**Status:** Accepted

## Context
Until now all work merged straight to `main` via feature-branch PRs. That conflates
"integrated" with "released": every merge lands on the stable branch immediately, there is
no buffer where several increments can integrate (and soak under CI) before promotion, and
external contributors — now that the repo is public — get no signal about where work should
target. The collaboration-governance effort (SPEC-collaboration.md) needs a declared
branching model as its foundation, because the Tier A checks (branch naming, protected-
branch guard) and Tier B reconciler (declared platform policy) enforce *against* it.

## Decision
**Gitflow-lite**, sized for this project (solo maintainer + occasional external
contributors, continuous integration, deliberate releases):

- `main` — stable/release. Changes arrive only by PR from `dev` (or `hotfix/*`).
  Promotion `dev → main` is an explicit Maintainer decision.
- `dev` — integration branch and the **repository default**: PRs and clones target it
  naturally; work integrates there under the same gate before promotion.
- `feature/* | fix/* | docs/* | chore/*` — short-lived branches off `dev`;
  `hotfix/*` may branch off and target `main` directly.
- Both `main` and `dev` are protected identically: required `gate` status check
  (strict), linear history, no force pushes, no deletions. Squash merges.
- Review policy: Maintainer may self-review own PRs at current team size; external
  contributions require Maintainer review. Growth flips a declared review-count
  setting, not the process.

Applied 2026-07 (increment 0): `dev` created from `main`, protection replicated,
default branch switched, CI push-trigger extended to `dev`.

## Alternatives considered
- **Trunk-based (status quo: everything → `main`)** — rejected: no integration buffer
  between "merged" and "stable"; public-repo contributors would keep landing work
  directly on the release branch. Fine for a private prototype; wrong for a public
  project promising a stable `main`.
- **Full Gitflow (release/*, hotfix/*, develop ceremonies)** — rejected: release-branch
  and version-freeze ceremony is overhead this team size cannot amortize; Gitflow-lite
  keeps the two-tier stability property without the ritual.
- **GitHub Flow + release tags** — close second; rejected because a persistent `dev`
  gives the gate a place to catch cross-increment integration failures *before* they
  reach the branch users clone and CI badges advertise.

## Consequences
- (+) `main` is always releasable; integration risk is absorbed on `dev` under the same
  fail-closed gate (identical protection means no weaker path into either branch).
- (+) The Tier A branch checks have a declared model to enforce; Tier B has declared
  platform policy to reconcile against.
- (−) One more hop for every change (`feature → dev → main`) and periodic promotion
  PRs — accepted as the price of a stable public `main`.
- (−) Default-branch switch changes where clones/PRs point; existing open PRs against
  `main` must be retargeted or promoted deliberately (none open at switch time).
