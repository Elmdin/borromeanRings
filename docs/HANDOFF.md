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

**Stage 0 — land what is open.** As of 2026-09-05: #129, #123, #122, #124 are CI-clean
and stacked in that order; #125, #126, #127 follow once their bases land. Approvals are
the only thing outstanding.

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
matrices — #79's "must be non-`noop`" idea is the mechanism), #134 (evidence + risk band).

**Stage 5 — research epics, build only on an explicit go.** #140–#146. Each says so in
its body. Spec, then stop and ask.

Remaining M1 items (#58, #59, #66, #60's `enforce_admins`) gate going public and can be
worked at any point.

## 6. Where the truth lives

| Question | Source |
|---|---|
| What does every check enforce? | `docs/CHECKS.md` (generated claims must match the registry — #132 gates this) |
| Why is the code shaped this way? | `docs/adr/` — 50 ADRs; read the one a check cites |
| What is shipped vs planned? | `docs/ROADMAP.md` (Phase 1.5 is what shipped after v0) |
| What is enforced across the six matrices? | `docs/ENFORCEMENT-COVERAGE.md` |
| What was researched and why? | `docs/research/` — video review, tooling survey |
| How is this repo governed? | `borromeanrings.toml` — the policy spine, single source of truth |
| Is it working right now? | `./status.sh` (this project) · `./ledger.sh` (is the gate catching anything) |
| How do I label/prioritise an issue? | `docs/TRIAGE.md` |

The index of all open work is epic **#69**.

## 7. How this session's work should inform yours

Every artifact produced in the last cycle — a feature, docs, issue comments, commit
messages, a fix to a fix — had a real defect found in it by independent review, including
a security guard that a "hardening" change made *weaker* than what it replaced. The
lesson is not that the work was bad; it is that **the review rule and the gate are
load-bearing.** Do not skip them because the change looks small. The small ones were
where the defects were.
