# SPEC — Docstring-coverage ratchet

**Status:** Implemented · **Realized by:** `src/meta_harness/docstrings.py`,
`checks/python/45_docstrings.sh`, `.borromeanrings-docstring-baseline` · ADR-0029

## Problem

API documentation coverage was unmeasured and unenforced (matrix row **G —
docstring/API-doc coverage**). Documentation rots first and silently; without a
signal, a well-documented codebase drifts toward undocumented as it grows.

## Contract

Check `45_docstrings` measures the fraction of **documentable definitions** with
a docstring and **ratchets** it against a recorded baseline — it may not fall,
but there is **no absolute target to game** (a genuine non-regression signal, in
keeping with the project's stance against arbitrary metric gates).

### What counts as documentable

- the **module** itself (module docstring);
- every **public** (`name` not starting with `_`) class, function, and method;
- **descends into classes** (methods, nested classes) but **not into functions** —
  inner closures are not public API surface and are excluded (matching common
  docstring-coverage tools).

`coverage = documented / total` (1.0 when there is nothing to document).

### Ratchet

```
current  = measure_package(src_dir, package).coverage
baseline = .borromeanrings-docstring-baseline   (default 0 ⇒ vacuous until set)
fail iff current + 1e-9 < baseline
```

The receipt records `docstring_coverage` and `docstring_baseline`. Opt-in: a
project enforces it by adding `45_docstrings` to `[checks].required` and
recording a baseline. Greenfield (no package/source) passes.

### borromeanRings's own baseline

`1.0` — every public definition is documented today, locked in so a new
undocumented public def fails the gate until documented.

## Design

- Pure `analyze_source` / `measure_package` (text/paths in, counts out);
  100% covered. `__init__.py` markers are excluded so an empty one does not
  distort the fraction.
- Mirrors the coverage ratchet (`40_test`): a baseline file, a `current + ε <
  baseline` compare, no external tool.

## Extensibility

A future option could weight by definition kind, or require the docstring to be
non-trivial (length / sections); both slot into `analyze_source`.
