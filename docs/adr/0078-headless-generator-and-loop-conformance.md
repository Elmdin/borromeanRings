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
   codes are `0` green, `1` escalated, `2` generator-failed, `3` **refused** — an outcome
   the spec implied but did not name, for "there is nothing to drive": no
   `borromeanrings.toml`, no declared command — and `4` **misconfigured**, for a config
   that is present and broken. Refusing is not escalating; nothing was attempted. And a
   broken config is not an absent one: the first is a project nobody asked to gate, the
   second is a governed project about to go ungated and unnoticed, and an orchestrator
   branches on the number rather than on the sentence.

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

4. **A generator that writes under `.meta-harness/` is `generator-failed`, and the
   fingerprint is the content.** The spec forbade the write and specified the detection
   (snapshot the directory before and after) but not the consequence; this is that
   consequence, reported into the decision as exit `125` — "could not be trusted to have
   run honestly", distinct from any code the command actually returned.

   The fingerprint is `size:sha256`, not `size:mtime_ns`. Size and mtime was the first
   implementation and it was forgeable in one line: write `0` over `2` in the counter,
   then `os.utime` the nanoseconds back, and the guard goes silent on exactly the tamper
   it exists to catch. Hashing costs one read of the evidence area per attempt; the cost
   is real and scales with a directory nothing prunes, and it is the only reading a
   generator cannot restore.

   Nothing is excluded from the snapshot, either. The driver's own capture of the
   generator's output now lives outside `.meta-harness/` until the comparison is over,
   because the excluded path used to be `generator/$RUN_KEY/$ATTEMPT.log` — and the run
   key and the attempt are both handed to the generator, which makes an exception it can
   compute into a door.

   **What we do *not* claim about the counter.** A generator runs as the same user in the
   same tree, is handed the project path, and from attempt two is handed a path inside
   `.meta-harness/` (the verdict it must read). The counter is readable, and file
   permissions would be theatre. What holds is narrower and true: reading it buys nothing
   (the attempt and the cap arrive as numbers), writing it is caught within a run, and —
   decision 8 — deleting it between runs no longer resets the bound.

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

   It is also what makes decision 8 possible: `claude-code:<session_id>` is how one
   session's rows are picked out of a project-wide history.

7. **"The tree changed" means everything the gate can read changed — `(branch, head,
   dirty tree, all refs, the index)`.** This is a correction to SPEC-generator.md N3, and
   it took two passes to get right, which is itself the argument for stating it as a list
   of what checks actually read rather than as an intuition about "the code".

   Tree alone is wrong: `08_branch`, `09_commits`, `11_changelog`, `13_adr` and
   `34_api_diff` read the branch and the history, so an amended commit message changes
   what the gate sees and no file at all. `(branch, head, tree)` is *also* wrong, in the
   same direction and for two more reasons a review found: six checks resolve their diff
   base by trying `origin/dev dev origin/main main`, so `git update-ref refs/heads/main
   HEAD` — or a plain `git fetch` — moves what they read with HEAD untouched; and
   `01_source_coherence`, `12_secrets` and `15_a11y` enumerate files with `git ls-files`,
   so `git rm --cached f` changes what they inspect while the file sits unchanged on disk
   and `add -A` puts it straight back into the tree OID.

   Each narrowing has the same failure shape: the generator is told it did nothing and the
   run escalates with the fix already in place — a human called in to look at finished
   work. Three fixtures discriminate the three cases (`commit_only.sh`, `move_a_ref.sh`,
   `untrack_a_file.sh`), and each goes red against the narrower rule. `next_action`'s
   parameter keeps the name `tree_changed`; what the driver feeds it is the wider
   comparison.

8. **The retry bound is anchored to the gate's append-only history as well as to the
   counter file.** The counter is one small file in the agent's own working tree. In the
   headless driver a write to it is caught; in `stop_gate.sh` — the adapter most runs
   actually use — there is no evidence guard at all and the file *is* read back, so
   `rm .meta-harness/stop_attempts/*` bought an unbounded retry loop with nothing to
   detect it. That is the one failure a human cannot un-spend, sitting behind a file
   anyone in the tree can delete.

   Both adapters now take the attempt number as `max(counter + 1, history)`, where
   `history` is the trailing run of failures attributed to *this generator label* since
   its last green, read from `.meta-harness/verdict_history.jsonl`. That file is
   append-only, it is what the effectiveness ledger reports (ADR-0047), and truncating it
   destroys a record a human reads — so the cheap attack stops working and the expensive
   one is loud. It is still not unforgeable; nothing file-based can be against a process
   running as the same user. It is strictly better than one deletable integer, and the
   claim is now sized to what it does.

   The driver also *resumes* rather than restarts: a counter left behind by a killed run
   means the key has spent attempts, and N5 bounds the key, not the invocation.

9. **Both adapters call `next_action`.** The first implementation shared only `CAP` and
   left `stop_gate.sh` with the loop transcribed in shell. The two agreed — a review
   enumerated all four caps and found them equivalent — but agreeing today is not the
   property claimed, which was that they cannot drift. The hook now calls the same
   function, passing `tree_changed=true, exit_code=0` because a Stop event carries neither
   signal: a hooked agent cannot say "I wrote nothing" or "I could not" (spec §6). That
   asymmetry is a real limit of the substrate, and it is now visible at the call site
   instead of implied by a missing branch.

10. **The four scenarios are integration tests over real gate runs**, with the evidence
   behind each outcome asserted, not just the outcome: how many receipt bundles the gate
   actually produced, which ids the retry named, whether the counter survived. Two
   negative fixtures sit beside them — one resets the counter, one edits a receipt in an
   earlier bundle — and both are caught. Every one of these tests was *shown* to fail
   against a deliberately regressed loop before being trusted (eleven regressions: the
   unchanged-tree rule, the cap comparison, the non-zero-exit rule, the failing-id
   delivery, the evidence guard, change detection, the snapshot identity narrowed back to
   the tree alone, the identity recording, a re-hardcoded cap, counter clearing, and log
   capture). A sub-agent review of the finished commit then found one more, which is now
   fixed and tested: the pre-flight refusal was reachable from inside the loop. A second,
   independent review then found the fail-open in decision 11 and five more defects, all
   of which are the reason decisions 4, 7, 8, 9 and 11 read as they do. The lesson worth
   keeping is not "review finds things" but *which* thing hid it: every fixture in the
   suite pre-created a `.gitignore` that the harness itself never writes, so the
   configuration under test was the rare one.

11. **`.meta-harness/` is excluded from the snapshot identity whether or not the project
   gitignores it, because the driver must not depend on a file borromeanRings never
   writes.** The blocking defect of this change: `dirty_tree_oid` is `git add -A` plus
   `write-tree`, which includes untracked-not-ignored paths, and the driver's capture of
   the generator's stdout lived in `.meta-harness/`. On a project without the ignore, the
   tree therefore "changed" on every attempt — so a generator that ran cleanly and wrote
   **nothing** was reported `green`, exit 0, "a change was written and the gate accepted
   it". Neither `init.sh` nor `adopt.sh` writes a `.gitignore`, so that was the default
   configuration, and every fixture in the suite pre-created the file that hid it.

   Two fixes, because either alone would leave the other half standing: the evidence area
   is excluded from the tree OID outright (`git rm --cached` against the temporary index),
   and the capture lives outside it until the comparison is over. The driver also warns
   when `.meta-harness/` is not ignored — it no longer depends on that, but a project
   whose gate scans its own receipts wants to know.

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
  `Intent` is not yet on this base** (it lives on `feat/verdict-evidence`, PR #163), and
  merging the two is a **migration, not a rename**. On that branch `Intent` is
  `(branch, head_sha, input_digest)`, `Intent.to_dict()` emits exactly those three keys,
  `parse_intent` reads exactly those three and drops the rest, and `Verdict.to_dict()`
  there is `"intent": self.intent.to_dict()`. The two `to_dict`s collide on the same key,
  and whichever wins, `generator` is **dropped** unless `Intent` is extended. The merge
  therefore requires three edits, named here so they are not discovered later: add
  `generator: str = ""` to `evidence.Intent`, emit and read it in `to_dict`/`parse_intent`,
  and delete `Verdict.generator` and `_parse_generator` from `verdict.py`. Persisted
  records survive it — the JSON shape is the same — but the code does not merge itself.
- (−) The headless driver duplicates the hook's loop *shape* in a second thin script, as
  ADR-0071 predicted. Two places to keep correct; the decision and the cap are not among
  them.
- (−) The evidence guard is a **two-point diff**, so a generator that creates a file under
  `.meta-harness/` and deletes it again before exiting, or that edits one and restores its
  exact bytes, is invisible to it. (Restoring the *timestamps* no longer suffices — that
  hole is closed.) Closing the rest would need a filesystem watcher (inotify is Linux-only
  and may not be installed) or an executor the generator cannot reach at all — #201's and
  #144's job, not a `local` executor's. Named rather than papered over: the guard catches a
  generator that *leaves* the gate's evidence changed, which is what a generator trying to
  buy itself attempts must do.
- (−) The loop's end-to-end behaviour sits outside the mutation lane: `test_generator_loop.py`
  reads repo-root paths, which mutmut's copied working dir does not have (ADR-0022), so it
  is in `setup.cfg`'s ignore list. That trade is still right — un-ignoring it fails the
  lane closed with "MUTATION CHECK DID NOT RUN" — but this change is the evidence that it
  is not free: the fail-open in decision 11 lived in the shell driver, where no mutant
  could reach it, and the integration tests that could have caught it all shared one
  unrepresentative fixture. The response is to keep moving decisions into Python, where
  mutation does see them (`verdict_mismatch`, `attempt_number`, `attempts_from_history`
  are all new here and all mutated), and to keep the fixtures honest about the default
  configuration rather than the convenient one.
- (−) The evidence guard means a governed project whose `.gitignore` does not ignore
  `.meta-harness/` cannot use the headless driver sensibly — every gate run would read as
  a change to the tree. `init.sh` writes that ignore; a hand-built project must too.
- (−) `headless:<basename>` names the *program executed*, so a command written as
  `bash x.sh` records `headless:bash`. Pointing `[generator].command` at the script itself
  is the fix; guessing which token of an argv string is "the real" command would be exactly
  the kind of inference this project refuses elsewhere.
- (+) The N3 correction removes a whole class of false escalation: a generator that fixes
  a commit message, adds a commit, or moves a branch is no longer told it did nothing.
- (−) Roughly a dozen real gate runs are added to the test suite (about 40 s of CPU). Three of the
  four scenarios use a language-agnostic fixture whose gate costs ~2 s; only
  fixed-on-retry uses a Python fixture, because that row of the spec names `20_lint`.
