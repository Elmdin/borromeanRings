# ADR-0008 — CI runs the gate as the required status check

**Status:** Accepted

## Context
Phase 1 needs GitHub-native auto-merge (`gh pr merge --auto`), which merges a PR once its
**required status checks** pass. That requires a check that runs borromeo's gate on GitHub's
servers — not just locally. It also strengthens QAS-2 (author/environment-agnosticism): the same
`verify.sh` should produce the same verdict on a clean CI runner as on a developer laptop.

## Decision
A GitHub Actions workflow (`.github/workflows/verify.yml`) runs `bash verify.sh` on every
`pull_request` and on `push` to `main`. It installs the check toolchain via
`pip install -e ".[dev]"` (the `dev` optional-dependency group in `pyproject.toml`) so CI runs the
*same* checks as local. This CI job becomes the **required status check** that branch protection
enforces and that native auto-merge gates on.

## Alternatives considered
- **No CI; rely on the local gate + `merge.sh` only** — rejected: the verdict would never be
  verified in a clean environment, and GitHub-native auto-merge has no required check to gate on.
- **A bespoke CI script separate from `verify.sh`** — rejected: it would drift from the local gate,
  breaking "one gate, identical behavior" (the single-source-of-truth principle, ADR-0005).
- **Pin exact tool versions in `dev`** — deferred: lower-bound ranges for now; pin later if CI/local
  drift causes a problem (a tech-debt item, not a v0/Phase-1 blocker).

## Consequences
- (+) The gate is verified on a clean runner for every change; enables native auto-merge.
- (+) Reuses `verify.sh` verbatim — CI and local can never disagree about what "the gate" means.
- (−) Adds a toolchain install step to CI latency (acceptable). Tool versions are range-pinned, so a
  new tool release could in principle change a verdict — surfaced here rather than hidden.
