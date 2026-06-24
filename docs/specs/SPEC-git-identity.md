# SPEC — Git-identity enforcement

> borromeo must guarantee commit provenance: every commit/push in a governed repo
> uses the **declared** git identity. A wrong account committing (observed in the
> field) is a correctness/security failure. ADR-0017.

## Problem
borromeo had **no** git-identity enforcement. An agent could commit under any
`git config user.*`, so commits landed under the wrong account.

## Policy (declared, not assumed)
`borromeo.toml`:
```toml
[git]
name  = "wimaan3"
email = "imaansoltan@gmail.com"
```
Empty/absent ⇒ **not enforced** (can't enforce an unknown identity; opt-in by
declaration). `init.sh` seeds it for new projects from the user's `git config`.

## Enforcement — two layers (defense in depth)
1. **Preventive guard** (`PreToolUse` on Bash): before a `git commit` / `git push`
   runs, compare the repo's configured `user.name`/`user.email` (and any
   `--author=` override) to the declared identity. Mismatch ⇒ **deny** the command
   with a clear reason. Stops the bad commit before it exists.
2. **Gate backstop** (`checks/shared/06_git_identity.sh`): fail-closed if the
   configured identity, or any commit unique to the branch (`<base>..HEAD`, base =
   `main` when present), is not the declared identity. Catches anything the guard
   missed (e.g. commits made outside the agent).

## Contracts (`meta_harness.git_identity`, pure + unit-tested)
- `Identity(name, email)`.
- `is_enforced(declared) -> bool` — true iff name or email declared.
- `configured_violation(configured, declared) -> str | None` — reason on mismatch.
- `author_violations(authors, declared) -> list[str]` — offending commit authors.

Only a declared field is checked (declare email only ⇒ name is unconstrained).

## Fail-closed / edges
- Not declared ⇒ pass (not enforced).
- Not a git repo ⇒ pass with note (nothing to attribute).
- No base branch ⇒ check HEAD's author only.
- The guard and gate read identity from the **governed** repo (`CLAUDE_PROJECT_DIR`
  / `PROJECT_ROOT`), so it works when borromeo governs another project by reference.

## borromeo self-compliance
borromeo declares `wimaan3 / imaansoltan@gmail.com`; its configured identity and
history already match, so the new required check `06_git_identity` passes.
