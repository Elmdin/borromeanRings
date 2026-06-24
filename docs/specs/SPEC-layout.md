# SPEC — Repository layout enforcement

> Agents in governed repos produce messy GitHub hygiene: specs dumped at the repo
> root, docs scattered, large test suites laid out flat. borromeanRings turns a project's
> **declared** layout conventions into a fail-closed gate. ADR-0018.

## Policy (declared in `borromeanrings.toml`; absent ⇒ not enforced, opt-in)
```toml
[layout]
specs_dir = "docs/specs"                                  # SPEC*.md must live here
root_doc_allowlist = ["README.md", "AGENTS.md", "PLAN-v0.md"]   # the only .md allowed at repo root
test_grouping_threshold = 15                              # >N flat test files ⇒ must group by type
test_groups = ["unit", "integration", "e2e"]              # the intended group dirs (advisory in msg)
```
Each rule is independently opt-in: `specs_dir` empty ⇒ no spec-placement check;
`root_doc_allowlist` empty ⇒ no root-doc check; `test_grouping_threshold` ≤ 0 ⇒ no
test-layout check. `init.sh` seeds sensible defaults so new projects get hygiene.

## Rules (check `07_layout`, fail-closed)
1. **Specs placement** — every `SPEC*.md` in the repo must live under `specs_dir`.
2. **Root docs** — every `*.md` directly in the repo root must be in
   `root_doc_allowlist` (keeps stray `SPEC.md`/notes out of the root).
3. **Test grouping ("by type when large")** — flat (ungrouped) test files directly in
   `tests_dir` may number up to `test_grouping_threshold`; beyond that they must be
   organized into type subdirectories. A small flat suite stays valid (borromeanRings's own).

## Contracts (`meta_harness.layout`, pure + unit-tested)
- `misplaced_specs(spec_paths, specs_dir) -> list[str]` — SPEC paths not under `specs_dir`.
- `disallowed_root_docs(root_docs, allowlist) -> list[str]` — root `.md` not allowed.
- `excess_flat_tests(flat_count, threshold) -> bool` — too many ungrouped tests.

The check gathers the filesystem facts (repo-relative `SPEC*.md` paths, root `*.md`
names, count of test files directly under `tests_dir`) and calls these.

## borromeanRings self-compliance
- Move `docs/SPEC-{deep-research,merge,prompt-rewrite,spine}.md` → `docs/specs/`;
  update every reference.
- Root `.md` = README/AGENTS/PLAN-v0 (all allowlisted).
- 9 flat tests < threshold ⇒ test-layout passes.
