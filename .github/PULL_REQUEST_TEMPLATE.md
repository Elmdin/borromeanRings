<!-- borromeanRings governs itself: a change is not done until the gate says so.
     Definition of done: docs/HANDOFF.md §2. Contribution rules: .github/CONTRIBUTING.md. -->

Closes #

## What & why

<!-- What changes, and why. Link the spec (docs/specs/) or ADR (docs/adr/) if there is one. -->

## Tests

<!-- What was added or changed, and how you showed each new test FAILS when the behaviour
     it describes regresses. A test that passes regardless is worse than none. -->

## Verification

- [ ] `./verify.sh` prints `RESULT: PASS` locally (fast gate)
- [ ] `./verify.sh --heavy` run, and `60_mutation` and `74_secret_history` both PASS — CI runs the heavy lane; fast-green alone has failed CI before
- [ ] No check or hook was weakened, disabled, or bypassed to get there
- [ ] A sub coding agent reviewed this PR and posted its findings **as comments on the PR**; every finding is addressed or explicitly answered
- [ ] If this fixes a defect: the regression test/check was added **before** the fix
- [ ] If this touches `src/` on a `feat/` branch: an ADR under `docs/adr/` (`13_adr`) and a `CHANGELOG.md` entry under `## [Unreleased]` (`11_changelog`)
- [ ] If this touches 3+ files: a spec under `docs/specs/` was written first
- [ ] No new CI workflows or packaging changes (or: they are called out below and were asked for)
- [ ] Every commit subject is ≤ 72 chars with a conventional prefix (`09_commits`)

<details>
<summary>verify.sh --heavy output</summary>

```
(paste the gate output here — the RESULT line and the heavy checks at minimum)
```

</details>

## Notes for reviewers

<!-- Trade-offs, follow-ups, deferred decisions, anything non-obvious. -->
