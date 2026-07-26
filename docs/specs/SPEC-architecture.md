# SPEC — Architectural fitness (import-direction contracts)

**Status:** Implemented · **Realized by:** `src/meta_harness/architecture.py`,
`checks/python/35_architecture.sh`, `[architecture]` in `borromeanrings.toml` ·
ADR-0027

## Problem

`07_layout` enforces *file* placement, not *dependency* direction. The
architecture documented in `docs/ARCHITECTURE.md` — an **acyclic** registry of
independent checks over a config **foundation** (`spine`, the Single Choice) with
a research **testbed** (`deep_research`) that must stay non-load-bearing — was a
prose promise nothing enforced. Design intent that isn't checked erodes silently
(matrix row **D — dependency-direction / architecture fitness functions**).

## Contract

Declare import-direction rules in `[architecture]`; check `35_architecture`
builds the internal module graph (native stdlib `ast`, no external tool) and
fails closed on any violation. Each rule is **opt-in** (empty/false ⇒ off):

| Rule | Meaning | Violation |
|---|---|---|
| `leaves = [m, …]` | `m` (a foundation) imports **no** internal sibling | `m` imports any sibling |
| `private = [m, …]` | **no** internal module may import `m` (a testbed/sink) | some module imports `m` |
| `forbidden = [[a, b], …]` | `a` must not import `b` | `a` imports `b` |
| `forbid_cycles = true` | the internal graph is acyclic | any import cycle |

### borromeanRings's own contracts

```toml
[architecture]
leaves = ["spine"]           # config foundation depends on no domain module
private = ["deep_research"]  # research testbed stays non-load-bearing
forbid_cycles = true         # ARCHITECTURE.md §2: acyclic, no feedback
```

These are true today and **robust to the in-flight PRs** (e.g. after the mutation
work lands, `deep_research → ratchet`, but `spine` stays a leaf and nothing
imports `deep_research`).

## Design

- **Pure analysis, thin I/O.** `leaf_/private_/forbidden_/cycle_violations` and
  `evaluate` take a graph and return violations (unit-tested with synthetic
  graphs); `build_import_graph` is the only filesystem touch.
- **Absolute + relative imports** are both resolved to sibling names.
- **Native, not import-linter.** A pure-Python check keeps the gate's external
  footprint small (it already requires ruff/mypy/bandit/pytest) and — unlike a
  tool that must be installed to run — can be built and gated locally. See
  ADR-0027 for the trade-off and when import-linter would be preferred.

## Extensibility

Richer layering (multi-tier `layers = [...]`, independence contracts) can be
added as new contract kinds in `evaluate`; import-linter remains an option for a
future heavy-lane check if contract expressiveness outgrows the native analyzer.
