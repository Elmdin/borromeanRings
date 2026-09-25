# Survey — inferring a project's package, and disclosing what a run did not inspect

**Question.** An audit showed that following this harness's own onboarding leaves three
checks measuring nothing and the first green run silent about it (ADR-0089). Two small
capabilities were needed: read the importable package from a project's layout, and list
the checks that inspected nothing *outside* the graded set. Did anything here, in a
dependency, or in the ecosystem already do either?

## What already exists

| Where | What was found | Fit |
|---|---|---|
| This repo | `meta_harness.adopt` — `plan_adoption`, `RECOMMENDED`, `RATCHET_BASELINES`, `coverage_seed`. Already the module that decides what a project should adopt and what to seed. | **Extend.** `infer_package` belongs beside `coverage_seed`: both answer "what value should this project's config hold", read from the project rather than asked of the user. No new module, and `init.sh` imports the same function `adopt.sh` does, so the two entry points cannot disagree. |
| This repo | `meta_harness.source_coherence.walk_sources` — walks a project's source, skipping vendored trees. | **Not a fit, and worth saying why.** It answers "which files are this project's own code", given a root. The question here is which *directory* is the importable package — one level up, and decided by `__init__.py`, which `walk_sources` has no opinion about. |
| This repo | `meta_harness.layout` — `misplaced_specs`, `disallowed_root_docs`, `excess_flat_tests`. | **Not a fit.** Layout *rules* (what a project must not do), not layout *discovery* (what a project has). Putting inference there would mix a policy module with a reading one. |
| This repo | `meta_harness.verdict.advisory_failures` — failing receipts outside the expected set, with untrusted-JSON handling. | **Copied deliberately, one predicate changed.** `hollow_outside` is that function with `is_failing` replaced by `status == "noop"`. Two near-identical scans is worse than one parameterised scan on any other day; here the shared part is six lines of JSON hygiene and the difference is the entire meaning of each, so the duplication is legible and the alternative (a `predicate=` argument) reads worse at both call sites. Noted as a real trade, not an oversight. |
| A declared dependency | `setuptools.find_packages` / `find_namespace_packages`. | **Not a fit.** It is a build-time discovery over a configured layout, needs setuptools importable in the harness's own trusted interpreter, and returns every package including sub-packages — where this needs the single top-level one, or an honest "cannot tell". Six lines of `pathlib` against a build dependency in the gate's own path. |
| Python standard library | `importlib.util.find_spec`, `pkgutil.iter_modules`. | **Not a fit.** Both answer "is this importable *from here*", which requires the project on `sys.path` — precisely what the gate's trusted interpreter refuses to do (ADR-0080). The question is answered from the filesystem, not from an import. |
| Ecosystem | `setuptools-scm`, `hatch`'s package discovery, `poetry`'s `packages` inference (advisory — no key-free search exists; ADR-0051). | **Not a fit.** All are build backends inferring what to *package*; adopting one would put a build tool in the gate's dependency set to answer a question about a directory name. |

## Decision

**Build, and keep both small.** `infer_package` is six lines of `pathlib` in the module
that already answers "what should this project's config say", and it is deliberately
conservative: two candidate packages or none returns `""`, because guessing wrong is worse
than asking. `hollow_outside` is an acknowledged near-duplicate of `advisory_failures`,
kept separate because what each one *means* is the part that differs.

The alternative that mattered most was not a library but a non-change: leave onboarding to
the documentation. ADR-0089 records why that lost — the instructions already existed, and
following them produced a red gate and three checks that could not fail.

## Sources

- `grep -rn "package" src/meta_harness/ checks/ init.sh adopt.sh` — every existing reader
  of `[project].package`.
- `docs/adr/0080-gate-python-off-project-sys-path.md` (why import-based discovery is out),
  `docs/adr/0041-adoption-helper.md`, `docs/adr/0049-honest-noop-status-and-source-coherence.md`,
  `docs/adr/0051-prior-art-gate.md` (key-free ecosystem search).
- The audit itself: a fresh external project, `init.sh` → gate → `adopt.sh` → gate, with
  four injected defects.
