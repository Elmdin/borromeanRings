# ADR-0007 — Gated, explicitly-requested merge (no autonomous self-merge)

**Status:** Accepted

## Context
The user asked for an "auto-merge" capability so they don't have to merge by hand in GitHub. This
sits directly on borromeanRings's locked principle (ADR/PLAN-v0 §12.5): self-**extension** is allowed,
self-**rewriting** is not — *a human approves every merge to borromeanRings itself.* A naive "auto-merge
everything" mode would violate that.

## Decision
borromeanRings gains a `./merge.sh` command bound by one invariant: **a merge happens only when (a) a
human explicitly invokes it AND (b) the gate (`verify.sh`) exits 0.** It mechanizes the human's
decision; it never originates a merge. There is **no standing/blanket auto-merge mode**. The rule is
encoded and unit-tested in `meta_harness.merge_policy`, separate from the git plumbing in `merge.sh`.

## Alternatives considered
- **Standing auto-merge (merge whenever the gate is green, unprompted)** — rejected: that is
  autonomous self-modification of the trust root, the exact thing §12.5 forbids.
- **No merge feature; always merge by hand in GitHub** — rejected: the user wants the convenience,
  and the explicit-request + gate invariant makes it safe.
- **Policy baked into the shell script as comments only** — rejected: the safety rule is the most
  important logic in the feature; it belongs in tested code, not a comment.

## Consequences
- (+) The human stays the approver of every merge (they invoke each one); the gate stays the
  precondition (fail-closed). Auditable via a per-merge receipt.
- (+) The merge becomes "just another consumer of the gate" — consistent with the architecture.
- (−) Not hands-off: each merge is a deliberate command, by design. The GitHub-native
  `gh pr merge --auto` + CI path (deferred) will make it hands-off *at the PR level* while still
  gated by a required status check — never an unconditional self-merge.
