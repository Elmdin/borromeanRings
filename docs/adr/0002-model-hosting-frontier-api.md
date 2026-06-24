# ADR-0002 — Model hosting = frontier API

**Status:** Accepted

## Context
borromeanRings orchestrates an AI coding agent; the model must run somewhere. The dev machine is a WSL2
laptop with no GPU (ADR-0003), so local inference of a frontier-class model is not viable.

## Decision
Use a **frontier model via remote API**. borromeanRings is pure local orchestration + deterministic
checks; inference is remote. Data-locality posture (code leaves the machine on every model call)
is **documented, not mitigated** in v0.

## Alternatives considered
- **Local open-weights model** — rejected: no GPU; quality/throughput insufficient for the
  governed-agent use case (ADR-0003).
- **Mitigate data locality now** (redaction, on-prem proxy) — rejected for v0: out of scope; would
  expand v0 well past the single-gate mission. Recorded as a known limitation.

## Consequences
- (+) Best available model quality with zero local hardware investment.
- (+) Keeps v0 focused on the gate, not on inference infrastructure.
- (−) Source code is transmitted to a third party per call; acceptable for the harness's own repo,
  but must be surfaced to any future governed project. Tracked as a deferred concern.
