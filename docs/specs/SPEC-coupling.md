# SPEC — Coupling ratchet (fan-out)

**Status:** Implemented · **Realized by:** `src/meta_harness/coupling.py`,
`checks/python/33_coupling.sh`, `.borromeanrings-coupling-baseline` · ADR-0038

## Contract

`33_coupling` ratchets the **worst efferent coupling (fan-out)** — the most
internal siblings any one module imports — against a baseline. Non-regression, no
absolute ceiling.

- Native: reuses `architecture.build_import_graph`; no external tool.
- `fail iff worst_fan_out > baseline`. Baseline defaults huge (off) until recorded;
  opt-in via the required list + a baseline file. Receipt records `worst_fan_out`,
  `worst_module`. Greenfield passes.
- Exposes `fan_in` (afferent coupling) too, for reporting.

## borromeanRings baseline

`2` (`critic_rubrics` imports `critic` + `doc_drift`). A module that reaches
fan-out 3 fails the gate until pared back. Pure functions, 100% covered.
