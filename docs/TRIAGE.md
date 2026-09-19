# Issue triage

How an issue gets labelled, prioritised, milestoned, and when it earns an ADR.
Written down because triage decisions made silently are re-litigated later.

## 1. Is it borromeanRings at all?

borromeanRings is the **meta-harness**: the governing quality layer. Products built
*with* it (the Deep Research tool, the notes/Kernel) are separate repos. An issue about
one of those gets **`separate-product`** and is closed here.

## 2. Type — what kind of work is it?

Exactly one, usually:

| Label | Use for |
|---|---|
| `harness-feature` | A new borromeanRings capability (usually a new check or command) |
| `quality` | Engineering rigor on what exists: tests, lint, verification |
| `security` | Hardening, or a vulnerability in the harness itself |
| `efficiency` | Token/compute cost reduction that does not cost output quality |
| `research` | Investigation and prior-art synthesis, producing a decision |
| `evaluation` | Assessing how the platform works and what to improve |
| `documentation` | Docs, specs, contributor material |
| `repo-setup` | GitHub settings, repo hygiene, scaffolding |
| `deep-research` | The research *enhancement* (a harness feature, not the product) |
| `bug` | Something that does not do what it says it does |
| `epic` | A tracking issue spanning several work items — add alongside a type |

## 3. Priority — what happens if it waits?

| Label | Means |
|---|---|
| `priority:high` | Blocks a milestone, or leaves a gate that can be trusted when it should not be |
| `priority:med` | Real value, no one is blocked |
| `priority:low` | Worth doing, nothing breaks if it never happens |

A **hollow guarantee is always `priority:high`** — a check that passes without
inspecting anything, a doc claiming a gate that does not exist, an enforcement setting
that is off while the docs say it is on. Those are worse than a missing feature,
because someone is relying on them.

## 4. Milestone — which question does it answer?

| Milestone | Question |
|---|---|
| **M1 Pre-public hardening** | Is this safe and presentable to strangers? |
| **M2 Platform evaluation & quality** | Does the platform actually do what it claims? |
| **M3 Research & efficiency** | Can it do the same for less? |
| **M4 Docs & community** | Can someone else contribute to it? |

Leave the milestone empty rather than guessing. An unmilestoned issue is visible in
triage; a wrongly-milestoned one hides inside a milestone that then never completes.

## 5. When does it need an ADR?

Check `13_adr` enforces this mechanically: on a `feat/` branch, a change touching `src`
must add or modify an ADR under `docs/adr/`. The judgement call is what counts as
load-bearing:

**Write an ADR when** the change adds or removes a gate; changes what the gate treats
as pass or fail; changes the trust model (what is enforced preventively vs. as a
backstop); or picks between real alternatives where the rejected one was defensible.

**Do not** write one for a bug fix that restores intended behaviour, a test, or a
docs change — the commit message carries that.

An ADR records **why**, including what was rejected. An ADR that only restates what the
code does has not earned its number.

## 6. Closing an issue

Close with **evidence**, not assertion: name the check, file, or ADR that satisfies it,
so a reader in six months can verify the claim without re-deriving it.

If the work landed earlier and the issue was simply never closed, say so — several
issues in this repo were open for months against shipped work, which made the backlog
overstate what remained. Where only part is done, **narrow the issue** rather than
closing it: leave the residue explicit.

## 7. Related

- [`CONTRIBUTING.md`](../.github/CONTRIBUTING.md) — how to make a change that passes the gate
- [`CODE_OF_CONDUCT.md`](../.github/CODE_OF_CONDUCT.md) — how we talk to each other while doing it
- [`CHECKS.md`](CHECKS.md) — every check, what it enforces, and its ADR
- [`ROADMAP.md`](ROADMAP.md) — what is shipped and what is planned
