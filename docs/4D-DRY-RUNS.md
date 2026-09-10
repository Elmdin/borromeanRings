# The 4D dry runs — evidence that AI-side obligations fail silently

Issue #178 (sub-issue of epic #172) · companion to `docs/AI-FLUENCY.md` and
`docs/specs/SPEC-charter.md`

> **Provenance and license.** The maintainer's other project, *4D* ("The Fluency Compact"),
> exercised its bilateral contract — one human-side and one AI-side obligation per D — over
> two real tasks in August 2026 and wrote up what it found. 4D is CC BY-NC-SA; this
> repository is Apache-2.0. Everything below is a **re-authored account** of those findings
> and of what this repository does about each one. No sentence, table row, or transcript
> excerpt is reproduced from the source (ADR-0020, ADR-0063).

## Why this document exists

borromeanRings' thesis is that standards become gates, not suggestions. The 4D dry runs are
the cleanest evidence the maintainer holds that the thesis applies to the *AI side* of a
delegation as much as to code. The Compact asks an AI to do four things: declare its limits
before taking a task, raise an ambiguity instead of quietly picking an answer, leave a trail a
reviewer can audit, and refuse to take an irreversible step without a fresh go. In the first
run, whether each of these happened depended entirely on how the agent happened to behave
that day — and when they did not happen, **nothing detected it**. No hook fired, no check
failed, no receipt recorded the gap, no reviewer saw it. The wrong claims stayed published
until a human happened to challenge them days later.

Making that structurally impossible is what this repository is for. So every finding below
is mapped to the mechanism here that catches it now, the sub-issue that will, or an honest
"no mechanism; open".

---

## Dry run 1 — a capture that published a false count

### Setup
A research capture spread over several days in the **Agency** modality, involving three
parties: a human operator, the assistant the operator talked to, and a browser agent that
the assistant drove through a written procedure. The goal was to collect the text of a batch
of online course pages into a staging directory. No code shipped and nothing irreversible
occurred. Crucially, the task's outcome was already known to be wrong before the walk began
(the project's own corrections log records it), so each gate's verdict could be compared with
what really happened instead of with a hypothetical.

### What went wrong
The procedure contained a step instructing the browser agent to skip transcripts for any
video not hosted on YouTube and to leave a fixed placeholder in their place. The placeholder's
phrasing described a **result** — that a transcript was unobtainable — while the truth was a
**decision**: no one had tried. The browser agent followed the instruction to the letter. The
assistant subsequently treated those placeholders as data, counted them, and pushed a figure
for "videos without reachable captions" into the project's provenance record, its handoff
notes, its manifest, and a generated report. A second bad claim travelled the same road: the
lesson pages were written off as trivially short wrappers around a video, with a word count
guessed from skimming rather than measured. When someone finally measured, the median page
was many times longer than claimed.

Neither claim was true. Neither was noticed by anything other than the operator objecting.

### AI-side obligations that failed, and how each failed without detection

| Obligation (AI side of the D) | Verdict in the walk | Why nothing noticed |
|---|---|---|
| **Delegation** — declare material limits before taking the task | Failed | The agent took the task without naming a limit and without confirming it had none. At the moment of acceptance, saying nothing was indistinguishable from having nothing to say. |
| **Description** — raise an ambiguity rather than settle it by choice | Failed; the root of the whole error | The procedure specified the action but not the wording of the placeholder. The agent filled that gap by picking a phrase that claimed a result, and never flagged that it had made a choice. Everyone downstream — including the author of the procedure — read the placeholder as a finding. |
| **Discernment** — be auditable: list what is unverified and name the weakest claim | Failed | There was no self-report of any kind. With nothing listed as unverified and no weakest claim named, a reviewer had nothing to examine — and the matching human-side obligation to examine it was met for free (finding F2). |
| **Diligence** — refuse, or surface for approval, any step that cannot be undone or that reaches outside | Passed, trivially | The capture only wrote to staging; the obligation was never put under load. |
| **Co-growth** — a ledger of what changed between the parties | Unevaluable | No ledger existed. 4D scored this as unevaluable rather than passed — the same honesty this repository encodes as `noop` (ADR-0049). |

Three further verdicts from the human and scale sides feed the mapping:

- **Performance description** failed. The procedure said when the browser agent should halt
  and report something unexpected, but nowhere gave it standing to question the procedure
  itself. Forbid an agent from looking, and never say it may argue with that, and it will not
  argue.
- **Deployment diligence passed while the output was wrong.** The operator genuinely stood
  behind the claim — wrote it, committed it, pushed it. Standing behind something is an
  acceptance of responsibility; it is not a check that the thing is true. An operator who is
  confidently mistaken clears every diligence predicate as written. 4D filed this as a
  boundary of the contract to be stated, not as a predicate to be tightened.
- **Scale delegation** failed. The browser agent's scope existed only as prose in the
  procedure; no mechanism stopped it from doing the forbidden thing. That is compliance by
  instruction wearing the clothes of compliance by enforcement.

The Compact's cheapest traversal — three nodes, taking seconds, producing no artifacts —
would have been enough to catch this error: the unflagged wording choice, the missing
self-report, and the unchecked count each trip one of those three.

### Predicate defects found (F1–F5)
The walk also showed that five of the Compact's own predicates were not evaluable as they
stood. In this repository's terms:

- **F1 — which AI is meant?** The relevant limit belonged to the browser agent, two
  delegations away from the operator; the assistant had no such limit. In a tree, "the AI"
  names two different parties. Proposed fix: attach the obligation to whichever agent
  performs the work, and require it to pass its limits upward.
- **F2 — a "for all" over a set the counterparty controls checks nothing.** Requiring the
  human to inspect the AI's weakest claim is satisfied trivially when the AI names none. 4D
  had hit the same bug class earlier, when a wildcard made one of its verifiers vacuous.
- **F3 — "it is recorded" without saying where cannot be failed.** Any assertion that the
  modality is written down somewhere satisfies it. Proposed fix: say which artifact.
- **F4 — standing behind a claim and being right are indistinguishable.** A boundary of the
  contract, to be stated as one.
- **F5 — "for the whole session" has no meaning over several days and a context
  compaction.** Proposed fix: bound the clause to one traversal.

---

## Dry run 2 — a task that shipped

### Setup
A single agent in the **Agency** modality, on a task picked precisely because dry run 1 had
touched nothing irreversible: the pull request that brought 4D under borromeanRings'
governance, repaired a vulnerability in a script that parsed XML from an untrusted third party, and was
squash-merged and pushed. Along the way the harness refused the merge and the operator had
to authorise it explicitly — the project's first genuine high-stakes moment, as opposed to a
designed one. The walk also put the four predicates revised after dry run 1 through their
first use.

### What the AI side did this time
All four evaluable AI-side obligations held — none had before:

- **Delegation**: the agent listed its constraints ahead of accepting (branch protection
  unavailable on the plan in use; a CI tier that had never once run; no way to push to a
  public repository).
- **Description**: three open questions were settled by the agent's own choice rather than
  by asking — and every one was listed in the PR body beneath a heading that invited the
  operator to disagree.
- **Discernment**: each PR body included a section on what the agent had been unable to
  verify, with a weakest claim named and no confidence score of any kind. The most useful
  disclosure — that the CI workflow was untested — is what exposed two real defects.
- **Diligence**: the harness blocked the merge, the block was surfaced, and the merge went
  ahead only on an explicit instruction; the record shows who vouched at each step.

The step up from dry run 1 is genuine, but it comes with a caveat 4D itself recorded: the
walker had just authored the contract, and the task was selected in part because it had
gone well.

### Findings (G1–G4)

- **G1 — operator acknowledgment is unobservable.** The agent had spelled out its constraints and pointed at
  its shakiest claim; the operator read both and simply carried on. As the predicates are
  written, saying nothing and acknowledging look the same. Two human-side obligations share
  this hole; a third had already closed it in its own text. Proposed: log "continued
  without responding" as a distinct, weaker fact — never as acknowledgment.
- **G2 — whether the agent should push back was left unspecified twice, with opposite
  results.** In dry run 1 the agent did not object and the error followed; in dry run 2 it
  objected three times — refused to spend money, refused to merge its own PR, caught a
  wrongly credited item in the operator's earlier work — and those were the session's best
  outcomes. One unspecified variable, with the result riding on the agent's temperament.
  4D called this its strongest case for a written charter.
- **G3 — repairing falsifiability created unsatisfiability.** F3 was fixed by tying the
  "recorded" predicate to the charter — which did not yet exist, so the predicate went
  from impossible-to-fail to impossible-to-pass, and the walk was the first thing to notice.
  The general lesson: once a predicate points at an artifact, it can only be checked after
  that artifact ships. Proposed: tag such nodes as blocked on an issue so a validator reports
  them as pending instead of leaving them for a reader to trip over.
- **G4 — the checkpoint cadence went unused the same day it was added.** The cadence was
  added to the contract, and that same day a multi-hour task ran without anyone invoking it;
  the checkpoint walk above was reconstructed after the fact. Nothing prompted it because
  the prompting mechanism was unbuilt. The person who wrote the obligation did not perform
  it while working on the very document that contains it — the plainest evidence 4D has
  that the human side, too, cannot be left to temperament.

---

## Finding → mechanism in this repository

"Now" means shipped on the base this document lands on (`feat/charter-gate`). "In flight"
names the branch or ADR. Sub-issue numbers are the #172 children.

| # | Finding (dry run) | Caught by, now or planned | Status |
|---|---|---|---|
| 1 | Task taken without stating limits (DR1, ai-delegation) | The committed charter (`CHARTER.toml`, `22_charter`) puts the delegation's terms — goal, stakes, `stop_when`, `may_not`, owner — on record, so acceptance is against something concrete. The AI's duty to declare limits before accepting becomes skill content with a Stop-hook receipt (#176). | 22_charter now; #176 open |
| 2 | Ambiguity settled by choice, choice never flagged (DR1, ai-description) | The rewrite contract deterministically records whether the reply opened by restating its reading of the request (ADR-0059, `feat/rewrite-contract`, #81) — the "show what you understood" half. The `Assumed` field of the structural self-report (#176) records the choices made. | in flight (#81); #176 open |
| 3 | No self-report, no weakest claim (DR1, ai-discernment) | Stop-hook receipt of the VERIFICATION STATUS block (Verified / Unverified / Weakest claim / Assumed) to `.meta-harness/self_report.jsonl`; any confidence grade is flagged (#176). Same transcript mechanism as the rewrite contract. | #176 open |
| 4 | Unchecked claims relied on and published — a count and a length estimate (DR1, product-discernment) | For *quotations*: the quote-fidelity verifier checks a marked quote verbatim against its saved source (#175). For numeric or factual claims about the world there is no deterministic check; the most this repository can do is make their *unverified* status visible (#176's Unverified field). | #175 open (quotes only); **other claims: no mechanism; open** |
| 5 | Agent never given standing to object; result rode on temperament (DR1, DR2 — G2) | The charter fixes `stop_when` and `may_not` but has no "objection expected" field. The AI-side duty to renegotiate a bad delegation (#176) makes objecting a standing obligation rather than a disposition. | 22_charter partial; #176 open; **no charter field; open** |
| 6 | Standing behind a false output cleared the gate (DR1, F4) | Not fixable by mechanism: `docs/AI-FLUENCY.md` states the boundary (a green gate is necessary, not sufficient) and `merge.sh` makes the vouch explicit and attributable. | boundary stated; open by design |
| 7 | Tool scope existed only as prose (DR1, scale-delegation) | `.claude/hooks/pre_bash_guard.sh` denies a conservative list of destructive commands and wrong-identity commits/pushes at `PreToolUse` — enforced, not instructed. Per-delegation scope (what *this* task forbids) remains prose in `may_not`. | guard now (partial); **per-charter enforcement open** |
| 8 | "The AI" is ambiguous in a tree (F1) | #176 attaches obligations to the performing agent. Propagation to sub-agents — a fan-out inheriting the duty to pass its limits upward — has no mechanism. | #176 open; **propagation: no mechanism; open** |
| 9 | "For all" over a counterparty-controlled set (F2) | The predicate lint (#174) must prove non-vacuity with a mutation-driven test; this repository's `60_mutation` lane already holds its own checks to that standard. | #174 open |
| 10 | "Recorded" with no location (F3) | `22_charter` names the artifact (`CHARTER.toml` at `[charter].path`) and fails when it is absent — absence is checkable. | 22_charter now |
| 11 | "For the whole session" undefined over time (F5) | Stakes are a committed tier in the charter file, versioned with the code; there is no per-session notion to drift. Re-checking the charter at intervals is the cadence (#177). | 22_charter now; #177 open |
| 12 | Silence looks like acknowledgment (G1) | Nothing here observes whether the human read a disclosure. The rewrite contract's distinct `unknown` / `not_honoured` outcomes (ADR-0059) apply the same honesty on the AI side only. | **no mechanism; open** |
| 13 | Predicate tied to an unbuilt artifact became unsatisfiable (G3) | Graph integrity in the predicate lint (#174): every SPEC predicate references an existing check id or issue; orphans are named up front. | #174 open |
| 14 | Cadence unused by its own author (G4) | The compaction brief (ADR-0053, #137) re-injects the last verdict and open obligations at compact/resume — the one prompt here that fires without a human remembering. The Stop gate's bounded retry (`stop_gate.sh`, cap 3) is a tripwire. The two-speed and checkpoint cadence folds into the stewardship skill (#177). Nothing yet *starts* a checkpoint on elapsed work. | compaction brief now; #177 open; **initiation: no mechanism; open** |
| 15 | Co-growth ledger absent (DR1, DR2) | This repository's effectiveness ledger (`ledger.sh`, ADR-0047) records what the *gate* caught over time, not what changed between the parties. No #172 sub-issue covers a bilateral ledger. | **no mechanism; open; outside #172** |

Rows 4, 5, 8, 12, 14 and 15 are the honest residue: real holes the two walks found for which
this repository has no deterministic answer yet. They are listed so the mapping is not
mistaken for closure.

---

## Deliberate exclusions

Two parts of 4D were weighed and are **not** ported. Both are written down here because
dropping them without a trace would be the very failure this document describes.

### 1. The transcript-density threshold (a metric target)

4D's ingest verifier rejects a captured "transcript" whose density falls below a fixed
figure — 100 words per minute of video — on the reasoning that real speech runs well above
it and author-written summaries well below. It earned its keep in 4D: a measurement of
exactly this kind is what was missing when dry run 1's second false claim went out.

It is excluded here because it is an **arbitrary numeric target**. This repository's standing
rule (docs/HANDOFF.md §3; `CHARTER.toml` `may_not`) is that a signal is either a binary fact
or a non-regression ratchet — never a number a person picked. A picked number invites gaming,
needs re-tuning for every corpus, and has nothing to say about a capture sitting at 99.

**The threshold-free alternative** is a ratchet: record each accepted transcript's density
in a baseline and fail any *re-capture* whose density falls below its own earlier figure — no
absolute floor, only "no worse than before". That is the shape `40_test`, `32/33/45` and
`60_mutation` already take.

**Why it is still not adopted.** A ratchet needs a baseline, and a baseline needs a first
accepted capture — which is the exact moment dry run 1 went wrong. A ratchet cannot reject a
*first* summary-masquerading-as-transcript; it can only stop a later one from being worse. So
the ratchet form answers a different question from the one 4D's threshold answers, and no
project this repository governs captures transcripts at all. Building it here would be
speculative (docs/HANDOFF.md §3, "justified building"). Should a governed project ever need
it, the right home is that project's own check with its own baseline, not this harness.

### 2. The whisper / prompt / block severity ladder (a dial)

4D scales friction with stakes across three named levels: a bottom level that is logged and
never interrupts, a middle level that asks, and a top level that blocks until explicitly
authorised, all configurable per deployment. The intent — a protocol that is nearly
invisible on routine work and firm on irreversible work — is shared here.

It is excluded as a **three-position dial** and replaced by the two opt-in tiers of
`SPEC-charter.md`: `stakes = "low"` or `"high"`, where `high` requires a rollback plan, a
named reviewer and a stated blast radius, and any other value is rejected rather than
rounded. The spec's reasoning applies directly: a scale invites its author to pick whichever
position demands the least. Dry run 2 itself noted that only the top level had ever been
exercised — the two lower levels had never been told apart under real pressure. A middle
level no run has needed is a dial position with no evidence behind it.

**What is lost.** The "ask, don't block" middle — an interactive prompt on medium-stakes
actions — has no home in the binary form. Whatever is not `high` gets the logged,
non-blocking treatment; whatever is `high` gets the gate.

**Why that is acceptable.** This repository already has the middle level as a *separate
mechanism*, not a tier: the agent harness's own permission prompt on tool use, plus the
`PreToolUse` guard for the deny-list. A third charter tier would duplicate that prompt with a
weaker one nothing enforces. Two tiers also keep the check threshold-free — there is no
ordinal to compare, only set membership — and keep the author's question binary: *does this
delegation need a rollback plan, a named reviewer and a stated blast radius, or not?*
