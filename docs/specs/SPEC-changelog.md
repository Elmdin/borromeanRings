# SPEC — Changelog discipline (Keep a Changelog)

**Status:** Implemented · **Realized by:** `src/meta_harness/changelog.py`,
`checks/shared/11_changelog.sh`, `[changelog]` in `borromeanrings.toml`, `CHANGELOG.md` ·
ADR-0028

## Problem

borromeanRings had no changelog and nothing enforced one — a released change had
no human-readable record of *what* changed and *why* (matrix row **G —
changelog updated**). Conventional commits capture intent per commit, but a
curated changelog is the artifact humans read.

## Contract

Declare `[changelog]`; check `11_changelog` enforces (opt-in via `enabled`):

| Rule | Config | Retroactive? | Meaning |
|---|---|---|---|
| **presence + shape** | `enabled = true` | No — constrains repo state | `path` exists and contains an `Unreleased` section |
| **entry on source change** | `require_entry_on_src_change = true` | **Yes** — diff-based | if any file under `src_dir/` changed in `base..HEAD`, `path` must be among the changed files |

`base` resolves like `09_commits` (`origin/dev` → `dev` → `origin/main` → `main`,
then `merge-base HEAD base`). No base ⇒ nothing to diff ⇒ strict rule is a no-op.

### borromeanRings's own policy

```toml
[changelog]
enabled = true
path = "CHANGELOG.md"
require_entry_on_src_change = false   # enable after the current PR queue merges
```

The strict rule is deliberately **off** for now: turning on a *required*
diff-rule would retroactively fail open src-touching PRs that predate the policy.
The presence rule is safe to enable immediately because it constrains the
repository's current state, not a branch diff.

## Design

- Pure `presence_violation` / `src_change_violation` (text/paths in, message or
  `None` out), unit-tested; the check wires git + config. `changelog.py` 100%
  covered.
- The strict rule keys off `src_dir/` only, so docs/test-only changes need no
  changelog entry, and a sibling like `source_notes/` is not mistaken for `src/`.

## Extensibility

A future rule could parse the `Unreleased` section for the change *categories*
(Added/Changed/Fixed) or require a non-empty entry body; both slot in as
additional pure violation functions.
