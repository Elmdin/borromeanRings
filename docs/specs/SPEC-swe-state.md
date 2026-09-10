# SPEC — SWE-state report: what a project practises, lacks, and should adopt next

**Status:** Accepted (implemented)
**Drives:** ADR-0067
**Refs:** #139 (the contract), #79 / ADR-0062 (archetypes), ADR-0041 (adoption path),
ADR-0046/0049 (status, honest `noop`), #138 (governance matrices), ADR-0024 (profiler)

## 1. Problem

`status.sh` says whether the gate is green; `ledger.sh` says whether it caught anything.
Neither says **what the project should be doing that it is not**. A maintainer who asks
"what does borromeanRings know about good engineering, and how much of it does this
project do?" has to read `borromeanrings.toml`, the last verdict, the archetype catalog,
`adopt.py`'s recommended set and five matrix documents, then reconcile them by hand — or
ask the AI, which answers from memory rather than from the record.

## 2. Goals

- **G1** One report, for ONE governed project, answers three questions from facts already
  on disk: what it **practises**, what it **lacks**, what to **adopt next**.
- **G2** Every line is traceable to a source (a check id, a verdict run, a catalog entry,
  a matrix row, an issue) — auditable, never opinion.
- **G3** Categorical only. **No score, no percentage, no ranking** by anything but the
  fixed adoption order in §4.4 (the maintainer rejects blended numbers outright).
- **G4** Honest about what it cannot tell: `unknown` / `unreadable` / "no matrices on
  disk" — never a guess, never a silent omission.
- **G5** Advisory: always exits 0; reads only; nothing is written anywhere.

## 3. Non-goals

- Not a gate and not a check: no receipt, no `CHECKS.md` entry.
- Does not re-run the gate; it reads the **last** verdict (`status.sh --run` refreshes).
- Does not evaluate matrix rows itself — it maps each row's *Enforced by* column onto the
  project's check states. A row that names no check is reported undecidable.
- Does not edit `borromeanrings.toml`; `adopt.sh` performs adoption.

## 4. Contracts

### 4.1 Inputs (facts already on disk)

| Fact | Source | Read by |
|---|---|---|
| required and heavy check ids | `borromeanrings.toml` `[checks].required` + `[checks].heavy` | `spine.load_config` |
| declared archetypes | `borromeanrings.toml` `[project].archetypes` | `spine.load_config` |
| last gate outcome per check | `.meta-harness/last_verdict.json` | `verdict.read_last_verdict` |
| archetype feature evaluation | the working tree | `archetypes.evaluate` + `required_features` (for the `why` citation) |
| adoption vocabulary | `adopt.RECOMMENDED`, `adopt.RATCHET_BASELINES`, `adopt.plan_adoption` | `swe_state` directly |
| ratchet baseline files | `<project>/<RATCHET_BASELINES[check]>` presence | the entry point |
| matrix rows | `docs/matrices/0N-*.md` under a `matrices_dir` (default `$BORROMEANRINGS_HOME/docs/matrices`; `README.md` excluded) | `swe_state.parse_matrices` (pure, text in) |

The pure core `meta_harness.swe_state` never touches the filesystem: `assess(...)` takes
these facts as arguments. `swe-state.sh` is the composition root that reads them
(the same shape as every check script: a bash entry point around a Python heredoc).
Fan-out of `swe_state` is **2** (`adopt`, `verdict`) — the coupling baseline; archetype
results cross the seam as plain `FeatureFact` values, not as an import.

### 4.2 Check states

For every check `c` in required ∪ heavy, in declared order:

| Condition | `status` |
|---|---|
| no verdict on disk (never gated) | `unknown` |
| verdict present but `c` absent from it (e.g. heavy check after a fast run) | `unknown` |
| verdict present, `c` present | the recorded status verbatim (`pass`, `noop`, `fail`, `error`, …) |

`practised` ⇔ `status == "pass"`. `lacking` ⇔ `verdict.is_failing(status)` **or**
`status == "noop"`. `unknown` is neither: **never gated ⇒ every required check is unknown,
not lacking**.

### 4.3 The three sections

**Practises**
- checks: required ∪ heavy with status `pass`; the `unknown` ones are listed on their own
  line so a heavy check never run on the fast lane is visible, not silently absent;
- archetype features present (id, title, evidence-free — the `21_archetype` log carries
  evidence);
- matrix rows *enforced*: every check id the row's *Enforced by* cell names is practised
  here, and the cell names no gap.

**Lacks**
- checks required but last reported `noop` / failing (with the status);
- RECOMMENDED checks not required (`plan_adoption(required, has_changelog).add_checks`,
  the same list `adopt.sh` would apply — the report and the upgrade tool agree);
- ratchets without a baseline: required checks in `RATCHET_BASELINES` whose baseline file
  is absent (a ratchet with no baseline is vacuous — ADR-0041);
- archetype features absent;
- matrix rows at a **gap** (`gap → #issue` in the cell; the issue is cited), and rows
  **unmet** here: the cell names a check that is lacking (`noop`/failing) or not adopted
  (in the registry, not in this project's required set).

**Adopt next** — one flat list in this fixed order, each item citing its source; within a
group, the project's own declared order (checks) or catalog order (features):

1. `[gate]` required checks that last reported a failing status, then those that reported
   `noop` — the fail-closed gaps the gate already demands;
2. `[baseline]` ratchets without a baseline — seed `<file>` from current state (`adopt.sh`);
3. `[check]` RECOMMENDED not adopted — add to `[checks].required`;
4. `[feature]` archetype features absent — with the catalog's `why` citation.

Nothing else orders the list. Matrix gaps are **not** adoptable by the project (they route
to a borromeanRings issue) and appear only under Lacks.

**Sources** — one line per input naming the file/run it came from, its readability, and
the matrix rows that were *undecidable* (no check id and no gap in the cell — e.g. hooks,
`merge.sh`, "see #4"): listed by id so the under-claim is visible.

### 4.4 Matrix-row classification

`Enforced by` cell → `checks` = every `NN_name` token; `gap` = the first `#NNN` after
`gap →` (or `""`).

| cell | state |
|---|---|
| contains `gap →` | `gap` (Lacks; partially-shipped halves are deliberately **not** credited) |
| names checks, project never gated | `unknown` |
| names checks, all practised | `enforced` (Practises) |
| names checks, one is `noop`/failing here | `lacking` (Lacks · unmet) |
| names checks, one is not in required ∪ heavy | `not_adopted` (Lacks · unmet) |
| names no check and no gap | `undecidable` (Sources) |

### 4.5 Entry points

- `swe-state.sh [--json] [--matrices DIR]` — resolves `BORROMEANRINGS_HOME` (its own dir)
  and the project (`BORROMEANRINGS_PROJECT` → `CLAUDE_PROJECT_DIR` → `$PWD`, then the
  nearest enclosing `borromeanrings.toml`). Text by default; `--json` is `asdict` of the
  report. Exit 0 always (advisory), including "not governed".
- `status.sh --swe` — prints the self-status block, then this report.

### 4.6 Rendering (plain text, sectioned)

```
SWE state — <project name>
Practises
  checks (required, last reported pass): …
  checks unknown (not in the last verdict): …
  archetype features present (<archetypes>): …
  matrix rows enforced: …
Lacks
  checks required but last reported noop/fail: …
  recommended by adopt.sh, not required: …
  ratchets without a baseline: …
  archetype features absent: …
  matrix rows at a gap: S6 (→ #58), …
  matrix rows unmet here: D7 (34_api_diff: not adopted), …
Adopt next
  1. [gate]     …
  (nothing to adopt)
Sources
  config: … · verdict: … · archetypes: … · matrices: … · ordering: fixed …
```

Empty lists render `none`; unknowable lists render the reason (`unknown — never gated`,
`unreadable`, `no matrices on disk`, `no archetypes declared`).

## 5. Edge cases

| Case | Required behaviour |
|---|---|
| never gated | every check `unknown`; Lacks·checks = `unknown — never gated`; Adopt next has no `[gate]` items; matrix rows naming checks are `unknown` |
| verdict file present but malformed | `verdict` in `unreadable`; checks `unknown` with that reason; the rest renders |
| `borromeanrings.toml` unreadable | `config` in `unreadable`; checks/recommended/ratchets/archetypes report `unreadable`; matrices still render (gap rows are project-independent; check rows are `unknown`) |
| no archetypes declared | feature lines say `no archetypes declared`; no `[feature]` items |
| archetype evaluation raised | `archetypes` in `unreadable`; feature lines say `unreadable` |
| `matrices_dir` absent or holds no `0N-*.md` | matrix lines say `no matrices on disk`; Sources says so |
| a matrix file unreadable | `matrices` in `unreadable`; matrix lines say `unreadable` |
| not a governed project | one line: `NOT GOVERNED — no borromeanrings.toml …`; exit 0 |
| heavy check never run (fast verdict) | `unknown`, never `lacking` |

## 6. Verification

- Unit (exact-value, `tests/unit/test_swe_state.py`): every section on a full fixture;
  each edge case in §5; the fixed adopt-next order; matrix parsing of the real cell
  shapes (✅, ⚠️, `gap →`, hooks-only, `see #4`); 100 % line + branch of `swe_state.py`.
- Integration (`tests/integration/test_swe_state_cli.py`, mutmut-ignored): a governed
  fixture gated once with a `noop` and a `fail`, `archetypes = ["cli"]`, run through
  `swe-state.sh` (text + `--json`) and `status.sh --swe`, asserting exact section content.
- borromeanRings's own report (dogfood) is recorded in the ADR.
