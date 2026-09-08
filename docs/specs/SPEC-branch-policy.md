# SPEC — Branch policy: nothing lands on a protected branch except via PR + gate

> Status: **implemented** (ADR-0058, issue #75). Composes with SPEC-collaboration.md
> (naming/commit rules), SPEC-merge.md (the gated merge) and SPEC-git-identity.md (the
> same two-layer guard + gate pattern, ADR-0017).

## 1. Problem
borromeanRings *practises* trunk-based development — short-lived branch → PR → gated
merge → branch deleted — but nothing *enforced* it. The PreToolUse guard denied
`git commit`/`git push` only while HEAD was a protected branch, by substring, so every
other way of landing work on `main` went through: `git push origin HEAD:main` from a
feature branch, `git push origin +main`, `git push --delete origin main`, `git merge
feat/x` while on `main`, `git branch -D main`. And there was no gate backstop: a commit
made outside the guard sat on `main` unnoticed until the platform refused the push (or
did not, because server-side protection is #60 and not yet applied).

## 2. Policy (declared, not assumed)
```toml
[collaboration]
protected_branches = ["main"]          # trunk-based: just the trunk
# protected_branches = ["main", "dev"] # Gitflow-lite (ADR-0021): both integration branches
```
Empty/absent ⇒ **off** (opt-in, like `[git]`/`[layout]`). The issue proposed a new
`[branching].protected` table; it is folded into the existing field — one declaration,
read by the naming gate, the guard and the backstop alike (Single Choice). Governed
projects declare it in their own `borromeanrings.toml`; the guard and check read the
*governed* project's config, so reference mode works unchanged.

The **model** is trunk-based by default (`["main"]`): a project that keeps a `dev`
integration branch (this repo, ADR-0021) simply lists it too — the mechanism protects
whatever is declared.

## 3. Enforcement — two layers (defense in depth)

### 3.1 Preventive guard (`PreToolUse` on Bash, `.claude/hooks/pre_bash_guard.sh`)
Any command containing `git` is handed to `meta_harness.trunk_policy.branch_policy_violation`
with the current HEAD (read with a fixed argv: `git -C <project> rev-parse --abbrev-ref HEAD`)
and the declared protected branches. A non-empty reason ⇒ **deny** with that reason.
Fail-open on any error (python missing, unreadable spine): server-side protection is
the backstop.

The parser: splits the command into logical lines (backslash continuations joined,
heredoc bodies skipped), tokenizes each with shell operators as separators, steps over
`VAR=value` prefixes and wrapper words (`env`, `sudo`, `exec`, …), looks inside
`sh -c '…'`, and reads git's real subcommand past its global options (`-C`, `-c`, …).
`git push` arguments are parsed into the refs they write (`PushSpec`).

**The floor.** While HEAD *is* a protected branch, any command that merely contains the
substring `git commit` or `git push` is still refused — exactly what the previous guard
did. A narrower parser must never let through what the old match caught (PR #126 was a
real regression of that shape); precision is added on top, never traded for coverage.

### 3.2 Gate backstop (`checks/shared/08_branch.sh`)
When HEAD is a protected branch and it carries commits its remote ref lacks
(`git rev-list --count <upstream|origin/branch>..HEAD` > 0), the check **fails**:

```
DIRECT COMMITS ON PROTECTED BRANCH: 'main' has 2 commit(s) not on origin/main — work
lands on protected branches only via PR + gate (trunk-based policy, ADR-0058). Move
them: git switch -c feat/<name> && git branch -f main origin/main.
```

No remote ref to compare (no `origin`, no upstream) ⇒ cannot judge ⇒ pass, logged as
such. Detached HEAD ⇒ not judged (PR CI). The naming rule (`branch_patterns`) is
unchanged; the check now runs when *either* field is declared.

### 3.3 How it composes with the gated merge
`merge.sh` is the sanctioned path onto a protected branch. Via `gh pr merge` the merge
happens server-side (the guard never sees a local write to `main`). Its no-`gh`
fallback (`git checkout main && git merge --no-ff … && git push origin main`) runs
*inside* the script, so a `./merge.sh` invocation is not parsed as a push to `main` —
the gate has already passed by then, which is the point of the script.

## 4. Command matrix (guard layer)
HEAD column: **P** = on a protected branch, **F** = on a feature branch.
Every row is a test in `tests/unit/test_trunk_policy.py` (exact reason) and
`tests/integration/test_hook_trunk_policy.py` (real hook, stdin protocol).

| Command | HEAD | Verdict | Why |
|---|---|---|---|
| `git commit -m x`, `git commit --amend` | P | **deny** | lands a commit directly on the protected branch |
| `git -c user.email=… commit`, `git -C . commit`, `GIT_AUTHOR_EMAIL=… git commit`, `cd d && git commit`, `bash -c 'git commit'` | P | **deny** | same commit, exotic spelling — parser finds the real subcommand |
| `git merge X`, `git rebase X`, `git cherry-pick X`, `git revert X`, `git am` | P | **deny** | creates/moves commits on the protected branch |
| `git reset --hard/--soft/--mixed/--merge/--keep` | P | **deny** | moves the protected branch pointer (`--hard` is also refused globally, on every branch) |
| `git reset`, `git reset -- path` | P | allow | unstaging only; no pointer moves |
| `git pull origin feat/x` | P | **deny** | merges an arbitrary ref into the protected branch |
| `git pull`, `git pull origin`, `git pull --rebase origin main` | P | allow | syncs the protected branch with itself |
| `git push` (implicit), `git push -u origin HEAD` | P | **deny** | pushes the protected branch |
| `git push origin feat/x`, `echo 'git commit' > f` | P | **deny (floor)** | any `git push`/`git commit` mention while ON a protected branch — the old guard's coverage, kept |
| all of the above | F | allow | work belongs on feature branches |
| `git push origin main`, `git push -u origin main`, `git push origin main feat/x`, `git push origin dev` | any | **deny** | destination is a protected ref |
| `git push origin HEAD:main`, `feat/x:main`, `feat/x:refs/heads/main`, `refs/heads/main`, `'refs/heads/*:refs/heads/*'` | any | **deny** | refspec destination resolves to a protected ref (globs matched) |
| `git push origin +main`, `--force-with-lease origin main`, `--force-with-lease=main:abc …`, `--force-if-includes` | any | **deny** | force-updates a protected ref (bare `--force`/`-f` is refused globally first) |
| `git push --delete origin main`, `git push origin :main`, `git push -d origin main` | any | **deny** | deletes a protected ref |
| `git push --all origin`, `git push --mirror origin` | any | **deny** | pushes every branch, protected ones included |
| `git -C . push origin main`, `cd d && git push origin main`, `bash -c 'git push origin main'`, `git fetch && git push origin main` | any | **deny** | same push, found anywhere in the line |
| `git push origin feat/x`, `-u origin feat/x`, `--force-with-lease origin feat/x`, `origin HEAD:refs/heads/feat/x`, `-o ci.skip origin feat/x` | F | allow | feature ref |
| `git push origin feat/main`, `git push origin main-2` | F | allow | not a protected *name* (exact match, not substring) |
| `git push --tags origin`, `git push origin v1:refs/tags/v1` | F | allow | tags are not branches |
| `git push --dry-run origin main`, `git push -n origin main` | F | allow | writes nothing |
| `git branch -D/-d/--delete main`, `git branch -f main X`, `git branch -M main`, `git branch -m feat/x main` | any | **deny** | deletes or force-moves a protected branch locally |
| `git checkout -B main`, `git switch -C main`, `git switch --force-create main` | any | **deny** | resets a protected branch to HEAD |
| `git update-ref refs/heads/main X` | any | **deny** | plumbing rewrite of a protected ref |
| `git branch -D feat/old`, `git branch feat/new`, `git branch -c main copy`, `git checkout -b feat/y`, `git checkout -B feat/y`, `git switch -c feat/y` | any | allow | feature refs / read-only copies |
| `git checkout main`, `git switch main` | any | allow | switching *to* a protected branch is fine; committing there is then refused |
| `git fetch`, `git fetch origin main`, `git log main`, `git diff main...HEAD`, `git show main:f`, `git status`, `git rev-parse …`, `git stash`, `git tag v1` | any | allow | read-only / not a branch write |
| `grep -r 'git push --force' docs/`, `cat > f <<'EOF' … git push origin main … EOF` | F | allow | a mention is not an invocation (heredoc bodies skipped) |
| same two | P | **deny (floor)** | see the floor rule |
| anything | detached HEAD | allow (push rows still apply) | no branch to protect |
| anything | `protected_branches = []` | allow | policy off (opt-in) |

Known conservative edge: `git -C /elsewhere commit` is judged against the *governed*
project's HEAD (the fixed-argv read), so it can be refused while the governed repo sits
on `main` even though the other repo does not — the same trade the previous guard made.

## 5. Server-side enforcement (#60) — the maintainer's call
The local layers are aids; the platform is the backstop. This spec **documents** the
GitHub command and does not run it (branch protection is issue #60 and a maintainer
decision). For a repo `OWNER/REPO` and protected branch `main`, requiring the gate
status check, linear history, and forbidding force pushes and deletion:

```sh
gh api -X PUT "repos/OWNER/REPO/branches/main/protection" \
  -H "Accept: application/vnd.github+json" \
  --input - <<'JSON'
{
  "required_status_checks": { "strict": true, "contexts": ["gate"] },
  "enforce_admins": true,
  "required_pull_request_reviews": { "required_approving_review_count": 1 },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
```

Repeat for every declared protected branch (`dev` under Gitflow-lite). Verify with
`gh api repos/OWNER/REPO/branches/main/protection`. `enforce_admins: true` is what
closes the `--admin` bypass the HANDOFF forbids; drift between this declaration and the
live setting is the Tier B reconciler (SPEC-collaboration.md §3), not built here.

## 6. Verification
- `tests/unit/test_trunk_policy.py` — every matrix row with its exact reason; parser
  seams (`git_invocations`, `git_subcommand`, `push_spec`); 100% line + branch.
- `tests/integration/test_hook_trunk_policy.py` — every row through the real hook, both
  HEAD states; allowed rows must yield **no** decision.
- `tests/integration/test_gate_trunk_policy.py` — `08_branch` against a real repo with a
  bare origin: in-sync passes, 2 direct commits fail with the exact message, feature
  branch ahead passes, naming rule intact, no remote ⇒ cannot judge, upstream preferred
  over `origin/<branch>`, undeclared ⇒ off.

## 7. Out of scope
Server-side application (#60); the Tier B drift reconciler; `git -C <other repo>`
HEAD resolution; policies on tags.
