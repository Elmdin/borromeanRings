# borromeanRings — self-assessment

> **What this is.** The evaluation issue #51 asked for: how the platform works end to end,
> what the evidence of one build cycle says about where it is weak, the gaps in the order the
> platform itself ranks them, and the improvements that follow. Every claim cites a file, an
> ADR or a PR review. Nothing here is a target; the project rejects numeric targets
> (`docs/HANDOFF.md` §3).
>
> **Base note.** Written on the `docs/handoff` base. Some mechanisms cited below ship on
> branches still open for the maintainer's approval (`docs/HANDOFF.md` §9); each such citation
> names its PR. Counts are from this base: `ls checks/shared checks/python checks/ci` gives
> 27 check scripts, `borromeanrings.toml` declares 18 `[checks].required` and 4 `[checks].heavy`.
> `./describe.sh` is absent on this base; `git show origin/feat/self-description:describe.sh`
> is the generator that would print the registry-derived counts once #151 merges (29 scripts
> there, because it adds `04_self_description` and `17_prior_art`).

## 1. How it works

**The gate.** `verify.sh` is the single entry point that humans, CI and hooks call. It runs
every script in `checks/shared/` plus the language set chosen by `[project].language`
(`checks/python/`, ADR-0015), and under `--heavy` also `checks/ci/` (ADR-0033). Each check
writes one receipt; the verdict is computed from receipts, never from a check's exit code
alone (`verify.sh`, the Python heredoc). A required check with no receipt is `MISSING` and
fails the run.

**Receipts and the verdict.** A receipt carries `check`, `command`, `exit_code`, `status`, a
log path and a `content_sha256` over all of it including the log (`src/meta_harness/receipts.py`,
ADR-0026). The verdict re-derives every required receipt's digest and prints `!TAMPERED` on a
mismatch; a run-digest over the intact receipts is the anchor CI can record. ADR-0026 is
explicit that this is tamper-*evidence*, not tamper-proofing. The verdict is persisted to
`.meta-harness/last_verdict.json` and appended to `verdict_history.jsonl`
(`src/meta_harness/verdict.py`, ADR-0046/0047); `ledger.sh` reads the history to answer
"is the gate catching anything" without a score.

**The honest-noop doctrine.** A check that inspected nothing reports `noop`, never `pass`;
the gate prints `inspected NOTHING: N of M`; and non-failing statuses are an explicit
allowlist, `NON_FAILING_STATUSES = {pass, noop}`, so an unknown or forged status fails
(ADR-0049, lands with #122). The doctrine came from a real incident — a governed project
reported 12/12 green while seven checks had scanned a `src/` that did not exist — and
generalises the earlier `12_secrets` rule that "cannot scan" is never "nothing to find"
(ADR-0042). `01_source_coherence` catches the misconfiguration that produced the incident.

**The six hooks.** `.claude/` is an adapter over the substrate-neutral gate (ADR-0013). On
this base four events are wired in `.claude/settings.json`: `UserPromptSubmit`
(`prompt_rewrite.sh`, the spine-driven rewrite directive, ADR-0011), `PreToolUse` on Bash
(`pre_bash_guard.sh`: destructive-command deny-list, bare force-push, protected-branch and
identity guard, ADR-0017/0021), `PostToolUse` on Edit/Write (`post_edit_format.sh`) and
`Stop` (`stop_gate.sh`: runs the gate, retries up to `CAP=3`, then escalates; skips only when
the gated-input hash equals the last proven-green state, ADR-0016). `PreCompact` and
`SessionStart(compact|resume)` are the fifth and sixth (`pre_compact.sh`, `session_start.sh`,
ADR-0053, lands with #152), so the last verdict and open obligations survive compaction.
`docs/HOOK-EVENTS.md` on that branch records, per event, why it is or is not wired. Every
hook is inert outside a directory holding `borromeanrings.toml`.

**Governance by reference.** Nothing is copied into a governed project: `init.sh` writes a
`borromeanrings.toml` and a `.claude/settings.json` whose hooks point back at
`BORROMEANRINGS_HOME`; `adopt.sh` upgrades an already-governed project and seeds ratchet
baselines from its current state (ADR-0013, ADR-0041). Governance is per-project opt-in;
there is no global enforcement (ADR-0013, `docs/HANDOFF.md` §3). The plugin packaging
(ADR-0057, #166) keeps the same six scripts and the same inertness rule.

**Ratchets.** Continuous metrics are non-regression ratchets against a seeded baseline,
never a threshold: coverage (`40_test`), cyclomatic complexity (`32_complexity`, ADR-0031),
fan-out coupling (`33_coupling`, ADR-0038), docstring coverage (`45_docstrings`, ADR-0029)
and mutation score (`60_mutation`, ADR-0022). `src/meta_harness/ratchet.py` is the one
decision primitive. Moving a baseline is a reviewed commit, not a side effect
(`docs/CHECKS.md` on `feat/self-description`, "Notes").

**The two lanes.** The fast lane runs on every Stop and every `./verify.sh`; the heavy lane
(`--heavy`) adds mutation, CVE audit, licence compliance and history secret-scan and is what
CI enforces (ADR-0033, `.github/workflows/verify.yml`). `docs/HANDOFF.md` §2 records that
three PRs went red in CI after a green fast lane — the heavy lane is the bar, the fast lane
is the inner loop.

**The review rule.** Every PR gets a sub coding agent's review posted as comments on the PR,
and each finding is addressed or answered before merge (`docs/HANDOFF.md` §2 item 3). The
same document's §7 states why: every artifact of the previous cycle had a real defect found
this way. §2 below is the record of the cycle that followed.

## 2. What the evidence says

The rows are the sub-agent reviews of this cycle (PRs #148–#184, findings files
`review148.md`…`review184.md` in the session scratchpad, each linked to its PR review URL).
Severity is the reviewer's. "Mechanism" says whether a deterministic check now catches the
class, or whether catching it still depends on review.

| PR | Blockers / should-fixes found | Class | Mechanism now, or review |
|---|---|---|---|
| #148 prior-art gate | should-fix: docstring/ADR/SPEC say "top-level function or class", code reports `Class.method` too. nit: config-read subshell exit code ignored; would noop on a bad config, fail-closed only by an incidental second load | doc overclaim; fail-open path (latent) | review; review (#186) |
| #149 catalog audit | blocker: ADR says four API-key tools were confined, code confined three (Langfuse still recommended for `claude-code`); the test asserted the three, not the fourth. should-fix: unknown `substrate` returned `[]` silently | doc overclaim; vacuous test; fail-open path | review; review; fixed in-PR (`ValueError`) |
| #150 adopt.sh tests | blocker: a placeholder-substitution test that could not fail (the copied files never contain the placeholder) | vacuous test | review; the mutation ratchet cannot see it (integration file, mutmut-ignored) (#187) |
| #151 self-description | should-fix ×2: ADR and SPEC describe frontmatter parsing, advisory-lane detection and a `--readme` flag that were not implemented; README counts hand-edited in the PR meant to generate them | doc overclaim | review; `04_self_description` now guards the counts only (ADR-0052) |
| #152 compaction brief | should-fix: `session_start.sh` lacked the dedupe guard its siblings have (double injection under dual registration). should-fix: a `"compact\|resume"` matcher string never verified against the substrate — the hook could silently never fire | sandbox trap; fail-open path | review (HANDOFF §8 now records the matcher rule); no test can reach the substrate's matcher |
| #153 matrices #2–#6 | none (19 "enforced by" claims verified against scripts) | — | — |
| #160 API-usage contracts | blocker: `paired`/`requires_before` grouped call sites by bare name, so `A.close` was hidden by `B.close` — silent false negatives on the ADR's flagship case. should-fix: nested-def double counting; bare `await f()` not treated as discarded | fail-open path (false negative); false positive; fail-open path | review; the existing test contained the shape but never asserted the count |
| #161 templates & labels | should-fix: three templates link `docs/HANDOFF.md`, present only on an unmerged branch | doc overclaim (dead citation) | review (#188) |
| #162 context-budget ratchet | should-fix: the `hook` source measures only `echo`/`printf` lines; `pre_bash_guard.sh` emits via `deny()` and measured 0 bytes while the SPEC claimed hook messages were covered | doc overclaim | review |
| #163 verdict evidence | nit only (narrow `except OSError` could turn a PASS into a crash, never a FAIL into a PASS) | — | — |
| #164 a11y noop | blocker: `git ls-files` failure or a non-git dir read as "no HTML" → `NOOP` / `RESULT: PASS` over violating HTML — the exact class ADR-0049 set out to close. should-fix: no regression test for that path | fail-open path; vacuous evidence | fixed in-PR by copying the `01_source_coherence` idiom; not shared (#186) |
| #165 rename tail | should-fix: the `DeprecationWarning` never reached stderr in any real call path; docs promised a visible signal. nit: false "config uncommitted" from a stray legacy file | doc overclaim; false positive | fixed in-PR (`FutureWarning`) |
| #166 plugin packaging | should-fix: committed symlinks break on a Windows checkout without `core.symlinks`; undocumented | sandbox trap | review |
| #167 rewrite contract | should-fix: no time bound on the transcript-reading subprocess in the Stop hook. should-fix: `transcript_path` accepted without a boundary check — the tail of any local `.jsonl` could be copied into this project's record | sandbox trap; security bypass | review |
| #168 research skill tokens | should-fix ×2: a skill cited catalog entries that do not exist; an audit cited a research file absent on the branch. Recorded separately: the heavy lane on this PR was vacuous because a test read outside the mutmut sandbox (`docs/HANDOFF.md` §9 rule 2) | doc overclaim (dead citation); sandbox trap → vacuous evidence | review (#188); fixed in #182 by relocating the test, not by a guard (#187) |
| #169 trunk policy | blocker: `git config alias.p push; git p origin main` bypassed the guard entirely. should-fix: `cd ../worktree && git commit` on a protected branch bypassed HEAD resolution. nit: non-shell wrappers bypass any text guard | security bypass ×2 | review; the server-side backstop is #60 |
| #170 supply chain | should-fix: `ENFORCEMENT-COVERAGE.md` said ❌ in the table and ✅ in the summary for the same row | doc overclaim (self-contradiction) | review (#188) |
| #171 README quickstart | none (every verifiable claim verified) | — | — |
| #179 archetypes | should-fix: SPEC calls presence-regex predicates "deterministic" without saying they prove presence, not correctness. should-fix: the #164 fix not carried; merge order could reopen the fail-open path | doc overclaim; fail-open path | review; #186 |
| #180 charter gate | nits ×2: an ADR overstated field-name overlap with the source; a docstring paraphrased the source's sentence | license copy (nit) | review |
| #181 predicate lint | blocker: a phrase and a worked example from a CC BY-NC-SA source reused near-verbatim in four files. should-fix: a "wording only" ADR edit added a new factual claim | license copy; doc overclaim (ADR substance) | review (#189); review |
| #182 quote verifier | blocker: substring match over a whitespace-joined multi-line span read a quote with a dropped "not" as `verbatim`. should-fix ×2: symlinked file or directory under a declared path escapes the project root and its diff is echoed into the log | fail-open path (false negative); security bypass ×2 | review; review |
| #183 stewardship cadence | blocker: a clause-for-clause paraphrase of a source sentence | license copy | review (#189) |
| #184 dry-run evidence | should-fix: `docs/HANDOFF.md` cited twice, absent on the base | doc overclaim (dead citation) | review (#188) |

**Counted by class** (findings, blocker or should-fix, across the 24 reviews; nits excluded
unless noted):

| Class | Findings | PRs | Caught by a mechanism today | Tracking |
|---|---|---|---|---|
| Doc overclaim (docs assert what the branch does not do, or cite what it does not contain) | 13 | 11 | counts only (`04_self_description`); hedges in predicates (`23_predicates`, #181); quotes (`24_quotes`, #182); none for dead paths or behavioural claims | #188 for the deterministic half; the semantic half stays with review and the dormant critic (ADR-0030, #68) |
| Fail-open path (a silent `noop`, an empty result, or a false negative where a fail belonged) | 8 | 7 | the verdict layer only (ADR-0049 allowlist, `01_source_coherence`); inside a check, only where the `01_source_coherence` idiom was hand-copied | #186 |
| Security bypass (guard or boundary defeated) | 5 | 3 | none — `pre_bash_guard.sh` is a text guard by design; branch protection is the backstop | #60; `[quotes]`/transcript boundaries fixed in their PRs' fix rounds |
| License copy (CC BY-NC-SA prose or example reproduced) | 2 (+2 nits) | 2 (+1) | none — a shingle script in the scratchpad, run by hand | #189 |
| Vacuous test or vacuous evidence (a test or a lane that could not fail) | 3 | 3 | `60_mutation` for unit tests of `src/` only; integration tests and the sandbox-collection case are outside it | #187 |
| Sandbox trap (substrate or environment assumption: matcher syntax, symlinks, timeouts, dedupe) | 4 | 4 | dedupe helper exists (`.claude/hooks/_lib.sh`); the rest by review | #137 closed the matcher inventory; the rest unfiled as rules in HANDOFF §8–§9 |
| False positive (a check that fires on correct input) | 1 (+2 nits) | 1 (+1) | none needed beyond review; low cost | — |

Three readings of that table:

1. **The gate is strong where it is deterministic and blind where prose makes a claim.**
   Not one review found a check that turned a real `fail` into `pass` at the verdict layer
   (ADR-0026/0049 hold). The defects were one level down — inside a check's enumeration, or
   in the documents describing the check.
2. **Fail-open paths recur because the fix is copied, not shared.** #164's fix was the
   `01_source_coherence` idiom pasted into `15_a11y`; #179 then nearly lost it at merge
   time; #148 carries the same shape latently. This is the top-ranked gap (§3).
3. **Review is the only mechanism for four of the seven classes.** That is consistent with
   `docs/HANDOFF.md` §7, and it is why the review rule is load-bearing; it is also the case
   for pushing three of those classes into checks (#186, #188, #189), because the platform's
   own law is to enforce each practice at the lowest tier that can express it
   (`docs/ENFORCEMENT-COVERAGE.md` §1).

## 3. Gaps, in the platform's fixed order

The order is the one `docs/ENFORCEMENT-COVERAGE.md` §1 and ADR-0049 impose: a fail-closed
gap outranks a vacuous-evidence risk, which outranks matrix coverage, which outranks
ergonomics.

### 3.1 Fail-closed gaps

| Gap | Evidence | Tracks |
|---|---|---|
| Check-internal enumeration collapses into `noop`: git failure, non-repo, or an ignored subshell exit code each read as "nothing to inspect" unless the script re-implements the guard by hand | #164 blocker, #148 nit, #179 should-fix; the idiom lives in `checks/python/01_source_coherence.sh` and `checks/shared/12_secrets.sh` only | #186 (filed from this document) |
| The protected-branch and identity guard is a text guard, bypassed by a git alias, a `cd` into a worktree, or any non-shell wrapper; the server-side backstop is not applied | #169 blocker + should-fix; `pre_bash_guard.sh` header says "guard, not the policy engine"; `docs/HANDOFF.md` §4 | #60 (and `enforce_admins`, `docs/HANDOFF.md` §5) |
| Detectors with silent false negatives ship with tests that exercise the shape but not the count | #160 blocker (scope leak), #182 blocker (cross-line match) | fixed in their fix rounds; the class is covered by #187's "assert the count" rule only for mutation, otherwise review |
| Hook wiring that the substrate may never fire cannot be tested from inside the repo | #152 matcher finding | rule recorded in `docs/HANDOFF.md` §8; `docs/HOOK-EVENTS.md` (#152) is the inventory; no mechanism possible without driving the substrate — accepted |
| `15_a11y` reports `pass` on no HTML on this base | #154 | #154, fixed by #164 |

### 3.2 Vacuous-evidence risks

| Gap | Evidence | Tracks |
|---|---|---|
| A test that reads outside `src/`/`tests/` fails only inside mutmut's sandbox; `docs/HANDOFF.md` §9 records a PASS with a vacuous count on #160/#168 while `checks/ci/60_mutation.sh` and ADR-0022 say zero evaluated fails closed — the two accounts disagree and nothing pins the sandbox-collection case | HANDOFF §9 rule 2; `setup.cfg` `[mutmut]` ignore list is hand-kept | #187 (filed) |
| Integration tests that drive `verify.sh` are outside the mutation lane entirely, so a structurally vacuous one is invisible to any check | #150 blocker | #187 |
| Docs claim behaviour the code lacks; `55_doc_drift` and `56_critics` are dormant by choice until a judge is wired through the user's own agent | #151, #162, #165, #179; ADR-0030, `borromeanrings.toml` `[critic].judge_command = ""` | #68; `docs/CRITIC-ACTIVATION.md` |
| In-repo paths and links cited in docs do not resolve on the branch | #161, #168, #184, #170 | #188 (filed) |
| Re-authored ports carry copied phrases; the shingle comparison is a scratchpad script | #181, #183 blockers; HANDOFF §9 rule 1 | #189 (filed) |
| Presence-regex predicates (archetype features) can be read as correctness proofs | #179 should-fix | #79/#179 fix round (SPEC caveat) |
| Coverage non-regression row in `docs/ENFORCEMENT-COVERAGE.md` §A says ❌ while `40_test` ratchets coverage and `docs/CHECKS.md` says so | the two documents disagree on this base | unfiled as a separate issue: it is one row of #188's class; fix in the same PR that lands #188 |

### 3.3 Coverage of the matrices

| Gap | Evidence | Tracks |
|---|---|---|
| Matrices #2–#6 are documented with "enforced by" rows verified, but most rows beyond the existing checks are candidates | #153 review verified 19 claims; `docs/matrices/` (lands with #153) | #155 (fuzz/DAST), #156 (batch-size ratchet, deploy record), #157 (SLO/postmortem presence), #158 (PII fixtures, model staleness), #159 (static a11y rules) |
| Archetypes declare which checks must be non-`noop`; only the first catalogue exists | ADR-0062 (#179) | #79 |
| Python only; the check contract is language-neutral but no second set exists | `checks/python/` is the only language directory; ADR-0015 | #67 |
| Supply-chain rows that need CI or a remote service are deferred with exact configs, unapplied | ADR-0061 "Deferred to the maintainer" (#170) | #58 (maintainer items), #74 |
| API-usage contracts cover Python AST only; behavioural or type-aware API breaks are signature-shape only | ADR-0054 (#160); `docs/ENFORCEMENT-COVERAGE.md` §D | #130 (fix round), #140 for the formal end |

### 3.4 Ergonomics

| Gap | Evidence | Tracks |
|---|---|---|
| Parallel heavy lanes starve the fast gate's per-check timeout | `docs/HANDOFF.md` §9 rule 3 (300 s tripped under four mutation runs) | #144 |
| The heavy lane is the bar but the fast lane is what an agent runs by reflex; three PRs went red in CI after a green fast lane | `docs/HANDOFF.md` §2 item 1 | rule only (HANDOFF §2, `CHARTER.toml` `done_when` on #180); no mechanism proposed — a Stop hook cannot run mutation |
| Plugin symlinks break on non-symlink checkouts | #166 should-fix | #136 (fix round) |
| The legacy-config deprecation is visible only from `verify.sh` | #165 | fixed in #165's fix round |
| Self-status reads `MANUAL` for plugin-only governance | ADR-0057 "one honest gap" | #136 |

## 4. Prioritised improvements

At most ten; each cites §2. No dates, no estimates, no targets.

1. **Share the fail-closed enumeration idiom** as one helper every file-listing check
   uses, with adversarial rows for git failure and non-repo per check. Because the same
   fail-open shape appeared in three PRs (#164, #148, #179) and was fixed by copy-paste each
   time. — #186
2. **Make the mutation lane prove it collected the tests it claims** and print the mutant
   count. Because §2 records a heavy lane that passed on vacuous evidence (#160/#168) and a
   vacuous integration test the lane cannot see (#150). — #187
3. **Add a deterministic citation check** for in-repo links and paths in docs. Because dead
   citations are four of the thirteen doc-overclaim findings and need no model to catch. — #188
4. **Commit the shingle comparison as a heavy-lane check** for declared re-authored
   sources. Because two of five 4D ports came back with copied passages (#181, #183) and the
   rule is enforced by memory. — #189
5. **Apply server-side branch protection with `enforce_admins`** so the text guard is a
   convenience, not the enforcement. Because #169 showed a one-line alias defeats the local
   guard, and the platform's own doctrine is that a local aid needs a backstop
   (`pre_bash_guard.sh` header). — #60
6. **Assert the count, not just the shape, in detector tests.** Because #160's existing test
   contained the exact nesting that double-counted and passed anyway; #182's single-line test
   passed while the multi-line case failed. Record it as a `docs/HANDOFF.md` §2 rule and a
   review-checklist line in `.github/PULL_REQUEST_TEMPLATE.md` (#161). — #161 fix round
7. **Wire the doc-drift critic through the user's own agent on the heavy lane**, advisory
   first. Because the semantic half of the doc-overclaim class (#151, #162, #179) is the one
   class no deterministic check can reach, and the seam already exists dormant
   (ADR-0030). — #68
8. **Land the archetype non-`noop` clause on every governed project** so a hollow green is
   red by declaration. Because ADR-0049's incident and #164 both show `noop` reads as green
   unless something says which checks must not be `noop`. — #79
9. **Reconcile the two coverage documents** (`ENFORCEMENT-COVERAGE.md` §A vs `CHECKS.md` on
   the coverage row; the ❌/✅ contradiction #170 found) in the PR that lands #188, and let
   that check keep them honest. — #188
10. **Bound every subprocess a hook starts** with the same `borromeanrings_bounded` wrapper
    the gate uses. Because #167 found an unbounded transcript read in the Stop hook, and a
    stalled Stop hook is a governance outage the user cannot see. — #81 fix round

## 5. Constraints honoured

| Rule | Where it is enforced or recorded |
|---|---|
| **No API keys, no independent model calls, no token spend outside the user's agent** | ADR-0030 (critic must run through the user's own `claude`); `borromeanrings.toml` `[critic].judge_command = ""` (dormant by default); `docs/research/AGENT-TOOLING-SURVEY.md` §0 (on `feat/prior-art-gate`) records this as the constraint that disqualified most of the tooling ecosystem; `docs/HANDOFF.md` §3 "Agent-only"; `CHARTER.toml` `may_not` and `stop_when` (lands with #180) |
| **No publishing, no push, no merge, no release without the maintainer's go** | `docs/HANDOFF.md` §3 "Draft before push" and §4 (never `--admin`); ADR-0007 (merge only on explicit invocation and a green gate); ADR-0057 §5: the marketplace file is a file in this repo, not a submission to any catalogue; ADR-0061 "Deferred to the maintainer": Dependabot, SLSA and pinned-Actions configs are written into the ADR, not applied |
| **No CI growth, no packaging pipeline** | ADR-0061 Context (the maintainer's constraint verbatim); #170's review confirmed `.github/workflows/` untouched; ADR-0013 defers pip packaging |
| **Threshold-free** | `docs/HANDOFF.md` §3 "Threshold-free"; `src/meta_harness/ratchet.py` (non-regression only); ADR-0022 (mutation is a ratchet, not a score); #153's review grepped the matrices for numeric targets and found none; `CHARTER.toml` `may_not` "introduce an arbitrary numeric quality target" (#180) |
| **Local guard on destructive and identity-breaking commands** | `.claude/hooks/pre_bash_guard.sh`: `rm -rf /`, fork bomb, `git reset --hard`, `DROP TABLE`, bare force-push, commit/push on a protected branch, wrong identity (ADR-0017/0019/0021); the guard is defence in depth, `06_git_identity` and #60 are the backstops |
| **Re-author, never copy, CC BY-NC-SA material** | ADR-0020; epic #172; `docs/HANDOFF.md` §9 rule 1; `CHARTER.toml` `stop_when` (#180); mechanism proposed in #189 |
| **Per-project opt-in; hooks inert elsewhere** | ADR-0013; every hook opens with `[ -f "$PROJECT_DIR/borromeanrings.toml" ] || exit 0`; #166's review verified all six |
| **Never touch user-level configuration from a task worktree** | `docs/HANDOFF.md` §3; `CHARTER.toml` `may_not` (#180); #150's review diffed `~/.claude/settings.json` before and after the suite to prove it |

This document was produced under the same rules: docs-only branch, read-only `gh` calls
against this repository, four issues filed (#186–#189), nothing pushed.
