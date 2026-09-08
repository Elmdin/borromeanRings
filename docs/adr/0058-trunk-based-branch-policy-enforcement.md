# ADR-0058 — Enforce the branch policy: nothing lands on a protected branch except via PR + gate

**Status:** Accepted
**Spec:** `docs/specs/SPEC-branch-policy.md`
**Relates to:** ADR-0017 (guard + gate pattern), ADR-0021 (branching model), issue #75; #60 is the server-side layer

## Context
The repository practises trunk-based development — feature branch → PR → gated merge
(`merge.sh`) → branch deleted — and `main` has, in fact, received zero direct commits.
But that was habit, not enforcement. The PreToolUse guard denied only the substrings
`git commit`/`git push` *while HEAD was a protected branch*. Every other way of landing
work on a protected branch went through: a push from a feature branch to `main` in any
spelling (`origin main`, `HEAD:main`, `+main`, `refs/heads/main`, `--delete`, `--all`),
`git merge`/`rebase`/`cherry-pick`/`reset --soft` while on `main`, `git branch -D main`,
`git checkout -B main`. And no gate check noticed a direct commit that had already been
made — the platform refused the push only if server-side protection was applied, which
is issue #60 and still the maintainer's call. Governed projects inherited the same gap.

## Decision
The branch policy becomes a declared, enforced borromeanRings capability, at two layers
(the ADR-0017 shape):

1. **Preventive guard.** `pre_bash_guard.sh` hands every command containing `git` to
   `meta_harness.trunk_policy.branch_policy_violation(command, head, protected)` — pure,
   unit-tested per matrix row — and denies with its reason. The parser finds every git
   invocation in a compound line, reads the real subcommand past global options, and
   parses `push` arguments into the refs they write. HEAD is read with a fixed argv.
   **The floor is kept:** while HEAD is protected, any command merely mentioning
   `git commit`/`git push` is still refused, so the parser is never narrower than the
   substring match it replaces (PR #126 was a regression of exactly that shape).
   Fail-open on guard error; server-side protection is the backstop.
2. **Gate backstop.** `08_branch` fails when HEAD is a protected branch carrying commits
   its remote ref lacks (`<upstream|origin/branch>..HEAD`), naming the count and the fix.
   It cannot judge without a remote ref (passes, says so) and skips detached HEAD.

**Configuration** is the existing `[collaboration].protected_branches` — the issue's
proposed `[branching].protected` is folded into it rather than added beside it (one
declaration feeds the naming gate, the guard and the backstop). Empty ⇒ off, opt-in like
`[git]`/`[layout]`. Trunk-based is the default shape (`["main"]`); this repo's
Gitflow-lite (ADR-0021) lists `dev` too — the mechanism protects whatever is declared,
so the model is a *value*, not a code path.

**Server-side enforcement** stays #60: the spec documents the exact `gh api` call
(required `gate` check, `enforce_admins`, no force-push, no deletion) for the maintainer
to run; this change runs nothing against GitHub.

## Alternatives considered
- **Reuse PR #126's `git_invocations` parser** — it is the right seam but not merged into
  this base. `trunk_policy` carries its own (same design: segments, wrappers, `sh -c`,
  global options) plus heredoc skipping and push-refspec parsing; when #126 lands, the
  two tokenizers should be unified in one module (a follow-up, not a blocker).
- **Guard only** (the issue's minimum) — rejected: a commit made outside the agent sits
  on `main` invisibly; the gate backstop is what makes the policy an invariant.
- **Deny every `git push` while on a protected branch and nothing else** — rejected:
  that is the status quo; the pushes that matter come *from* feature branches.
- **A new `[branching]` table** — rejected: two declarations of the same set drift.
- **Wait for #60 alone** — rejected: substrate-neutral, works offline and in governed
  projects on any host; and defense in depth is the point.

## Consequences
- (+) Direct commits/pushes/rewrites of a protected branch are refused in every spelling
  tested (see the matrix), with a fix hint; a direct commit that slips past is caught by
  the gate. Governed projects get both by declaring one field.
- (+) Allowed cases are *proven* allowed (feature pushes, `--force-with-lease` to a
  feature branch, fetch/log/diff, dry-run, tags, heredocs mentioning git).
- (−) The floor keeps the old conservatism: on a protected branch even a `grep` for
  `git push` is refused. Acceptable — you should not be working there.
- (−) `git -C <other repo> …` is judged against the governed repo's HEAD (as before).
- (−) Two shell tokenizers exist until #126 merges (see Alternatives).
