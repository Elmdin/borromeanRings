# SPEC — Cyclomatic-complexity ratchet

**Status:** Implemented · **Realized by:** `src/meta_harness/complexity.py`,
`checks/python/32_complexity.sh`, `.borromeanrings-complexity-baseline` · ADR-0031

## Problem

Nothing bounded function complexity (matrix row **B — cyclomatic-complexity
ceiling/ratchet**). Branch-heavy functions accrete silently and become untestable.

## Contract

`32_complexity` measures the **worst-case** function complexity across the package
and **ratchets** it against a baseline — it may not regress, but there is no
absolute ceiling to game (a non-regression signal, consistent with the project's
stance against number gates).

- **Complexity** = 1 + decision points: `if`/`elif`, `for`/`while`, `except`,
  `with`, `assert`, ternary (`IfExp`), comprehension `if`, each extra boolean
  operand (`a and b and c` → +2), and each `match` case. Measured **per function**,
  **excluding nested defs** (a nested function is its own unit).
- **Ratchet:** `fail iff worst_complexity > baseline`. Baseline defaults to a huge
  number (off) until recorded; opt-in via the required list + a baseline file.
  The receipt records `worst_complexity`, `complexity_baseline`, `worst_function`.
- Greenfield (no package/source) passes.

### borromeanRings's baseline

`10` (`architecture.py::_referenced_heads`) — the current worst; a new function
that beats it fails the gate until simplified.

## Design

Pure `function_complexities` / `worst_complexity` (source in, numbers out), 100%
covered; the check is thin bash mirroring the coverage/docstring ratchets. Native
stdlib `ast` — no external tool (see ADR-0031 for the radon trade-off).
