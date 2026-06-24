# ADR-0018 — Enforce declared repository layout (specs, root docs, test grouping)

**Status:** Accepted

## Context
Agents working in governed repos produced poor GitHub hygiene: `SPEC.md` files
dumped at the repo root, miscellaneous docs scattered there too, and large test
suites laid out flat with no organization. `05_hygiene` only checks that declared
artifacts **exist** — it says nothing about **where** files live or how they're
organized. Layout is a real maintainability property; make it a declared, gated
invariant rather than a matter of agent taste.

## Decision
A project DECLARES its layout conventions in `borromeanrings.toml` `[layout]`, enforced by
the new required check `07_layout` (fail-closed). Each rule is **independently
opt-in** — off when its config is empty/zero, so the check never surprises an
undeclared project; `init.sh` seeds sensible defaults for new ones.

1. **Specs placement** — every `SPEC*.md` in the repo must live under `specs_dir`
   (borromeanRings: `docs/specs`).
2. **Root-doc allowlist** — every `*.md` directly at the repo root must be in
   `root_doc_allowlist` (borromeanRings: `README.md`, `AGENTS.md`, `PLAN-v0.md`).
3. **Test grouping ("by type when large")** — flat (ungrouped) test files directly
   in `tests_dir` may number up to `test_grouping_threshold`; beyond it they must be
   grouped into type subdirectories (`test_groups`, e.g. unit/integration/e2e). A
   small flat suite stays valid — borromeanRings's own 9 flat tests pass under threshold 15.

Pure decision logic in `meta_harness.layout` (`misplaced_specs`,
`disallowed_root_docs`, `excess_flat_tests`), unit-tested to the repo's 100%
baseline; the check gathers the filesystem facts and calls it.

## borromeanRings self-compliance (part of "build into borromeanRings")
- Moved `docs/SPEC-{deep-research,merge,prompt-rewrite,spine}.md` → `docs/specs/`
  and updated every reference across docs, source, tests, and `borromeanrings.toml`.
- Declared the `[layout]` policy; the gate now passes 9/9 including `07_layout`.

## Alternatives considered
- **A fixed, global convention (no config)** — rejected: layout taste is
  project-specific; the spine keeps it declared and steerable (consistent with the
  config-policy spine, ADR-0010), and avoids dictating *how* the agent organizes
  beyond the declared outcome.
- **Always require nested test dirs** — rejected: flat is idiomatic for small pytest
  suites (borromeanRings's own), so a blanket rule would force needless structure. The
  threshold triggers organization only once a suite is genuinely large.
- **Warn instead of fail** — rejected for declared rules: borromeanRings turns standards
  into gates, not requests. (A project that wants softness simply leaves a rule off.)

## Consequences
- (+) Stray root `SPEC.md`/docs and sprawling flat test dirs now fail the gate — the
  hygiene problems the Maintainer observed cannot land silently.
- (+) Substrate-neutral and reference-mode safe: the check reads the *governed* repo.
- (−) The threshold is a number in config; it is declared policy (not a hidden magic
  constant) and per-project tunable, but it is still a chosen value — documented here.
- (−) The spec/root-doc rules match by filename/path; deliberately simple (no content
  inspection). Good enough for placement hygiene.
