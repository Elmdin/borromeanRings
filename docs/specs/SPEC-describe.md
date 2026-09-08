# SPEC — Capability self-description (`describe.sh`) + count drift guard

**Status:** Draft · **Closes:** #132 · **ADR:** 0052 (to write)

## Problem

Every AI summary of this project lists 6–8 quality gates. The real surface is ~30 checks
across six governance matrices, threshold-free ratchets, tamper-evident receipts, a
`noop` status, portfolio + effectiveness views, an adoption path, and advisory lanes.
The truth exists in the registry, the spine, the ADRs and `ENFORCEMENT-COVERAGE.md` —
but nothing *presents* it. An agent reads the README's "The checks (v0)" table of eight
and stops. Same shape as a hollow green: the truth exists and is not surfaced. And the
README's own stated count has drifted twice this cycle ("eight" → "nineteen" → "twenty").

## Contract

### `describe.sh` — a generated capability report

Read-only, always exits 0 (advisory, like `status.sh`). Renders from **sources of truth
only** — never from hand-written prose that can drift:

| Section | Source of truth | How |
|---|---|---|
| Checks (id, what it enforces, lane) | `checks/{shared,python,ci}/[0-9]*.sh` | parse `id=`/`cmd=`; fallback: `run_check "ID" "tool"` for the five inline scripts |
| Which are required / heavy *here* | `borromeanrings.toml` via `load_config` | `required_checks`, `heavy_checks` |
| Ratchets | the `cmd=` text contains "ratchet" | derived, not listed by hand |
| Decisions | `docs/adr/0*.md` | count + the ADR each check's header cites |
| Governance matrices | `docs/ENFORCEMENT-COVERAGE.md` §6 table | parse `| **Name** | status |` rows — the one hand-maintained input, and it is the matrices' single source |
| Commands | `*.sh` at repo root | verify / status / ledger / merge / init / adopt / install-global |
| Skills | `.claude/skills/*/` directory names | the installed set, not their prose |

Not derived (deliberately, until there is a source of truth to derive from): advisory
lanes and "planned" rows — a fixed hand-list would be exactly the drift this replaces.

Output: Markdown to stdout (`--json` for machines). `--readme` rewrites the block between
`<!-- describe:begin -->` / `<!-- describe:end -->` in the project's README (appends if
absent), touching nothing outside the markers; `summary_block` + `replace_block` are the
pure core of that. The `borromeanrings-status` skill and `AGENTS.md` point at it.

### `04_self_description` — the drift guard (a gate)

Fail-closed. The README's stated counts must equal the registry:
- `**N checks**` ⇔ number of check scripts on disk
- `(<word> gates` ⇔ `len(required_checks)` for this repo (number words parsed)
Absent claim ⇒ `noop` (a README may choose not to state a count). Wrong claim ⇒ `fail`,
printing both numbers. This is what stops the README rotting again.

### README

The v0 table of eight stays as history but is retitled; a generated block (marked
`<!-- describe:begin/end -->`) carries the real summary, refreshed by `describe.sh
--readme` and gated by the count guard.

## Acceptance (from #132)
- [ ] `describe.sh` output names every check on disk and all six matrices.
- [ ] `04_self_description` fails on a wrong README count; `noop` when none stated.
- [ ] A cold agent, given only the repo, produces a summary naming ≥ 20 checks and all six matrices (test: run `describe.sh`, assert counts).
- [ ] Each test verified to fail when its behaviour regresses.

## Quality attributes
Generated, not written · drift-guarded by a gate · threshold-free (counts are equalities, not targets) · `noop`-honest.
