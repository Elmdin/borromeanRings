# SPEC — Collaboration governance (branching, review, commits, skills, distribution)

> Status: **approved** (Maintainer delegated review-and-continue, 2026-07; increment 0 —
> the `dev` branch, its protection, and default-branch switch — is live). See ADR-0021.
> Umbrella spec: each increment lands as its own gated PR into `dev`.

## 1. Purpose
borromeanRings gates *code quality*; this extends it to gate *how people and agents
collaborate*: branching, commit hygiene, review policy, skill quality, and distribution.
Same thesis as everywhere else in this repo — collaboration standards become **declared,
deterministic gates**, not conventions in a doc nobody enforces.

## 2. Branching model — Gitflow-lite (ADR-0021, live)
- `main` — stable/release. Nothing lands except via PR from `dev` (or `hotfix/*`).
- `dev` — integration, the **default branch**. All feature work targets it.
- `feature/*`, `fix/*`, `docs/*`, `chore/*` — short-lived branches off `dev`;
  `hotfix/*` may branch off and target `main`.
- Squash merges; linear history and the `gate` status check required on **both**
  `main` and `dev` (protection is declared-and-applied, verified in Tier B).
- CI runs on every PR and on pushes to `main` **and `dev`** (workflow updated in this PR).

**Review policy (declared now, enforced in Tier B):** the Maintainer may self-review and
merge their own PRs at current team size; **external contributors' PRs require Maintainer
review**. When the team grows, flip to required cross-review by raising the declared
`required_approving_review_count` — a config change, not a process rewrite.

## 3. Three enforcement tiers
- **Tier A — local, deterministic (this spec's implementation scope).** New checks +
  a guard hook, config-driven via a `[collaboration]` table in `borromeanrings.toml`
  (opt-in like `[layout]`; absent ⇒ off; fail-closed once declared).
- **Tier B — platform reconciler (declare + apply + verify-drift).** GitHub-side policy
  (branch protection, default branch, review requirements) is *declared* in the spine;
  an apply script sets it and a check detects drift between declared and live settings.
  Deferred to a later increment.
- **Tier C — advisory + Stewardship.** Mechanize the Stewardship tripwires
  (`skills/ai-fluency-stewardship`): retry-loop detection, orphaned-process detection
  (PR #82 fixed the leak; Tier C adds *monitoring*), N-steps-without-artifact. Plus
  prompt-rewrite compliance verification (issue #81). Deferred.

## 4. Tier A contract (increment 1)
| Piece | Contract |
|---|---|
| `08_branch` (shared check) | Fail if the current branch matches none of the declared `branch_patterns` (default: `feat/*, feature/*, fix/*, docs/*, chore/*, refactor/*, perf/*, test/*, ci/*, hotfix/*` — `feat/*` included because it is this repo's own convention). **Skips** on the declared protected branches (`main`, `dev`) — CI runs there post-merge — and in detached-HEAD CI states. |
| `09_commits` (shared check) | Fail if any commit on `base..HEAD` (base = merge-base with `dev`, falling back to `main`) violates Conventional Commits (`type(scope)?: subject`, declared `commit_types`, subject length bound). Merge commits exempt. |
| Protected-branch guard (extends `pre_bash_guard.sh`) | Deny any command that would land work on a protected branch — commit/merge/rebase while on one, a push to one in any spelling, a local delete/force-move — with `08_branch` failing a protected branch that is ahead of its remote as the backstop. Full matrix in SPEC-branch-policy.md (ADR-0058). Lives in the existing PreToolUse hook — same event and matcher, no new registration surface. |
| `[collaboration]` config | `protected_branches = ["main", "dev"]`, `branch_patterns = [...]`, `commit_types = ["feat","fix","refactor","docs","test","chore","perf","ci"]`, `subject_max_length = 72`. Empty/absent table ⇒ checks skip (undeclared projects unaffected). |
Logic lives in `meta_harness.collaboration` (pure functions: `branch_violation()`,
`commit_violations()`), unit-tested to the coverage baseline; checks stay thin adapters.

## 5. Adopted from the agent-skills evaluation (folded per Maintainer decision)
1. **Anti-rationalization + Red Flags + Verification** (increment 2): add to `AGENTS.md`
   and each `skills/*/SKILL.md` a short section listing (a) the rationalizations an agent
   uses to bypass the discipline ("the gate is slow", "this change is trivial"), (b) red
   flags that it is drifting, (c) how to verify compliance. Pure docs; template defined
   once and reused.
2. **`11_skill_anatomy` gate check** (increment 3): deterministic validator for every
   `skills/*/SKILL.md` — YAML frontmatter present with `name` + non-empty `description`;
   `name` matches its directory; required sections present; length bounds; **exemptions
   owned by the validator config, not by the skill being validated** (a skill cannot
   self-exempt). → own ADR.
3. **Package for distribution** (increment 4): `plugin.json` + marketplace metadata +
   a getting-started doc so borromeanRings installs as a plugin, not just via
   `install-global.sh`.
4. **Prove harness-agnostic** (increment 5): a second thin adapter (candidate substrate
   chosen at increment time) implementing the same enforcement seams (prompt directive,
   pre-command guard, stop gate) + an **adapter-contract ADR** defining exactly what a
   substrate must provide. → own ADR.

## 6. Increments & done-criteria
| # | Increment | Done when |
|---|---|---|
| 0 | Gitflow infra (**live**) | `dev` exists, protected like `main`, default branch; CI push-trigger includes `dev` |
| 1 | Tier A checks + guard + `[collaboration]` | Checks in required set; borromeanRings's own branches/commits pass; unit tests at baseline; gate green |
| 2 | Anti-rationalization sections | `AGENTS.md` + all skills carry the template; `11_skill_anatomy` (when it lands) asserts presence |
| 3 | `11_skill_anatomy` | In required set; all existing skills pass; ADR recorded |
| 4 | Distribution packaging | Plugin installable from a clean machine; getting-started verified |
| 5 | Second adapter + adapter contract | Same gate verdict produced under the second substrate on a sample project; ADR recorded |
| — | Tier B reconciler, Tier C stewardship monitors | Specced separately when reached (Lean: not before) |

Each increment: its own `feature/*` branch → PR into `dev` → gate green → Maintainer
merge. `dev → main` promotions are explicit Maintainer decisions. No increment starts
implementation before this spec is approved (increment 0 was pre-agreed infra).

## 7. Out of scope
Issue/PR *content* quality judgment (advisory only, Tier C); multi-maintainer org
policy (revisit at growth); the frontier-tracking pipeline (issue #80) and app-type
capability profiles (issue #79) — separate efforts that consume this governance.
