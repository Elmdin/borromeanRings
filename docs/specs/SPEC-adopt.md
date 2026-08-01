# SPEC — Adoption helper for existing projects

**Status:** Implemented · **Realized by:** `src/meta_harness/adopt.py`,
`adopt.sh` · ADR-0041

## Problem

An existing governed project stays at whatever checks its `borromeanrings.toml`
declared when it was bootstrapped. New checks shipped by the enforcement-coverage
program are on disk (shared machinery) but never run until the project opts in —
and opting into ratchets naively makes them vacuous, while opting into all of
them at once turns a healthy project red.

## Contract

`adopt.sh <project-dir>` (default: CWD) migrates a project that already has a
`borromeanrings.toml`:

1. **Plan** — `plan_adoption(current_required, has_changelog)` returns the subset
   of the **recommended set** the project is missing, the ratchet baselines to
   seed, whether a changelog is needed, and the new required list (existing order
   preserved, additions appended). Idempotent: an already-migrated project plans
   no additions.
2. **Seed baselines** — for each newly-added ratchet, write its baseline file from
   the project's *current* value:
   | check | baseline file | seed |
   |---|---|---|
   | `32_complexity` | `.borromeanrings-complexity-baseline` | `worst_complexity(src, pkg)` |
   | `33_coupling` | `.borromeanrings-coupling-baseline` | `worst_fan_out(src, pkg)` |
   | `45_docstrings` | `.borromeanrings-docstring-baseline` | `measure_package(src, pkg).coverage` |
   Skipped when there is no package to measure (the ratchet is greenfield-pass).
3. **Seed changelog** — if `11_changelog` is added and none exists, write a
   minimal Keep-a-Changelog file with an `## [Unreleased]` section.
4. **Rewrite** — `rewrite_required(toml_text, new_required)` replaces the
   `[checks].required` array in place, scoped to the `[checks]` table, preserving
   all other text/comments. Fail-closed: a missing table or array raises.

**Recommended set:** `12_secrets`, `11_changelog`, `32_complexity`,
`33_coupling`, `45_docstrings` — the safe-after-seeding quality/security core.
Excludes library-only (`34_api_diff`), config-gated (`35_architecture`), the
heavy CI lane, and collaboration gates (a separate wave).

## Guarantees

- **Green first run** by construction, except a real `12_secrets` finding (which
  *should* fail — a genuine leaked credential).
- **No absolute targets** — every ratchet baseline is the project's own current
  value.
- **Native / no installs** — stdlib `ast` + text transform only.
- **Idempotent** — re-running adds nothing and re-seeds nothing.
