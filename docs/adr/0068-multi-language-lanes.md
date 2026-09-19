# ADR-0068: TypeScript and Go check lanes — honest about absent tools, never networked

**Status:** Accepted · 2026-09-10 · phase 1 of #67 · supersedes the "only the Python set
ships" consequence of ADR-0015

## Context
ADR-0015 made the check set selectable by `[project].language` and left every non-Python
lane as a follow-up. A TypeScript or Go project could declare its language and get no
receipts — fail-closed, and useless. ADR-0054 §consequences already chose `ast-grep` as
the structural primitive for non-Python code. This ADR ships the first two lanes behind
the contract in `docs/specs/SPEC-multi-language.md`.

## Decision
1. **Same ids, same semantics.** `checks/typescript/` and `checks/go/` each provide
   `00_build / 10_format / 20_lint / 30_typecheck / 40_test / 50_security` with the
   guarantees Python's lane gives, so `[checks].required`, the verdict, the ledger and
   `status.sh` need no per-language branch. Tools: `tsc`, `prettier`, `eslint`, `tsc
   --strict`, `vitest`|`jest` (istanbul `json-summary`), `ast-grep` with shipped rules;
   `go build`, `gofmt -l`, `go vet`, `staticcheck`, `go test -coverprofile` + `go tool
   cover -func`, `gosec`.
2. **A missing lane tool is `noop`, naming it — never `error`, never an install.** Python's
   toolchain is borromeanRings's own dev dependency, so its absence is a harness defect
   (`error`). A TypeScript or Go toolchain belongs to the governed project. The gate
   reports `<tool> not installed`, counts it in `inspected NOTHING: N of M`, and leaves
   the decision to the maintainer. The gate never runs `npm install`, `npm ci`, `go get`
   or `go install`; the integration test asserts no `node_modules` appears.
3. **No network on the fast lane.** `npm audit` (in any form) and `govulncheck` fetch
   advisory databases; both are excluded from the fast lane and tracked for the heavy lane
   (#193). A Stop-hook gate that depends on a registry is neither deterministic nor
   available offline.
4. **Closed language vocabulary, fail-closed.** `spine.SUPPORTED_LANGUAGES = ("python",
   "typescript", "go", "none")` (`none` = shared checks only); `load_config` raises on
   anything else and `verify.sh` now refuses to run instead of silently falling back to
   Python (it did before — an unknown language would have run the wrong lane and
   reported green).
5. **One coverage ratchet for every language.** `.borromeanrings-coverage-baseline` is the
   file for all lanes; tool summaries are parsed by the pure, fixture-tested
   `meta_harness.lang_coverage`, the decision is `meta_harness.ratchet.decide_ratchet`,
   and `adopt.sh` seeds the baseline from the latest measured `40_test` receipt
   (`adopt.coverage_seed`) since adoption never runs a language's test tool.
6. **Parsing lives in Python, never in bash.** `lang_coverage` (istanbul / `go tool cover`
   / `go test` summaries) and `lang_security` (`ast-grep --json`) are 100 % line+branch
   tested on hand-written fixtures that follow the tools' documented formats.

## Alternatives considered
- **`error` for a missing tool, as Python does** — rejected: it would fail every governed
  TS/Go project on a machine without the toolchain (CI runners for this repo included),
  for a reason that is not the project's code.
- **Silently `pass` when the tool is absent** — rejected: ADR-0049's hollow-green defect.
- **Install the tool on demand** — rejected: the gate must never mutate the project or
  the machine; it is also network.
- **`npm audit --omit=dev` on the fast lane** — rejected: network (§3).
- **`go build` again in `30_typecheck`** — rejected: a duplicate signal dressed as a sixth
  check; `staticcheck` (or an honest `noop`) is the truthful content of that slot for Go.

## Consequences
- (+) Issue #67's acceptance criterion "a TS project and a Go project pass the gate using
  their check sets" holds — with the honest caveat that on a machine without the tools
  the pass is `6 of 6 inspected NOTHING`, printed in the output.
- (+) Adding a language is now a documented recipe (SPEC §6) with three `_lib.sh` helpers.
- (−) Phase 1 is the fast lane only. Per-language ratchets (#190), mutation (#191),
  `18_api_contracts` via ast-grep (#192) and heavy-lane audits (#193) are filed.
- (−) The positive-path integration tests (a real `go test`, a real `tsc`) are gated on the
  tool being present and were **skipped** on the machine that built this; they run
  wherever the tool exists.
- (−) `describe.py`'s `_LANES` (registry, #132) is not on this branch's base; add
  `"typescript", "go"` there and regenerate the README block at rebase time.
