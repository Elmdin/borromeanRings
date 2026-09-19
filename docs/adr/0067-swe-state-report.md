# ADR-0067 — SWE-state report: practises / lacks / adopt next, categorical and sourced

**Status:** Accepted
**Spec:** `docs/specs/SPEC-swe-state.md`
**Refs:** #139, #79 / ADR-0062 (archetypes), ADR-0041 (adoption path), ADR-0046/0049
(status, honest `noop`), #138 (governance matrices), ADR-0024 (profiler), ADR-0038 (coupling)

## Context

`status.sh` answers "is the gate green here, and was that green real?"; `ledger.sh`
answers "has the gate caught anything?". Neither answers the maintainer's question in
#139: **what should this project be doing that it is not** — which practices it has,
which gates would catch what, and what to adopt next. Today that answer comes from the
AI's memory of best practice, which is exactly the source borromeanRings exists to replace
with the record.

The facts are all on disk already: `borromeanrings.toml` (what is required), the last
verdict (what actually passed, `noop`ed or failed), the archetype catalog (what an app of
this kind must have), `adopt.py` (what the upgrade tool would add) and the governance
matrices (which practice each check enforces, and which practices route to a gap).
Nothing joined them.

## Decision

1. **A pure module, `meta_harness.swe_state`.** `assess(...)` takes already-read facts
   and returns frozen dataclasses; `render` prints four sections — Practises, Lacks,
   Adopt next, Sources; `to_json` is `asdict`. `parse_matrices` decodes the matrices'
   *Enforced by* column from text: every `NN_name` token is a check, `gap → #N` is a gap.
   The module never touches the filesystem.

2. **Categorical only, one fixed order.** No score, no percentage, no ranking. "Adopt
   next" is one list in a fixed order — required checks that last reported a failing
   status, then `noop`, then ratchets without a baseline, then RECOMMENDED not adopted,
   then archetype features absent — and *nothing else* orders it. The recommended set
   comes from `adopt.plan_adoption`, so the report and `adopt.sh` cannot disagree.

3. **Honest where it cannot tell.** Never gated ⇒ every required check is `unknown`, not
   lacking; a required check absent from the last verdict (a heavy check after a fast
   run) is `unknown` and its matrix rows are neither enforced nor unmet; a malformed
   input marks its own section `unreadable` and the rest still renders; no matrices on
   disk is said in those words. Matrix rows whose cell names no check and no gap
   (hooks, `merge.sh`, "see #4") are listed as *undecidable from receipts* rather than
   credited or debited. A row that names a gap is a gap even if half of it shipped —
   under-claiming is the safe direction for a report whose subject is hollow greens.

4. **Composition in the entry point, not in a module.** `swe-state.sh` reads the spine,
   the verdict, the archetype evaluation, the baseline files and the matrices, then calls
   the pure core — the same shape as every check script. This keeps `swe_state`'s fan-out
   at the coupling baseline (2: `adopt`, `verdict`); archetype results cross the seam as
   plain `FeatureFact` values. `status.sh --swe` prints the report after the self-status
   block. Advisory: always exit 0; not a check, no receipt.

5. **Matrices are read from `$BORROMEANRINGS_HOME/docs/matrices` by default** (they
   describe borromeanRings's checks, not the governed project) and `--matrices DIR`
   overrides. On a base without them the report says so.

## Alternatives considered

- **A score or a has/partial/missing percentage per matrix.** Rejected — the maintainer
  rejects blended numbers outright (HANDOFF §3 "Threshold-free"); a percentage over rows
  of unequal weight is exactly the meaningless signal #139 warns against.
- **Re-running the gate inside the report.** Rejected — `status.sh --run` already
  refreshes the verdict; a read-only report must not write receipts as a side effect.
- **Importing `spine`, `archetypes`, `verdict` and `adopt` into one module.** Rejected —
  fan-out 4 against a baseline of 2; the ratchet is fixed by design, never by raising the
  baseline (HANDOFF §8).
- **Crediting the shipped half of a `gap →` row (e.g. O5's negative half).** Rejected —
  it would require per-row prose parsing and produce a claim the receipts cannot back.

## Consequences

- A session can answer "what does this project practise / lack / adopt next?" from the
  record, with every line traceable to a check id, a verdict run, a catalog entry, a
  matrix row or an issue.
- Dogfooded on this repository (fast-lane verdict, matrices from `feat/governance-matrices`):
  (one run, 2026-09-10, after a fast-lane gate, so the heavy checks had no verdict entry;
  a run after `--heavy` classifies them and the counts move — the numbers below are a
  dated observation, not a contract)
  20 checks practised; the 4 heavy checks `unknown`; 13 matrix rows enforced
  (S1, S3, S12, D1–D5, O1–O4, M4); 57 rows at a gap; 5 unmet (`34_api_diff`,
  `06_git_identity`, `15_a11y` not adopted — the first and last are deliberate for a CLI
  repo, the second by ADR-0019); S16, D6, D16, O16 undecidable from receipts; nothing to
  adopt.
- The matrices' *Enforced by* convention (a check is named only if its script decides the
  criterion) is now load-bearing for a report, which raises the cost of a sloppy cell —
  the drift `describe.sh` (#132) exists to catch.
- Not done here: the profiler's advisory archetype *detection* (ADR-0024) is not folded
  in — the report uses only the declared archetypes, so an undeclared project shows "no
  archetypes declared" rather than a guess.
