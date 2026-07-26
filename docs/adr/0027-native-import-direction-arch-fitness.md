# ADR-0027 — Native import-direction architectural fitness (not import-linter)

**Status:** Accepted

## Context
`docs/ARCHITECTURE.md` commits to an **acyclic** registry of independent checks
with a config **foundation** (`spine`, the Single Choice Principle) and a research
**testbed** (`deep_research`) explicitly "not the product". Nothing enforced any
of it: `07_layout` governs file *placement*, not import *direction*. Unchecked
architecture decays — a stray `import` from the foundation into a domain module,
or a cycle, would pass every existing gate (matrix row **D**).

## Decision
Add check `35_architecture` plus a declarative `[architecture]` block:
`leaves` (foundation modules that import no sibling), `private` (modules nothing
may import), `forbidden` (explicit `A ↛ B` edges), and `forbid_cycles`. The
analysis is **native stdlib `ast`** in `meta_harness.architecture` — pure
graph→violations functions (unit-tested with synthetic graphs) behind a thin
`build_import_graph`. Rules are opt-in; borromeanRings declares `spine` a leaf,
`deep_research` private, and the graph acyclic.

## Alternatives considered
- **`import-linter`** (the battle-tested tool) — rejected as the mechanism *here*,
  for three concrete reasons: (1) as a *required* gate tool it enlarges the
  external footprint every governed project must install (the gate already
  requires ruff/mypy/bandit/pytest); (2) `run_check` treats a missing tool as a
  hard error, so it can't be built or gated locally without first installing it —
  colliding with this environment's "no silent local install" constraint; (3) our
  contracts (leaf/private/acyclic) are a small, well-understood slice that ~90
  lines of covered `ast` code expresses directly. import-linter wins when
  contracts grow (multi-layer stacks, independence matrices); recorded as the
  promotion path via a future heavy-lane check, not the T0 default.
- **Extend `07_layout`** to also parse imports — rejected: `07_layout`'s secret is
  *file organization*; folding dependency-graph analysis in would break its
  cohesion. A separate check keeps each check single-purpose (the very property
  the pipes-and-filters style buys).
- **Advisory-only** — rejected: import direction is deterministic; a fresh graph
  either satisfies the contracts or doesn't, so fail-closed carries no
  false-positive risk (verified: full gate green with the check required).

## Consequences
- (+) The foundation-leaf, private-testbed, and acyclicity promises in
  ARCHITECTURE.md are now enforced; a regression fails the gate with a named
  violation (`[leaf] spine imports …`, `[cycle] a -> b -> a`).
- (+) Zero new external dependency; `architecture.py` is 100% covered; the graph
  analysis is reusable for future contract kinds.
- (+) Contracts are declared in one place (`borromeanrings.toml`), consistent
  with the Single Choice Principle for the check set.
- (−) The native analyzer is intentionally less expressive than import-linter
  (no multi-layer stacks yet); if contracts outgrow it, promote to import-linter
  on the CI heavy lane.
- (−) One more required check (~1s) — negligible; runs on the internal graph only.
