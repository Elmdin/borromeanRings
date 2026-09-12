# Handoff — building borromeanRings autonomously

This is the contract for an agent (or a person) picking up this repository cold. It says
what "done" means here, which rules cannot be bent, in what order to build, and where the
truth lives. Read it before touching anything.

## 1. What this project is, in one paragraph

borromeanRings is a **meta-harness**: a governing quality layer that wraps any AI coding
agent and enforces software-engineering standards as **deterministic, fail-closed gates**
rather than prompt requests. The agent is interchangeable; the gate is the product. It
governs its own repository from commit one, and governs other projects *by reference* —
they point at this code, nothing is copied.

## 2. Definition of done — the gate decides, not the author

A change is done when **all** of the following hold. There is no partial credit.

1. `./verify.sh --heavy` exits 0. The fast gate (`./verify.sh`) is the inner loop; the
   heavy lane (adds mutation, CVE audit, licences, secret history) is the bar CI enforces.
   **Verify with `--heavy` before opening a PR** — three PRs in this repo's history failed
   CI after being reported green on the fast lane alone.
2. The change is on a `feat/`, `fix/`, `docs/` or `test/` branch, merged to `dev` by PR.
3. **A sub coding agent has reviewed the PR and posted its findings as comments on the
   PR** — not into a chat. Findings are addressed or explicitly answered before merge.
   This is a standing rule, not a suggestion.
4. Anything touching `src/` on a `feat/` branch has an ADR under `docs/adr/` (check
   `13_adr` enforces it) and a `CHANGELOG.md` entry (`11_changelog` enforces it).
5. Every new test has been shown to **fail when the behaviour it describes regresses**.
   A test that passes regardless is worse than none — this repo's whole subject is
   vacuous passes, and it has shipped one of its own (see PR #127's review).
6. The issue is closed **with evidence**: name the check, file or ADR that satisfies it.

## 3. Rules that cannot be bent

| Rule | Why | Enforced by |
|---|---|---|
| **Threshold-free.** No arbitrary numeric targets (no "80% coverage"). Signals are binary or non-regression ratchets. | The maintainer rejects number gates outright; they invite gaming and mean nothing. | `40_test`, `32/33/45`, `60_mutation` are ratchets |
| **Agent-only.** Any AI/critic step uses the user's own agent (`claude` CLI). Never independent API keys, never separate token burn. | Cost and trust. | ADR-0030; `[critic].judge_command` |
| **Fail-closed by allowlist.** A status not explicitly known to be non-failing fails. | A negation turns every typo into a silent pass. | `verdict.NON_FAILING_STATUSES` (ADR-0049) |
| **Honest about nothing.** A check that inspected nothing reports `noop`, never `pass`. | A green built on hollow checks is the exact failure this project exists to prevent. | ADR-0049 |
| **Draft before push.** Nothing leaves the machine — push, tag, merge, release — without the maintainer's explicit go. | Their standing instruction. | you |
| **Per-project opt-in.** Global auto-governance is off. A project is governed only if its own `.claude/settings.json` wires the hooks. | Privacy and consent. | ADR-0013 |
| **Justified building.** Nothing past v0 is built until directed, and only when a real project needs it. | `docs/ROADMAP.md` §"How items graduate". | judgement |

## 4. The merge blocker you will hit

`dev` requires **1 approving review**, and GitHub forbids self-approval. If you and the
PR author are the same identity, **you cannot merge.** Do not use `--admin` to bypass
branch protection — that is precisely the gap issue #60 exists to close, and doing it in
a project about fail-closed enforcement would be a contradiction on the record. Open the
PR, get it reviewed, and hand the approval to a human.

## 5. Build order

Work the queue in this order. Each stage's PRs are independent of the next stage's.

**Stage 0 — land what is open.** As of 2026-09-05: #129 and #147 are independent and
CI-clean; #123, #122, #124 are CI-clean and stacked in that order; #125, #126, #127
follow once their bases land. Approvals are the only thing outstanding.

**Stage 1 — the gate learns to look before it builds.** #131 (prior-art & reuse gate).
Its Ruff component is a one-line config change; do that first, resolve every finding
without suppressing any, then the survey-required rule, then jscpd on the heavy lane.
Read `docs/research/AGENT-TOOLING-SURVEY.md` first: it explains why half of this
**cannot** be a gate and must stay advisory.

**Stage 2 — the project can describe itself.** #132 (capability self-description), then
#139 (SWE-state report). Both generate from the registry and spine, never from prose.

**Stage 3 — hygiene the research exposed.** #133 (enhancement catalog audit — it currently
recommends abandonware), #128 (adopt.sh tests), #137 (PreCompact hook).

**Stage 4 — the big features, each spec-first.** #130 (API-usage contracts; needs
`ast-grep` and breaks the Python-only barrier), #79 + #138 (archetypes and the remaining
matrices — the "an archetype declares which checks must be non-`noop`" mechanism described
in #130 and #138 is what makes #79 tractable), #134 (evidence + risk band).

**Stage 5 — research epics, build only on an explicit go.** #140–#146. Each says so in
its body. Spec, then stop and ask.

Remaining M1 items (#58, #59, #66, #60's `enforce_admins`) gate going public and can be
worked at any point.

## 6. Where the truth lives

| Question | Source |
|---|---|
| What does every check enforce? | `docs/CHECKS.md` (generated claims must match the registry — #132 gates this) |
| Why is the code shaped this way? | `docs/adr/` — read the one a check cites (do not trust any count written in prose; `ls docs/adr` is the truth) |
| What is shipped vs planned? | `docs/ROADMAP.md` (Phase 1.5 is what shipped after v0) |
| What is enforced across the six matrices? | `docs/ENFORCEMENT-COVERAGE.md` |
| What was researched and why? | `docs/research/` — video review, tooling survey |
| How is this repo governed? | `borromeanrings.toml` — the policy spine, single source of truth |
| Where is it weak, and what is the evidence? | `docs/SELF-ASSESSMENT.md` — review findings by defect class, gaps ranked fail-closed first, prioritised improvements with tracking issues (#51) |
| Is it working right now? | `./status.sh` (this project) · `./ledger.sh` (is the gate catching anything) |
| How do I label/prioritise an issue? | `docs/TRIAGE.md` (lands with #129) |

The index of all open work is epic **#69**.

## 7. How this session's work should inform yours

Every artifact produced in the last cycle — a feature, docs, issue comments, commit
messages, a fix to a fix — had a real defect found in it by independent review, including
a security guard that a "hardening" change made *weaker* than what it replaced. The
lesson is not that the work was bad; it is that **the review rule and the gate are
load-bearing.** Do not skip them because the change looks small. The small ones were
where the defects were.

## 8. State as of 2026-09-08 (second autonomous session)

**Open, reviewed, waiting on the maintainer's approval** (never `--admin`; merge order is
base-first): #129, #123, #122, #124, #125, #126, #127, #147, #148 (#131 prior-art gate),
#149 (#133 catalog audit), #150 (#128 adopt.sh tests), #151 (#132 self-description),
#152 (#137 compaction brief). Every one has sub-agent review comments and a follow-up
verification comment on the PR.

**In flight in parallel worktrees** (each commits only; the orchestrator pushes, opens the
PR, dispatches review): #130 API-usage contracts (heavy lane rerunning), #134 verdict
evidence/risk band, #135 context-budget ratchet, #138 governance matrices, #61 templates
and label scheme.

**Rules learned this session, each from a real failure:**
- A gate check in a shell chain must be `grep -q "RESULT: PASS"` on the saved log before
  any commit or push. A loose `grep -E "RESULT|FAIL"` matches the FAIL line too and once
  pushed a red commit.
- Anything a test or check loads by path must live under `src/` or `tests/`: mutmut's
  sandbox copies only those, so a repo-root data dir made the whole heavy lane fail
  closed. Rule packs therefore ship inside the package.
- Hook matchers: one settings entry per trigger value; a `a|b` string is only documented
  for tool-name matchers.
- The complexity (10) and coupling (fan-out 2) ratchets bite on every new module: split
  rendering into helpers and reach sibling modules through one seam rather than three.
- The commit-subject limit (72) and the review rule held only when asserted in the
  command, never by intention.

**Progress metric the maintainer asked for:** built = closed issues + issues with a
reviewed PR open, over the 59 deliverable issues in epic #69 (the epic itself excluded).
At this writing: ~41% built, ~20% merged. Report it whenever it moves ~5 points.

## 9. State as of 2026-09-10 (third autonomous session)

**Reviewed, waiting on the maintainer's approval** (merge order base-first, `--squash`, never
`--admin`): #122–#127, #129, #147–#153, #160–#171, #179, #180, #183, #184. Note on #168: its
mutation result was vacuous (see rule 2 below); #182 carries the fix, merge them together.

**In fix rounds:** #181 (predicate lint, license re-authoring verified), #182 (quote verifier,
cross-line false-verbatim fix). **Building:** #176 (structural self-report receipt), the last 4D
sub-issue.

**The 4D merge** (epic #172): the maintainer's local 4D project ("The
Fluency Compact", CC BY-NC-SA) is being folded in as capabilities, re-authored under ADR-0020's
rule. Built: charter gate (#173/#180), predicate lint (#174/#181), quote verifier (#175/#182),
stewardship-as-cadence (#177/#183), dry-run evidence + exclusions (#178/#184); building:
self-report receipt (#176). The license decision is the maintainer's (recorded on #172): default
is re-author; they may relicense their own prose instead.

**Rules learned this session, each from a real failure:**
1. **The license comparison is load-bearing.** Every review of a 4D port reads the source side
   by side. Of five ports, two came back with copied passages (#181: a phrase and a worked
   example; #183: a clause-for-clause paraphrase). Shingle comparison (5- and 6-word, script in
   the scratchpad from the #184 review) is the mechanical check; zero distinctive overlaps is
   the bar. The builder runs it before committing (three of six ports needed a review round
   because they did not); the reviewer runs it again.
2. **A test that reads outside `src/` or `tests/` breaks the mutation lane.** mutmut copies
   only those two dirs; a test reading `.claude/` or `contracts/` fails inside the sandbox,
   mutmut evaluates 0 mutants, and `60_mutation.sh` **fails closed** ("MUTATION CHECK DID NOT
   RUN"), as designed since ADR-0022. Seen on #160 and #168; each was fixed by moving the
   test into the mutmut-ignored integration files, after which the lane ran for real. An
   earlier version of this note called it a vacuous pass; that was wrong, and #187 is
   re-scoped to proving the guard with a regression test and printing the mutant count in
   the gate output.
3. **Four parallel mutation runs starve the fast gate.** The 300 s per-check limit tripped on
   #79's test lane under that load. Run `BORROMEANRINGS_CHECK_TIMEOUT=900 ./verify.sh` when other
   heavy lanes are up; five concurrent agents is the ceiling.
4. **Say "pushed" only after the push.** One verify request went out before the commit landed
   and the reviewer correctly refused to confirm. Poll `git ls-remote` for the sha.

**Progress metric** (built = closed + reviewed-PR-open, over 72 tracked issues): ~74% built,
~20% merged.

## 10. Merge map (2026-09-10) — the order the stacked PRs land

Every open PR is reviewed and awaiting the maintainer's approval. Merge top-down within each
tree, `--squash`, never `--admin`; after each merge the next child's base is retargeted to
`dev` automatically by GitHub (verify with `gh pr view N --json baseRefName`). A PR whose
parent has not merged cannot be merged first.

**Independent of the trunk (base `dev`, any order):** #123, #129, #147 → #195, #149, #161
(needs #147 and #129 first for its citations), #165.

**The trunk — #122 first, then its children in any order, each child's own chain in order:**
- #122 `feat/versioning-and-checks-catalog`
  - #124 → #125 → #126 → #127
  - #148 (#131 prior-art gate)
  - #150 (#128 adopt tests)
  - #151 (#132 self-description) → #171 (#66 README)
  - #152 (#137 compaction brief) → #166 (#136 plugin) → #196 (#142 substrate spec)
  - #152 → #167 (#81 rewrite contract) → #185 (#176 self-report)
  - #152 → #180 (#173 charter) → #183 (#177 cadence), #184 (#178 dry-runs)
  - #153 (#138 matrices)
  - #160 (#130 api contracts) → #198 (#67 TS/Go lanes)
  - #162 (#135 context budget) → #168 (#47 research skill) → #182 (#175 quotes)
  - #163 (#134 verdict evidence)
  - #164 (#154 a11y noop) → #179 (#79 archetypes) → #197 (#139 SWE state)
  - #169 (#75 trunk policy)
  - #170 (#58 supply chain)
  - #181 (#174 predicate lint)

**Known cross-branch touches to expect conflicts on (resolve by keeping both additions):**
`CHANGELOG.md` (every PR adds under Unreleased), `setup.cfg` (mutmut ignore lines),
`borromeanrings.toml` `[checks].required`, `docs/CHECKS.md` rows, `src/meta_harness/adopt.py`
RECOMMENDED, README's describe block (regenerate with `./describe.sh --readme` after #151).

  - #199 (#187 mutation-guard proof + evaluated count on the gate row)
  - #200 (#189 provenance gate)

**Deliberately waiting for the trunk to merge:** #186 (it refactors an idiom every check PR
copies). **Maintainer-side or excluded by the constraints:** #60 (enforce_admins), #64 (wiki
publishing), #68 (second-model critic), #59 (pre-public review).

## 11. Audit: checks that read a crashed tool as a clean pass (2026-09-10)

The single most important finding of the third session. A read-only sweep of every check
script found the pattern in twelve places; #186 is re-scoped to fix the nine on `dev` after
the trunk merges, and the three on open PRs are being fixed on those PRs. Full table:

## Confirmed fail-open sites (script @ branch, lines, fix shape)
1. checks/typescript/50_security.sh @ feat/multi-language L28-53 — ast-grep $tool_code captured, never gates; empty stdout ⇒ pass. Fix: nonzero exit + empty/unparseable output ⇒ fail. (PR #198, in fix round)
2. checks/python/32_complexity.sh @ dev L25-44 — `read -r < <(python…)` no status; empty current ⇒ pass. Fix: temp file + explicit $?; fail closed on empty/non-numeric.
3. checks/python/33_coupling.sh @ dev L24-42 — identical.
4. checks/python/45_docstrings.sh @ dev L25-43 — `current="$(…)"` unchecked; regressed="" ⇒ pass. Fix: check $?; fail closed on empty (go/40_test L60-66 idiom).
5. checks/shared/15_a11y.sh @ dev, @ feat/versioning… — git ls-files returncode ignored. Fixed on fix/a11y-noop (PR #164).
6. checks/shared/12_secrets.sh @ dev L27 — `git ls-files -z … || true` ⇒ empty list ⇒ clean pass. Fix: drop || true, check status, fail closed.
7. checks/shared/06_git_identity.sh @ dev L28-32 — `git log … || true` ⇒ no authors ⇒ pass. Fix: keep code=$?; fail closed when the repo is real and the query failed.
8. checks/ci/74_secret_history.sh @ dev L37-45 — python git() discards returncode; rev-list failure ⇒ "empty history" exit 0. Fix: inspect returncode; distinguish empty repo from git failure.
9. checks/python/34_api_diff.sh @ dev L51-57 — git show returncode unused; every file "new" ⇒ no breaking changes. Fix: continue only on path-not-in-tree; other nonzero ⇒ fail.
10. checks/shared/14_container.sh @ dev L17-31 — config read in $(… 2>/dev/null); crash ⇒ Dockerfile fallback ⇒ "not a container project" pass. Fix: `if ! x="$(…)" || [ -z "$x" ]; then fail` (17_prior_art L45-49 idiom).
11. checks/shared/23_predicates.sh @ feat/predicate-lint L20 — `|| echo False` ⇒ noop on spine crash. Fix: same fail-closed shape. (PR #181)
12. checks/ci/76_lockfile.sh @ feat/supply-chain L20 — `|| true` on config read ⇒ emit_noop. Fix: fail closed when the read errors; noop only for a genuinely empty value. (PR #170)

Low severity (git absence is legitimate): base-resolution `|| true` in 09_commits, 11_changelog, 13_adr, 17_prior_art, 34_api_diff; `find || true` in 07_layout.

## Safe idiom (no finding)
run_check helper (00/10/20/30/50 in every lane); 60_mutation (explicit evaluated=0 fail); 70/72 (empty report ⇒ fail); 40_test in all lanes (code=$? + empty-parse fail); 16_shellcheck; 19_context_budget; 01_source_coherence, 17_prior_art, 18_api_contracts, 21_archetype, 22_charter, 24_quotes, 04_self_description, 78_pins (`borromeanrings_status_for_code "$code"`); go/10_format (&& propagation).

**Receipt-dir rule (from PR #198):** never write a non-receipt file named `*.json` into
`$RECEIPT_DIR`; every `*.json` glob over the run dir treats it as a receipt. Scratch output
takes a non-`.json` suffix. #186 adds the reader-side guard.

## 12. Toolchain determinism (2026-09-10) — why PRs kept going red in CI

**Read this before diagnosing any "green locally, red in CI" report.** It was not the
fast/heavy split, and it was not the PR's diff.

The check toolchain was declared with lower bounds (`ruff>=0.6`, `mypy>=1.10`), so CI's
`pip install -e ".[dev]"` resolved whatever was newest on the runner while this machine
kept whatever the shared conda environment had. **Every tool differed:**

| tool | here | CI |
|---|---|---|
| ruff | 0.15.8 | 0.16.7 |
| mypy | 1.19.1 | 2.3.1 |
| pytest | 9.0.3 | 9.1.1 |
| mutmut | 3.6.0 | 3.7.0 |
| coverage | 7.13.4 | 7.16.0 |

That turned #207 red on `10_format` (0.16.7 reformats what 0.15.8 accepts) and #208 red on
`40_test`. Neither diff was at fault. **Diagnosis order for any future case: compare tool
versions first.** `gh run view <id> --log` prints pip's `Successfully installed` line.

PR #216 (ADR-0077, branch `fix/pin-the-toolchain`, based on `dev`, CI green) fixes it. Three
things in it are worth carrying forward.

**An upper bound at the next major is not sufficient.** #170's `78_pins` rule would have
caught the mypy major jump but not the ruff minor bump, which is the one that broke. A
formatter's output is not a semantically versioned interface. A tool whose *output is the
verdict* needs an exact pin.

**Pin the deciders, not the closure.** The first version pinned all 49 packages via a
`constraints-dev.txt`. CI rejected it: that also froze `click`, `idna`, `msgpack` and
`urllib3` at versions with known CVEs and `70_pip_audit` went red. "Pin everything" and
"keep dependencies patched" are in direct conflict; the tie-breaker is that a pin exists to
stop the release calendar changing a *verdict*. So only the eight check tools plus
`coverage` (measures the ratchet) and `libcst` (generates mutmut's mutants) are pinned.
Note this failure mode is invisible locally: `70_pip_audit` always fails here on unrelated
conda packages, so its signal gets discarded as noise. **CI is the only place that lane
means anything.**

**Observe a tool the way its check invokes it.** The checks disagree — `10_format` runs
`ruff` from `PATH`, `40_test` runs `python3 -m pytest` — and on this machine those resolve
to *different installs of pytest* (a user-site shim at 9.0.2 shadowing site-packages at
9.0.3). A drift check reading `importlib.metadata` would certify a version the gate never
runs. `meta_harness.toolchain.TOOLS` therefore stores an argv per tool. Filed as #214 to
make the invocations uniform.

**CI now prints the log of every check that did not pass** (`.github/workflows/verify.yml`),
marking non-required checks as advisory. Before this, a red CI named the failing check and
nothing else, and every diagnosis cost a full local reproduction. Note `06_git_identity`
fails on this repo's history by design (ADR-0019, local-guard-only for the public repo);
it is outside the required set and the step labels it advisory.

### Two hazards this turned up, both filed, neither fixed
- **#214** — checks reach tools two different ways (`PATH` vs `python3 -m`). Pick one.
- **#215** — a stale untracked copy of `checks/` sits at the repo root as `meta_harness/`,
  29 shell files from 2026-08-15, untracked *and* unignored, already diverged from the real
  `checks/`. Not deleted: not mine to remove and nothing has confirmed it is unreferenced.

### Rules this adds to the builder brief
- **Any new dev dependency is pinned exactly.** A test fails closed on an unpinned one; it
  caught `html5lib>=1.1` arriving from #211 while #216 was open.
- **The receipt directory contains non-receipts.** `70_pip_audit.report.json` shares it.
  Anything iterating that directory must identify a receipt by its `check` field, not by
  the `.json` extension. New code reproduced this known hazard on its first run.
