# ADR-0028 — Changelog discipline (Keep a Changelog), non-retroactive first

**Status:** Accepted

## Context
borromeanRings kept no changelog, and nothing enforced one (matrix row **G**).
Conventional commits (09_commits) capture per-commit intent, but the artifact a
human reads to learn "what changed in this release, and why" is a curated
changelog. Adding a *required* "the changelog must be updated when code changes"
check is the obvious enforcement — but doing so naively would retroactively fail
every open PR that touched source before the policy existed.

## Decision
Add check `11_changelog` + a `[changelog]` block with **two independently-gated**
rules:

1. **presence + shape** (`enabled`): `CHANGELOG.md` exists and carries an
   `Unreleased` section. This constrains the repository's *current state*, not a
   branch diff, so enabling it never fails an unrelated in-flight branch.
2. **entry on source change** (`require_entry_on_src_change`): diff-based — if
   source changed on the branch, the changelog must be in the diff. This is
   *retroactive* by nature, so it is a separate opt-in.

borromeanRings enables (1) now and leaves (2) **off** until the current PR queue
merges, then flips it on. `CHANGELOG.md` is seeded in Keep a Changelog format and
added to the `07_layout` root-doc allowlist.

## Alternatives considered
- **Enable the strict diff-rule immediately** — rejected: it would retroactively
  fail the open src-touching PRs (#91/#92 add modules without a changelog line),
  forcing edits across every branch. Splitting presence from the diff-rule lets
  enforcement start now without that friction.
- **Derive the changelog from conventional commits automatically** — attractive
  (09_commits already constrains commit form) but rejected as the *gate*: a
  generated changelog removes the human curation step that makes a changelog
  worth reading, and generation belongs in a release tool, not a fail-closed
  check. The diff-rule nudges the human to curate; generation can layer on later.
- **Only require presence (drop the diff-rule entirely)** — rejected: presence
  alone lets the `Unreleased` section rot. Keeping the diff-rule available (opt-in)
  preserves the path to real "every change is recorded" enforcement.
- **A new required tool (e.g. `towncrier`)** — rejected: pure-Python presence +
  diff checks need no dependency and fit the existing check contract.

## Consequences
- (+) A changelog now exists and is gated; the `Unreleased` section can't silently
  disappear.
- (+) Enforcement started without retroactively breaking the review queue; the
  strict rule is one config flag away once the queue clears.
- (+) `changelog.py` is pure and 100% covered; rules compose (categories,
  non-empty body) as future violation functions.
- (−) Until the strict rule is enabled, a code change *can* land without a
  changelog entry — an accepted, temporary gap with a clear switch-on point.
