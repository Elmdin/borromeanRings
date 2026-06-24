# ADR-0003 — No local model (WSL2 laptop, no GPU)

**Status:** Accepted

## Context
The development and execution environment is a **WSL2 laptop with no GPU**. This is a hard
constraint on what borromeanRings can assume about compute.

## Decision
Assume **no local model and no GPU**. borromeanRings is designed as local orchestration + deterministic
shell/Python checks only; all model inference is remote (ADR-0002).

## Alternatives considered
- **Require a GPU workstation / cloud GPU** — rejected for v0: adds cost and setup unrelated to
  proving the gate; the gate logic needs no GPU.
- **Small quantized local model as a fallback** — rejected: insufficient for the governed-agent
  role; would add a dependency the gate doesn't need.

## Consequences
- (+) borromeanRings runs anywhere a shell + Python + network exist; no hardware lock-in.
- (+) The gate is fully deterministic and GPU-free — exactly the part we want reproducible.
- (−) Hard dependency on network/API availability for the *agent* (not for the gate itself; the
  gate runs offline once code exists).
