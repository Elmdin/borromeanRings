# ADR-0009 — Command-orchestrated auto-merge (free private repo)

**Status:** Accepted

## Context
Phase 1 wanted GitHub-native auto-merge: `gh pr merge --auto` merges a PR once its **required
status checks** pass. That needs server-side branch protection / rulesets requiring the CI `gate`
check. On the current repo (private, free GitHub plan) **both classic branch protection and rulesets
are unavailable** — the API returns *"Upgrade to GitHub Pro or make this repository public."* So
GitHub cannot enforce the gate server-side here, and native `--auto` has no required check to wait on.

## Decision
borromeanRings orchestrates the gating **itself**, from its own merge command: `./merge.sh --auto` runs
the local gate, then **waits for the PR's CI checks to pass** (`gh pr checks --watch --fail-fast`),
then merges. The same `verify.sh` runs both locally and in CI (ADR-0008), so the verdict is
consistent. This delivers "merge automatically once everything passes" without a paid plan, and fits
borromeanRings's nature as a **local-first orchestrator** (the harness does the waiting, not GitHub).

The invariant from ADR-0007 still holds: a merge happens only when explicitly invoked **and** the
gate is green. `--auto` is still per-merge and explicit — there is no standing, unattended mode.

## Alternatives considered
- **Upgrade to GitHub Pro/Team** — enables branch protection/rulesets + native `gh pr merge --auto`
  (server-enforced). Rejected for now: costs money; the user's call, left open as a future option.
- **Make the repo public** — enables protection/rulesets for free. Rejected: the repo is deliberately
  private.
- **Native `--auto` without a required check** — rejected: with nothing required, GitHub would merge
  immediately, defeating the "wait for CI" intent.

## Consequences
- (+) Delivers gated auto-merge on a free private repo, today; CI still runs as independent evidence.
- (+) Consistent with ADR-0007/0008 — same gate, explicit per-merge request.
- (−) The enforcement is **client-side** (the command), not server-side: a determined human could
  still merge via the GitHub UI bypassing the gate. Server-side enforcement requires the paid/public
  option above. Surfaced here rather than hidden.
