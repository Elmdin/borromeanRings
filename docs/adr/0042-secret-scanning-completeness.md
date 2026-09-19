# ADR-0042 — Secret-scanning completeness: history + non-git fail-closed

**Status:** Accepted

## Context
`12_secrets` (ADR-0032) scans the **current tracked files** and passes closed on
those. Two gaps let a secret through unseen:

1. **Deleted-but-committed secrets.** A credential committed and later removed is
   gone from `HEAD` but lives forever in the reachable git history — recoverable by
   anyone with a clone. `12_secrets` never looks there (matrix row **C — git-history
   secret scan**).
2. **Non-git projects.** `git ls-files` on a directory that isn't a git repo returns
   nothing, so `12_secrets` scanned an **empty** file set and passed **vacuously** —
   "can't scan" silently reading as "nothing to find". Found in the adoption rollout
   (spaceThink has no git).

## Decision
Two fail-closed hardenings, one security story:

- **`74_secret_history`** (heavy lane, CI-tier) scans every blob **reachable from any
  ref** (`git rev-list --all`) via the existing native scanner. Deliberately *not*
  `--batch-all-objects`: unreachable/dangling blobs never get pushed and only surface
  local test artifacts as false positives (verified — borromeanRings's own dangling
  adversarial fixture). History is immutable, so a finding demands **rotation**;
  `[secrets].history_allow` acknowledges rotated/benign findings by a one-way
  **fingerprint** (the secret itself is never emitted to logs/receipts).
- **`12_secrets` now fails closed on a non-git directory** instead of passing
  vacuously — the remedy is `git init` (or dropping the check for that project).

## Alternatives considered
- **A tool (gitleaks/trufflehog for history)** — rejected as the mechanism: the
  native high-confidence scanner already exists and is unit-tested; history
  enumeration is a few lines of git plumbing. Entropy-based tools remain a possible
  heavy-lane add where the false-positive budget is acceptable.
- **Scan all objects, not just reachable** — rejected: dangling blobs aren't in the
  shared history and produce false positives (borromeanRings's own case). Reachable-only is
  both correct (models what's pushed) and quiet.
- **In-line `allow-secret` marker for history** — impossible: you can't edit the past.
  A fingerprint allowlist is the only acknowledgment that works for immutable history.
- **Make `12_secrets` skip (pass) on non-git** — rejected: that *is* the vacuity. A
  secret gate that can't establish its input must fail, not wave through.

## Consequences
- (+) A secret is caught whether it's in the working tree *or* anywhere in reachable
  history; a non-git project can no longer pass secret-scanning by having nothing to scan.
- (+) Native, unit-tested (`meta_harness.secret_history`), adversarially verified
  (committed→deleted secret caught, then cleared by allowlist), fingerprints never leak.
- (−) History scan is O(reachable blobs) — hence the heavy/CI lane, with a 512 KB
  per-blob cap (secrets are small).
- (−) Turning on `12_secrets`'s non-git rule makes any non-git governed project (e.g.
  spaceThink) fail that check until `git init` — a real gap surfaced, by design.
