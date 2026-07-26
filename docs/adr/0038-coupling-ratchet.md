# ADR-0038 — Coupling ratchet (worst-case fan-out, native)

**Status:** Accepted

## Context
`35_architecture` enforces import *direction* (leaves, private, acyclicity) but
not import *volume*. A module that imports many siblings is highly coupled — hard
to change in isolation, a cohesion smell (matrix row **D — coupling/cohesion
metrics**). Nothing bounded it.

## Decision
Add `33_coupling` + `meta_harness.coupling`: measure efferent coupling (fan-out)
per module from the existing arch import graph and **ratchet the maximum**
(non-regression, no absolute ceiling). borromeanRings baseline `2`.

## Alternatives considered
- **An absolute fan-out ceiling** — rejected (same reasoning as complexity/docstring
  ADRs): arbitrary number, gamed; a ratchet enforces "never worse than today".
- **Instability metric `I = fan-out/(fan-in+fan-out)` + the stable-dependencies
  principle** — richer (Martin's metrics), but a single instability number per
  module is noisy on a small graph and harder to action than "which module got more
  coupled". Fan-in is exposed for reporting; the *ratchet* keys on max fan-out, the
  sharpest actionable signal. Instability can layer on later.
- **A tool (e.g. `pydeps`, `radon` `mi`)** — rejected: the import graph is already
  built natively for `35_architecture`; reusing it is a few covered lines and keeps
  the gate tool-free.

## Consequences
- (+) The most-coupled module can't get more coupled without failing the gate,
  naming the offender; complements the direction rules with a volume bound.
- (+) Zero new dependency; reuses `build_import_graph`; `coupling.py` 100% covered.
- (−) Max-fan-out says nothing about the *distribution* or about afferent coupling
  as a gate (only reported) — a deliberate single-signal guardrail, not a full
  coupling model.
