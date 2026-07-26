# SPEC — Tamper-evident receipts

**Status:** Implemented · **Realized by:** `src/meta_harness/receipts.py`,
`checks/_lib.sh` (`emit_receipt`), `verify.sh` (verdict) · ADR-0026

## Contract

Each receipt carries `content_sha256` — a digest over its meaningful fields
(everything except the hash field) **plus its log content**:

```
content_sha256 = sha256( canonical_json(receipt \ content_sha256)
                         + "\n" + sha256(log_text) )
```

- **Emit** (`finalize_receipt`, in `emit_receipt`): compute and attach the digest
  when the receipt is written; the log has been fully written by then (every
  check calls `emit_receipt` last).
- **Verify** (`verify_receipt`, in the verdict): for each *required* receipt,
  recompute the digest from its fields + log and compare. A mismatch, a missing
  hash, or a missing log ⇒ **fail closed** (`!TAMPERED`), never trusted.
- **Anchor** (`run_digest`): the verdict prints one digest over all intact
  receipts — a value CI captures in its external log for later audit.

## Properties

| Property | Guarantee |
|---|---|
| Fresh run | all required receipts verify (no false positives) — empirically: 10/10 gate green with integrity on |
| Field edit (e.g. `status: fail→pass`) | detected |
| Log edit (e.g. a finding scrubbed) | detected |
| Missing / unhashed / corrupt receipt | flagged, fail closed |
| Determined local forger with the algorithm | **not** prevented — evidence, not proof (see below) |

## Threat model (honest)

The digest algorithm is public; a knowledgeable local editor can re-forge
receipt + log + digest together. This mechanism detects **accidental corruption**
and **naive editing** (the realistic local-agent failure mode) and provides an
**external anchor** via the run-digest. The trust backstop is **CI**, which
regenerates receipts in a clean environment. Cryptographic tamper-*proofing*
(signed receipts) is deferred until a key store exists — see ADR-0026.
