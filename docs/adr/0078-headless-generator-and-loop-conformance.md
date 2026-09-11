# ADR-0078 — The headless generator: one decision, two thin drivers, and provenance in the verdict

**Status:** Accepted · 2026-09-10 · issue #202 (build phase of #143) ·
**Spec:** `docs/specs/SPEC-generator.md` (§2, §3.2, §5) ·
**Implements:** ADR-0071 decisions 3 and 4 · **Builds on:** ADR-0049 (self-report is not
evidence), ADR-0026 (tamper-evident receipts), ADR-0056 (`intent`)

## Context

ADR-0071 specified the generator seam and built nothing. The loop it describes —
generate → gate → retry → escalate — existed only as a property of one shell script:
`.claude/hooks/stop_gate.sh` held the cap as a literal, expressed the retry request as a
stderr string, learned "a change is ready" from a Stop event, and no verdict recorded
which agent produced the change it judged.

That shape cannot be tested. There is no way to make an agent fail three times on demand,
so the one part of borromeanRings a human cannot recover from by hand — an unbounded retry
loop, or a cap that silently became four — had no test at all. It also cannot be driven:
#144's orchestrator needs a generator it can start and wait on, and a Stop hook is not
that.

This ADR is the build. It adds a second generator adapter with no model behind it, and in
doing so forces the loop's rules out of both scripts and into one tested place.

## Decision

1. **The decision is a pure function; the drivers are thin and there are two of them.**
   `meta_harness.generator.next_action(attempt, cap, gate_ok, tree_changed, exit_code)`
   returns `green | retry | escalated | generator-failed` with no clock, no filesystem and
   no subprocess, and the rule *order* is the contract: a non-zero exit outranks
   everything (the generator said it could not); an unchanged tree outranks the gate
   (retrying an idempotent generator only spends attempts); a green gate ends the loop
   even on the last attempt; then the cap; then retry. `gate_ok` is therefore read only
   after the first two rules pass, which is what lets a driver that had nothing to gate
   pass anything for it — unit-tested as an explicit property rather than left as a
   coincidence.

   The two drivers are **not** shared, and deliberately so (SPEC-generator.md §6): one is
   driven by events, the other by a process loop. Forcing the Stop hook through a
   subprocess driver on every Stop would cost a process launch per turn to remove about
   twenty lines of bash. What must not diverge — the cap and the decision — does not.

2. **`generate.sh` is the headless adapter**, a root-level sibling of `verify.sh` and
   `merge.sh`. It reads `[generator].command`, invokes it as
   `<command> <project> <last_verdict|"">` with `BORROMEANRINGS_{ATTEMPT,CAP,FAILING_CHECKS,GENERATOR}`
   set, cwd at the project, stdin closed and output captured to
   `.meta-harness/generator/<run_key>/<attempt>.log`, and runs the gate itself. Its exit
   codes are `0` green, `1` escalated, `2` generator-failed and `3` **refused** — a fourth
   outcome the spec implied but did not name, for "there is nothing to drive": no config,
   no declared command, no git repository, an unwritable evidence area. Refusing is not
   escalating; nothing was attempted.

   That distinction is load-bearing and therefore bounded: **refusing is pre-flight only.**
   Once the loop has begun, any failure that stops the driver — the evidence area became
   unreadable, the repository broke under the generator's hands, the failing ids could not
   be read back — ends the run as `escalated`, not `refused`. An orchestrator routing on
   exit codes will plausibly treat "nothing to drive" as "skip this worktree and move on",
   and a run where something *was* attempted must never be skippable. (Caught in review:
   the first implementation reused the pre-flight refusal inside the loop, which is a
   silent-skip path — the exact shape of failure this project exists to prevent.)

   It is bash, not Python, for the same reason the hook is: the I/O *is* the driver, and
   the project's mutation ratchet only sees Python. Logic that lives in Python is logic a
   surviving mutant can accuse; logic in a shell driver is covered only by the
   integration tests. So the Python surface is exactly the part worth proving, and the
   shell holds only plumbing.

3. **The failing check ids come off the verdict's rows, never off the summary.**
   `failing_check_ids` reads the persisted verdict and classifies with the gate's own
   `is_failing` allowlist, so a change to how the summary prints cannot silently drop a
   name (conformance §5.4), and an unknown status counts as failing. N2 is a requirement,
   not a best effort: if the ids cannot be read at all the run ends rather than handing
   the generator an empty list it would read as "nothing failed".

4. **A generator that writes under `.meta-harness/` is `generator-failed`.** The spec
   forbade it and specified the detection (snapshot the directory listing before and
   after) but not the consequence; this is that consequence. The driver fingerprints every
   file under `.meta-harness/` by **size and mtime** either side of the run — size alone
   would miss a counter reset from `2` to `0` — excluding only the log it is itself
   writing, and reports the violation into the decision as exit `125`: "could not be
   trusted to have run honestly", distinct from any code the command actually returned.

   The retry counter is protected twice over. It is **not resettable**: an edit is caught
   and ends the run. It is **not readable in any useful sense**: the driver hands over the
   attempt *number*, never a path into `stop_attempts/`, and within a run its own
   in-memory count is authoritative — the file is written for a human, the ledger and a
   second invocation on the same key, and never read back. We did not attempt to make the
   file unreadable by file permissions: the generator runs as the same user, so that would
   be theatre.

5. **CAP lives in `meta_harness.generator` and both adapters read it.** An unreadable CAP
   falls back to **one** attempt, not three: the smallest bound still escalates to a
   human, where guessing an unbounded one never would. A test asserts neither script
   carries a cap literal, so the Single Choice Principle here is enforced rather than
   remembered.

6. **`intent.generator` is recorded, and the gate makes no decision on it.** Whichever
   adapter runs the gate exports `BORROMEANRINGS_GENERATOR=<kind>:<id>`
   (`claude-code:<session_id>` from the Stop hook, `headless:<command basename>` from the
   driver); `verify.sh` records it into the verdict *after* `ok` is decided, so it is
   structurally incapable of loosening anything. Unset reads `""` — never a guess.

   The kind is **not** validated against an allowlist. Validating it would be a decision,
   and the field is provenance, not evidence (ADR-0071 §4): the only rules applied are
   that the label cannot damage the record it goes into (control characters refused, 128
   characters max).

7. **"The tree changed" means the executor's snapshot identity changed — `(branch, head,
   dirty tree)`, not the tree alone.** This is a correction to SPEC-generator.md N3, found
   while building it. The required check set contains checks that read the branch and the
   history (`08_branch`, `09_commits`, `11_changelog`, `13_adr`, `34_api_diff`), so a
   generator that amends a commit message or renames a branch has changed what the gate
   sees while leaving the working tree byte-identical. Under a tree-only comparison that
   generator is told it did nothing and the run escalates with the fix already in place —
   the worst kind of wrong, because a human is called in to look at work that is done. A
   fifth fixture (`commit_only.sh`) is the discriminating case, and it goes red against the
   tree-only rule. `next_action`'s parameter keeps the name `tree_changed`; what the driver
   feeds it is the wider comparison.

8. **The four scenarios are integration tests over real gate runs**, with the evidence
   behind each outcome asserted, not just the outcome: how many receipt bundles the gate
   actually produced, which ids the retry named, whether the counter survived. Two
   negative fixtures sit beside them — one resets the counter, one edits a receipt in an
   earlier bundle — and both are caught. Every one of these tests was *shown* to fail
   against a deliberately regressed loop before being trusted (eleven regressions: the
   unchanged-tree rule, the cap comparison, the non-zero-exit rule, the failing-id
   delivery, the evidence guard, change detection, the snapshot identity narrowed back to
   the tree alone, the identity recording, a re-hardcoded cap, counter clearing, and log
   capture). A sub-agent review of the finished commit then found one more, which is now
   fixed and tested: the pre-flight refusal was reachable from inside the loop.

## Alternatives considered

- **Make the Stop hook call `generate.sh`** so there is literally one driver. Rejected:
  the hook already *is* inside the loop (the substrate re-enters it), so the driver would
  have to run the gate once and return, which is the hook. It would add a process launch
  per turn and a second way to be wrong, to remove duplication that the shared decision
  function has already removed.
- **Let `next_action` take `gate_ok: bool | None`** to encode "the gate was not run".
  Rejected: it adds a third state to every call site and every test for information the
  precedence already makes irrelevant. Instead the irrelevance is a tested property.
- **Treat a write under `.meta-harness/` as `escalated` rather than `generator-failed`.**
  Rejected: escalation means "the generator tried and the gate refused"; a generator that
  edits the gate's evidence did not merely fail to fix the code. The outcomes are the
  vocabulary a #144 orchestrator will route on, and those two deserve different routes.
- **Compare `.meta-harness/` by content hash** instead of size + mtime. Rejected on cost:
  a bundle holds every check's log, and the comparison runs on every attempt. Size and
  mtime catch creation, deletion and in-place edits; the one thing they miss — a write
  that restores the byte-identical content *and* the mtime — requires the generator to
  have decided not to change anything.
- **Give the generator its own worktree** so it cannot reach `.meta-harness/` at all.
  Rejected as out of scope, not as wrong: that is #201's executor and #144's
  orchestration. The guard here is what a `local` executor can offer today.
- **Skip `intent.generator` until ADR-0056's `Intent` lands.** Rejected: the field is an
  acceptance criterion of #202, and a verdict written between now and then would be
  unattributable forever. See the consequence below for how the two meet.

## Consequences

- (+) The loop is a contract with tests instead of a property of one hook. The retry cap —
  the only failure mode a human cannot undo after the fact — is now proven at its
  boundary, in both directions, for caps other than 3.
- (+) #144 has a generator it can start, wait on, and route by exit code, with per-run-key
  counters and per-run-key logs already separated.
- (+) A verdict says who produced the change it judged, honestly labelled as self-declared.
- (+) Two independent defences stand between a generator and the gate's evidence, and both
  are demonstrated rather than asserted.
- (−) **`intent.generator` is implemented in `meta_harness.verdict` because ADR-0056's
  `Intent` is not yet on this base** (it lives on `feat/verdict-evidence`, PR #163). The
  persisted JSON is already the shape that `Intent` will own — `intent: {"generator": …}` —
  so records need no migration and `parse_intent` reads them fail-soft. **When #134 merges,
  `Verdict.generator` moves into `evidence.Intent` as one more fail-soft field and the
  shim in `verdict.py` goes away.** That merge is the only work this ADR knowingly defers.
- (−) The headless driver duplicates the hook's loop *shape* in a second thin script, as
  ADR-0071 predicted. Two places to keep correct; the decision and the cap are not among
  them.
- (−) The evidence guard is a **two-point diff**, so a generator that creates a file under
  `.meta-harness/` and deletes it again before exiting, or that edits one and restores both
  its bytes and its mtime, is invisible to it. Closing that would need a filesystem watcher
  (inotify is Linux-only and may not be installed) or an executor the generator cannot
  reach at all — which is #201's and #144's job, not a `local` executor's. Named here
  rather than papered over: the guard catches a generator that *leaves* the gate's evidence
  changed, which is what a generator trying to buy itself attempts must do.
- (−) The evidence guard means a governed project whose `.gitignore` does not ignore
  `.meta-harness/` cannot use the headless driver sensibly — every gate run would read as
  a change to the tree. `init.sh` writes that ignore; a hand-built project must too.
- (−) `headless:<basename>` names the *program executed*, so a command written as
  `bash x.sh` records `headless:bash`. Pointing `[generator].command` at the script itself
  is the fix; guessing which token of an argv string is "the real" command would be exactly
  the kind of inference this project refuses elsewhere.
- (+) The N3 correction removes a whole class of false escalation: a generator that fixes
  a commit message, adds a commit, or moves a branch is no longer told it did nothing.
- (−) Six real gate runs are added to the test suite (about 25 s of CPU). Three of the
  four scenarios use a language-agnostic fixture whose gate costs ~2 s; only
  fixed-on-retry uses a Python fixture, because that row of the spec names `20_lint`.
