# SPEC — Multi-language check lanes (TypeScript, Go), phase 1

**Status:** implemented (phase 1) · ADR-0068 · closes the lane part of #67 · supersedes the
"Python only" consequence of ADR-0015.

## 1. Problem

ADR-0015 made the check set language-selectable (`[project].language` → `checks/<language>/`)
but only `checks/python/` ever shipped. A TypeScript or Go project declaring its language
got no receipts and failed closed — correct, and useless. This spec defines the contract a
**language lane** must satisfy and instantiates it for TypeScript and Go.

## 2. The lane contract

A lane is a directory `checks/<language>/` holding the six fast-lane checks below. Each has
the **same id and the same semantics** as Python's, so a governed project's
`[checks].required` reads identically whatever the language and the verdict/ledger/status
code needs no per-language branch.

| Id | Guarantee | Python (reference) | TypeScript | Go |
|---|---|---|---|---|
| `00_build` | the declared source compiles | `compileall` + import | `tsc -p <tsconfig> --noEmit` | `go build ./...` |
| `10_format` | no unformatted file | `ruff format --check` | `prettier --check .` | `gofmt -l <src>` (non-empty list ⇒ fail; gofmt itself exits 0) |
| `20_lint` | no lint violation | `ruff check` | `eslint .` | `go vet ./...` |
| `30_typecheck` | no type error beyond what the compiler already proved | `mypy` | `tsc -p <tsconfig> --noEmit --strict` | `staticcheck ./...` |
| `40_test` | tests pass **and** coverage does not regress (ratchet) | `pytest --cov` | `vitest run --coverage` (or `jest --coverage`) | `go test -coverprofile` + `go tool cover -func` |
| `50_security` | no finding from the language's offline static analyzer | `bandit` | `ast-grep scan` with the shipped rules (`checks/typescript/rules/security.yml`) | `gosec ./...` |

Rules every lane check obeys (these are the contract; the Python scripts are the model):

1. **Source discovery** is `meta_harness.source_coherence.walk_sources(src_dir, suffix)`
   (via `borromeanrings_source_count` in `checks/_lib.sh`). It prunes `SKIP_DIRS`
   (`node_modules`, `vendor`, `dist`, `build`, `.venv`, …) so vendored code never counts
   as the project's own. Suffixes: TypeScript `.ts` + `.tsx`; Go `.go`.
2. **Greenfield ⇒ `noop`.** No source of the lane's language under `src_dir` ⇒ the check
   emits `noop` with "no <language> source in '<src_dir>' yet (greenfield)". Planning must
   never be forced to scaffold code (ADR-0049).
3. **Missing tool ⇒ `noop`, naming the tool.** When the lane's tool is not installed the
   check emits `noop` and its log reads exactly `<tool> not installed` (e.g.
   `tsc not installed`, `go not installed`, `ast-grep not installed`,
   `vitest not installed; jest not installed`). This deliberately differs from Python's
   `error` for a missing tool: Python's toolchain is borromeanRings's own declared dev
   dependency, while a TypeScript or Go toolchain is the governed project's to provide.
   The gate **never installs anything** and **never fails a project for an optional tool
   that is absent** — it says so on the record (`inspected NOTHING: N of M`), and the
   maintainer decides whether that green is good enough.
4. **Tool ran and failed ⇒ `fail`** (fail closed): a nonzero exit, unformatted files, a
   coverage regression, a missing `tsconfig.json` when TypeScript source exists, or a Go
   module whose packages all report `[no test files]` while source exists.
5. **Tool lookup** (`borromeanrings_lane_tool`): `<project>/node_modules/.bin/<tool>` first
   (the JavaScript convention — tools are project-local), then `PATH`. Go tools are
   `PATH`-only.
6. **No network on the fast lane.** Anything that contacts a registry is excluded:
   `npm audit` (any form, including `--omit=dev`) and `govulncheck` both fetch advisory
   databases, so neither may run on the Stop gate. They belong on the heavy lane (phase 2,
   see §5). `npm ci` / `go mod download` are likewise never run by a check: the project's
   dependencies must already be present, or the tool fails and the check fails closed.
7. **Bounded.** Every tool invocation goes through `borromeanrings_run_bounded` (wall-clock
   timeout, ADR on `_lib.sh`), so a hanging `vitest` cannot hang the gate.

## 3. Tool choices, with reasons

**TypeScript.** `tsc` is the compiler and the type checker; `00_build` runs it as declared
by the project's `tsconfig.json`, `30_typecheck` re-runs it under `--strict`
(`noImplicitAny`, `strictNullChecks`, …), which is a stronger guarantee than the project
may have opted into and costs nothing when it already has. `prettier` and `eslint` are the
ecosystem's format and lint defaults (both offline, both read project config; ESLint 9
without a config file errors, which fails closed, as it should). `vitest` is preferred
for tests and `jest` is the fallback; both emit the istanbul `coverage-summary.json`
format when asked for the `json-summary` reporter, so one parser serves both
(`lang_coverage.istanbul_line_percent`). `50_security` uses **ast-grep** — the structural
matcher the tooling survey verified (MIT, offline, no key, machine-readable JSON output)
and ADR-0054 already routes non-Python contracts through — with a small shipped rule file
of high-confidence sinks (`eval`, `new Function`, `document.write`). `npm audit` is
excluded (network; §2.6).

**Go.** The Go toolchain ships build, format, vet, test and coverage in one binary, all
offline: `go build ./...`, `gofmt -l`, `go vet ./...`, `go test -coverprofile`. Because the
compiler already type-checks in `00_build`, the `30_typecheck` slot holds the ecosystem's
type-aware static analyzer, `staticcheck` (offline, no key), and is an honest `noop` when
it is absent. `50_security` is `gosec` (offline, static). `govulncheck` is excluded
(network; §2.6).

**ast-grep** (both lanes, C/C++ later): survey-verified `github.com/ast-grep/ast-grep`,
MIT, no account, offline, `--json` output. Absent on this machine at the time of writing;
the check reports `ast-grep not installed`.

## 4. The coverage ratchet per language

Same file, same rule, same code path:

- **Baseline file:** `<project>/.borromeanrings-coverage-baseline` (one number, percent
  of lines). Absent ⇒ baseline `0` ⇒ the ratchet is vacuous until seeded — exactly as for
  Python.
- **Measurement:** the tool's own coverage summary is parsed by the pure module
  `meta_harness.lang_coverage` (100 % line + branch tested on hand-written fixtures that
  follow the tools' documented formats):
  - TypeScript: `total.lines.pct` from istanbul's `coverage-summary.json` (vitest
    `--coverage.reporter=json-summary`, jest `--coverageReporters=json-summary`). An
    `"Unknown"` pct (istanbul's value when zero lines were instrumented) ⇒ no number ⇒ fail
    closed with a message.
  - Go: the `total:` line of `go tool cover -func=<profile>`
    (`total:\t(statements)\t85.7%`).
- **Decision:** `meta_harness.ratchet.decide_ratchet(current, baseline,
  higher_is_better=True)` — the single ratchet primitive; a drop below the baseline is a
  `fail` with `COVERAGE REGRESSION: x% is below baseline y%` in the log; the receipt carries
  `coverage_percent` and `coverage_baseline`.
- **Seeding:** `adopt.sh` seeds `.borromeanrings-coverage-baseline` (when `40_test` is
  required and the file is absent) from the most recent `40_test` receipt's
  `coverage_percent`, whatever the language (`meta_harness.adopt.coverage_seed`). No
  receipt yet ⇒ it says to run `verify.sh` once first. This is the only way the baseline
  gets a value without the maintainer writing it: adopt never runs a language's test tool.

## 5. Deliberately NOT in phase 1 (each tracked)

| Not shipped | Why not now | Tracked in |
|---|---|---|
| Complexity / coupling / docstring ratchets for TS and Go (`32`, `33`, `45`) | Each needs a native or tool-backed measurer per language; the Python ones use `ast`. Candidate: `ast-grep`-driven counts or `gocyclo`/`eslint complexity`. | #190 |
| Mutation testing on the heavy lane (`60_mutation`) for TS (Stryker) and Go (`gremlins`/`go-mutesting`) | Heavy-lane tool checks; each needs its own summary parser + ratchet wiring. | #191 |
| `18_api_contracts` for TS and Go | ADR-0054 routes non-Python through ast-grep; the rule taxonomy must be mapped onto ast-grep patterns per language. | #192 |
| Network dependency audits (`npm audit`, `govulncheck`) on the **heavy** lane | Excluded from the fast lane by §2.6; the heavy lane already runs `pip-audit`, so the shape exists. | #193 |
| Describe/registry (`describe.py` `_LANES`) and `04_self_description` regeneration | Not on this branch's base (`feat/api-contracts`); it lands with #132 (`feat/self-description`). Add `"typescript", "go"` to `_LANES` and re-run `./describe.sh --readme` at rebase time. | #132 |

## 6. Adding a language (the recipe #67 asked for)

1. Add the name to `meta_harness.spine.SUPPORTED_LANGUAGES` (`python`, `typescript`, `go`, and
   `none` for a project governed by shared checks only; unknown languages fail closed
   in `load_config`, and `verify.sh` refuses to run rather than silently defaulting to
   Python).
2. Create `checks/<language>/{00_build,10_format,20_lint,30_typecheck,40_test,50_security}.sh`
   following `checks/go/` (the thinnest instance): source count via
   `borromeanrings_source_count`, tool via `borromeanrings_lane_tool`, missing tool via
   `borromeanrings_noop_missing_tool`, invocation via `run_check` or
   `borromeanrings_run_bounded`.
3. Put any parsing in a pure module under `src/meta_harness/` with fixture-based tests
   (never parse in bash).
4. Document the lane in `docs/CHECKS.md`; write the ADR; add an integration test that drives
   `verify.sh` on a fixture project with the tools hidden (`tests/integration/test_lane_*.py`).

## 7. Verification

- Unit: `tests/unit/test_spine.py` (vocabulary), `tests/unit/test_lang_coverage.py`,
  `tests/unit/test_lang_security.py`, `tests/unit/test_adopt.py` (coverage seed).
- Integration: `tests/integration/test_multi_language_gate.py` drives the real `verify.sh`
  on a fixture TypeScript project and a fixture Go project with every lane tool hidden
  from `PATH` (a sandboxed `PATH` of symlinks): every lane check `noop` naming its tool,
  gate green, `inspected NOTHING: 6 of 6`. An unknown language fails closed. Positive
  cases run only when a tool is present on the machine (`go`, `node_modules/.bin/tsc`).
