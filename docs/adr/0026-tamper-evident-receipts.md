# ADR-0026 — Tamper-evident receipts (content digest + fail-closed verdict)

**Status:** Accepted

## Context
Every check writes a receipt (`check`, `command`, `exit_code`, `status`, `log`,
extras); the fail-closed verdict trusts each required receipt's `status`. Until
now a receipt was plain JSON — a `status: "fail"` could be edited to `"pass"`,
or a log scrubbed of a finding, and the verdict would believe it. Receipts are
described as the project's "append-only evidence"; evidence that can be silently
rewritten is not evidence. This is matrix row **K — is the enforcement itself
real?** (the receipts sub-row).

## Decision
Give each receipt a **content digest** (`content_sha256`) over all its
meaningful fields **plus its log content**, computed at emit time
(`meta_harness.receipts.finalize_receipt`, wired into `emit_receipt`). The
verdict re-derives the digest for every *required* receipt and **fails closed**
on any mismatch, missing hash, or missing log (`!TAMPERED` in the summary). It
also prints a single **run-digest** over the intact receipts — an anchor CI can
capture in its external, append-only log.

This is **tamper-evidence, not tamper-proof.** The algorithm is public, so a
knowledgeable local editor can re-forge receipt + log + digest consistently.
Stated honestly, it buys:
- detection of accidental corruption / partial writes;
- detection of *naive* editing (a script or agent that flips a field without
  recomputing the digest — the realistic local-agent failure mode);
- an anchor digest to check local receipts against a trusted external record.

The real trust backstop remains **CI**, which regenerates receipts from scratch
in a clean environment.

Fail-closed (not advisory) was chosen because a fresh run *always* produces
matching digests — empirically verified: the full 10/10 gate passes with
integrity on, so there are no false positives to fear, and editing any field or
the log of a real receipt is detected.

## Alternatives considered
- **HMAC / signed receipts (a secret key)** — rejected for now: real
  tamper-*proofing* against a local editor needs key management borromeanRings
  deliberately avoids (model/harness-agnostic, no secret store). The honest
  content-digest + CI-anchor path covers the realistic threat without pretending
  to cryptographic guarantees. Signing is a future option if a key store exists.
- **Advisory-only (print a warning, don't fail)** — rejected: fresh runs never
  mismatch, so fail-closed carries no false-positive cost, and advisory
  integrity is theatre. (The advisory-first pattern is right for *non-deterministic*
  checks like the critic; a digest is deterministic.)
- **Hash the fields but not the log** — rejected: a scrubbed log (a check that
  hid its own finding) would go undetected; the log is part of the evidence.
- **Store hashes in a separate manifest only** — rejected as the primary
  mechanism: an in-receipt digest keeps each receipt self-verifying; the
  run-digest already gives the manifest-style anchor without a second file to
  keep in sync.

## Consequences
- (+) A required receipt can no longer be silently edited to flip the verdict;
  corruption and naive tampering fail the gate.
- (+) The run-digest gives audits a single value to anchor externally (CI log,
  or a future committed record).
- (+) Digest logic is one small, 100%-covered module; the receipt format's
  secret stays hidden behind `_lib.sh` (unchanged contract for checks).
- (−) Not proof against a determined, knowledgeable local forger — documented,
  not hidden. Promotion path: signed receipts once a key store exists; a
  verdict-only replay mode to re-verify a prior run's receipt dir.
- (−) `emit_receipt` now reads the log it just wrote (one extra read per check) —
  negligible.
