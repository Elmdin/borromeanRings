# ADR-0048 — Harness versioning + per-run version stamping

**Status:** Accepted

## Context
borromeanRings governs projects **by reference**: a project's Claude hooks (and its manual
`./verify.sh`) invoke borromeanRings's on-disk code at `BORROMEANRINGS_HOME`. There has been
**no version concept at all** — no `VERSION` file, zero git tags, zero GitHub releases. Two
consequences a maintainer eventually hits:

1. **"Is it stable enough to depend on?"** — consumers implicitly track *whatever commit the
   borromeanRings working tree happens to sit at* (today: the `dev` integration branch, ahead
   of `main`). There is no blessed, referenceable "stable release" to pin a project to.
2. **"Which version governed this project?"** — a gate run leaves receipts and a persisted
   `Verdict` (ADR-0046/0047), but none of it records *which borromeanRings produced the
   verdict*. A green receipt from an old, half-built harness looks identical to one from the
   current code.

This is orthogonal to *check adoption* (which checks a project requires): that already drifts
per project and is reported by `status`. This ADR is about the **harness itself** having an
identity.

## Decision
1. **Declare a version.** Add a top-level `VERSION` file (starts at `0.1.0` — the first
   tagged release of a still self-described "v0"; `1.0.0` is reserved for the API-stability
   commitment) as the human-declared release marker, and cut a matching annotated git tag /
   GitHub release on `main` per release. Releases follow SemVer; the tag is the stable ref a
   cautious project can pin to (by checking out borromeanRings at that tag).
2. **Stamp every run with the governing version.** `verify.sh` computes
   `HARNESS_VERSION` from `git -C "$BORROMEANRINGS_HOME" describe --tags --always --dirty`
   (reflecting the *exact* code state — clean tag, `-N-g<sha>-dirty` when ahead/modified, or a
   short SHA before the first tag), falling back to the `VERSION` file, then `unknown`. It is:
   - printed in the gate output (`harness-version: …`),
   - carried on the persisted `Verdict` (new `harness_version` field →
     `.meta-harness/last_verdict.json` and the `verdict_history.jsonl` history),
   - written as `harness_version.txt` into the run's receipt bundle (self-describing evidence).

`git describe` is chosen over reading `VERSION` alone because it reflects reality — a dirty or
ahead-of-tag working tree is stamped honestly, so evidence can never over-claim a clean release.

## Consequences
- A governed project's evidence now answers *"what verified me, and was it a clean release?"* —
  not just pass/fail. The `harness_version` field defaults to `""` for records written before
  this change, so old evidence still parses (back-compatible).
- "Latest version" gains meaning: with per-project opt-in governance (the chosen model), a
  cautious project can check out borromeanRings at a release tag rather than tracking `dev`.
- Surfacing `harness_version` as a column in `status.sh` is a small, deferred follow-up; the
  durable record lands here.
- No behavioural change to the verdict itself — stamping is best-effort and never affects
  pass/fail (same guard as ADR-0046/0047).
