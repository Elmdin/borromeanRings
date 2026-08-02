# SPEC — Git-history secret scanning

**Status:** Implemented · **Realized by:** `src/meta_harness/secret_history.py`,
`checks/ci/74_secret_history.sh` · ADR-0042

## Problem

A secret committed and later deleted is absent from `HEAD` but remains in the
reachable git history, recoverable by anyone with a clone — still compromised.
`12_secrets` scans only current tracked files and cannot see it.

## Contract

`74_secret_history` (heavy lane) fails closed on any high-confidence secret in the
**reachable** history:

1. **Scope** — blobs reachable from any ref (`git rev-list --all`), deduplicated.
   Unreachable/dangling objects are excluded (never pushed; only local test noise).
   Blobs larger than 512 KB are skipped (secrets are small).
2. **Scan** — each blob's text is run through `meta_harness.secrets.scan_text`
   (the same native high-confidence detector as `12_secrets`).
3. **Report** — `scan_blobs(blobs, allow)` returns one `HistoryFinding` per **unique**
   secret (deduped by fingerprint), attributed to the first blob it was seen in. The
   secret text is **never** emitted — only `kind`, blob sha, and a one-way
   `fingerprint = sha256(kind:snippet)[:16]`.
4. **Acknowledge** — history is immutable, so the remedy is **rotation**. A rotated /
   known-benign finding is acknowledged by its fingerprint in
   `[secrets].history_allow`; allowlisted fingerprints are dropped.
5. **Not a git repo** ⇒ no history ⇒ pass.

Companion hardening (same ADR): **`12_secrets` fails closed on a non-git directory**
rather than passing vacuously on an empty tracked-file set.

## Guarantees

- **No vacuous pass** — a committed-then-deleted secret is caught; a non-git project
  can't pass secret-scanning by having nothing to scan.
- **Secrets never re-leak** — logs/receipts carry fingerprints, not secrets.
- **Correct scope** — reachable-only avoids dangling-fixture false positives.
- **Native / no installs** — stdlib + git plumbing; unit-tested and adversarially verified.
