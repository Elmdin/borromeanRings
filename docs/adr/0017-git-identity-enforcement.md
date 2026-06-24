# ADR-0017 — Enforce the declared git commit identity

**Status:** Accepted

## Context
borromeo had **no** git-identity enforcement. Agents working in governed repos
committed under whatever `git config user.*` happened to be set — and in the field
a wrong GitHub account ended up authoring commits. Commit provenance is a
correctness/security property (who authored what), so this is a real gate gap, not
cosmetics.

## Decision
A project **declares** its commit identity in `borromeo.toml`:
```toml
[git]
name  = "wimaan3"
email = "imaansoltan@gmail.com"
```
Empty/absent ⇒ enforcement off (you cannot enforce an unknown identity — opt-in by
declaration; `init.sh` seeds it for new projects). Enforcement is **two layers**:

1. **Preventive guard** — the `PreToolUse(Bash)` hook blocks `git commit` / `git push`
   when the governed repo's configured `user.name`/`user.email` doesn't match the
   declared identity, with a one-line fix in the denial reason. Stops the bad commit
   before it exists. Fails *open* on guard error (the gate is the backstop).
2. **Gate backstop** — required check `06_git_identity` fails closed if any commit
   unique to the branch is not *authored* by the declared identity (base = `main`/
   `origin/main` when present, else the tip non-merge commit). It checks commit
   **authorship** — provenance metadata that travels with the commit, so the verdict
   holds in CI and fresh clones — **not** the repo's transient `git config user.*`,
   which a CI runner legitimately leaves unset (that is the guard's concern only).
   Catches `--author=` overrides and commits made outside the agent.

Decision logic lives in `meta_harness.git_identity` (pure, unit-tested to the repo's
100% baseline): `is_enforced`, `configured_violation`, `author_violations`. Only
declared fields are checked (declare email only ⇒ name is unconstrained).

## Alternatives considered
- **Guard only** — rejected: a commit made outside the agent (or with `--author=`)
  would slip through; provenance needs a fail-closed gate.
- **Gate only** — rejected: catches the bad commit *after* it exists (rework/history
  rewrite); the guard prevents it up front.
- **Infer identity from the GitHub remote / global git config** — rejected: implicit
  and unsteerable; declaring it in the spine makes the invariant explicit and auditable.

## Consequences
- (+) Commit provenance is now a borromeo invariant — the wrong-account failure the
  Maintainer hit cannot recur silently in a governed repo.
- (+) Substrate-neutral and reference-mode safe: guard and check both read the
  *governed* repo's identity, so it works when borromeo governs another project.
- (−) Requires each project to declare `[git]` (or `init.sh` to seed it); undeclared
  repos get no enforcement (acceptable: identity can't be guessed).
- (−) The guard matches `git commit`/`git push` by substring; exotic invocations could
  evade the *preventive* layer, but the gate backstop still fails them closed.
