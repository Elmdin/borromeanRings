# ADR-0019 — Git identity: local-guard-only for the public borromeanRings repo

**Status:** Accepted
**Amends:** [ADR-0017](0017-git-identity-enforcement.md) (for borromeanRings's *own* repo policy only)

## Context
ADR-0017 gave the git-identity policy **two layers**: a local `PreToolUse` guard and a
fail-closed gate check (`06_git_identity`) that requires every commit unique to the
branch to be *authored* by the single declared `[git]` identity.

That fit borromeanRings while it was a single-maintainer repo. Now that the repo is
**public and accepting external contributions**, the gate layer is actively harmful for
this repo: an external contributor's PR is authored under *their own* GitHub identity,
so `06_git_identity` fails closed in CI and the PR cannot satisfy the required gate —
the identity safeguard becomes a wall against the contributors a public repo invites.
(Surfaced when `CONTRIBUTING.md` wrongly instructed contributors to adopt the
maintainer's identity.)

The feature itself is not wrong — for a single-developer governed project, the gate
layer is still valuable. The mismatch is specific to a **multi-contributor public repo**.

## Decision
For **borromeanRings's own repository**, enforce git identity via the **local guard only**:

- **Remove `06_git_identity` from `[checks].required`** in `borromeanrings.toml`. The
  shared check script (`checks/shared/06_git_identity.sh`) stays in the repo — it remains
  an opt-in capability any *other* governed project can require — it is simply not part
  of this repo's required set, so the gate ignores it (the verdict only inspects required
  checks).
- **Keep the `PreToolUse` guard and the `[git]` declaration.** The guard only fires for
  someone who has borromeanRings installed globally (in practice, the maintainer), helping
  them avoid committing under the wrong account. External contributors — who clone the
  public repo without borromeanRings's global hooks — are unaffected, and their PRs pass CI.

This is a **per-repo policy choice**, not a change to the feature. ADR-0017's two-layer
design remains the offering; this repo opts into one layer.

## Consequences
- External contributions are no longer blocked by commit authorship. (+correctness for the
  public-repo goal.)
- This repo loses the CI-side authorship backstop; commit provenance is still visible in
  history and on the PR, and the maintainer's local guard remains. Acceptable for an
  open repo where contributors are expected to use their own identities.
- If borromeanRings later adds a *multi-identity allowlist* (considered and deferred), this
  repo could opt back into a gate layer that admits known contributors. Tracked with the
  collaboration-governance work.

## Alternatives considered
- **Identity allowlist** (gate accepts a set of identities): preserves a CI backstop and
  supports contributors, but adds a list to maintain and a code change to the check.
  Deferred — revisit with collaboration-governance.
- **Keep single-identity, rebase contributions onto the maintainer:** rejected — rewrites
  contributor authorship, erasing provenance and credit.
