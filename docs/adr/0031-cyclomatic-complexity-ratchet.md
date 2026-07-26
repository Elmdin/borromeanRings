# ADR-0031 — Cyclomatic-complexity ratchet (native, non-regression)

**Status:** Accepted

## Context
Function complexity was unbounded (matrix row **B**). Complexity is where bugs
hide and tests thin out; without a signal it only grows. The project already
prefers **ratchets** over absolute targets and keeps the gate's external-tool
footprint small (ADR-0027, ADR-0029).

## Decision
Add `32_complexity` + `meta_harness.complexity`: measure McCabe complexity per
function (excluding nested defs) natively via stdlib `ast`, and **ratchet the
worst-case** across the package against `.borromeanrings-complexity-baseline`
(non-regression, no absolute ceiling). borromeanRings records a baseline of `10`.

## Alternatives considered
- **`radon` / `xenon` (existing tools)** — rejected as the mechanism: a required
  external tool enlarges every governed project's footprint and can't be
  built/gated without installing it (same reasoning as import-linter/interrogate).
  McCabe over `ast` is ~40 covered lines and gives us exactly the metric.
- **Absolute ceiling ("no function > 10")** — rejected: an arbitrary number gets
  gamed, and a legitimately-branchy function shouldn't need a config exception. A
  ratchet enforces "never worse than today"; the baseline is raised deliberately
  when justified.
- **Sum/average complexity** — rejected: totals grow with the codebase (noisy),
  and an average hides the one monster function. The **max** is the sharpest
  single signal and points at exactly what to simplify.
- **Count nested-function decisions in the parent** — rejected: it double-counts
  and misattributes; each nested function is measured as its own unit (matching
  radon's model).

## Consequences
- (+) The worst function can't get worse without failing the gate; the receipt
  names the offender.
- (+) Zero new dependency; `complexity.py` pure and 100% covered; reusable for any
  governed Python project (opt-in via required list + baseline).
- (−) A single-max ratchet says nothing about the *distribution* — a second
  function creeping to the same max passes. Acceptable: the max is the guardrail;
  a distribution ratchet can layer on later.
- (−) Complexity ≠ readability; a low score isn't proof of clarity. It's a floor
  against the worst structural offenders, not a style judge.
