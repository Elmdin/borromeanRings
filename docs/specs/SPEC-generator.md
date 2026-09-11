# SPEC — generator (who produces the next change; one loop, two generators)

**Status:** **Built** (#202, ADR-0078) — both generators exist: the hook-driven agent
(`claude-code`) and the headless driver (`generate.sh`). The loop's decision and cap are
one tested place, `src/meta_harness/generator.py` ·
**Decision:** ADR-0071 (the seam), ADR-0078 (the build) · **Sibling:** `SPEC-executor.md`
(where the checks run), `SPEC-substrate-adapter.md` (where the hooks fire) ·
**Loop:** `.claude/hooks/stop_gate.sh` (events) and `generate.sh` (a process loop) ·
**Verdict:** `src/meta_harness/verdict.py`, ADR-0046, ADR-0056 (`intent`, on
`feat/verdict-evidence`; `intent.generator` ships here and moves into `Intent` when that
lands — ADR-0078)

## Three axes (see `SPEC-executor.md` for the table)

The **generator** is whatever produces the next change to the tree. It is not the
substrate (which fires hook events) and not the executor (which runs checks). Today it is
"whatever agent the Stop hook is attached to" and nothing records who that was. This spec
says what borromeanRings needs from a generator, what it will never take from one, and how
a scripted generator with no model behind it plugs into the same loop — so the loop can be
tested end to end (#202, done) and driven without a Stop hook (#144).

## User story

As the maintainer, I want the generate → gate → retry → escalate loop to be a contract
rather than a property of one hook script, so that a different agent, a different substrate
or a fixture script can sit in the generator's seat with the retry cap, the escalation and
the fail-closed verdict intact — and so that the verdict records which generator produced
the change it judged.

## 1. Today's generator, derived from `stop_gate.sh`

1. The agent ends its turn ⇒ substrate fires `stop` ⇒ `stop_gate.sh`.
2. Inert without `borromeanrings.toml`; `stop_hook_active: true` ⇒ exit 0 (the substrate's
   own re-entry guard); dedupe claim on `(stop, session_id)`.
3. No-op skip: if the gated-input hash equals the last proven-green hash
   (`change_detect.should_skip_gate`) ⇒ exit 0, gate not run. Fail-closed: any error ⇒ run.
4. `verify.sh` runs, bounded by `BORROMEANRINGS_GATE_TIMEOUT` (540 s); 124 ⇒ treated as
   FAIL with a note.
5. **PASS** ⇒ delete the attempt counter, exit 0 — the turn ends.
6. **FAIL** ⇒ `attempts += 1` in `.meta-harness/stop_attempts/<session_id>`.
   `attempts < CAP (3)` ⇒ stderr: `borromeanRings gate FAILED (attempt n/3). Fix the
   failing checks below, then finish again.` + the gate summary; **exit 2** — the substrate
   continues the turn and shows stderr to the model. Otherwise ⇒ stderr: `ESCALATION:
   borromeanRings gate failed 3 times — handing control to the human.` + summary; counter
   deleted; **exit 0** — the turn ends, the human sees it.

The generator here is implicit: the retry request is a stderr string, the "I have written a
change" signal is the Stop event, and identity is at most the substrate's `session_id`,
which the verdict does not record. ADR-0056's `Intent` records *branch, head, input
digest* — the *what*, not the *who*.

## 2. The Generator interface

### 2.1 Contract in one line

> **Given the project and the last verdict, write the next change and say so; the gate
> decides, counts, and escalates — you do not.**

### 2.2 What borromeanRings needs from a generator

| # | Need | Direction | `claude-code` (today) | `headless` |
|---|---|---|---|---|
| **N1 Deliver the verdict** | the gate's summary text and the receipt bundle location reach the generator after every failed attempt | gate → generator | stderr + exit 2 from the Stop hook; the bundle is under `.meta-harness/receipts/<run_id>/` and `last_verdict.json` names `run_id` | argv 2 = path to `last_verdict.json` (`""` on the first attempt); the bundle path is inside it |
| **N2 Request a retry, naming the failing checks** | "attempt n of CAP; these checks failed" | gate → generator | the same stderr text (check names come from the summary rows) | env `BORROMEANRINGS_FAILING_CHECKS` (comma-separated ids), `BORROMEANRINGS_ATTEMPT`, `BORROMEANRINGS_CAP` |
| **N3 "I have written a change"** | the signal that the tree is ready to gate | generator → gate | the Stop event | process exit 0 **with the project changed** — the driver compares `(branch, head, dirty tree, all refs, the index)` before and after. **Scope:** those five facts are a *git* identity — everything the gate reads that git can see and does not ignore. Outside it by construction: gitignored paths (`mutants/`, `.pytest_cache/`, `.venv/` — read by `60_mutation` and `40_test`; `.meta-harness/` is the one exception, force-excluded and separately guarded) and ambient machine state (installed packages, binaries on `PATH` — read by `70_pip_audit`, `72_licenses`, `40_test`, `60_mutation`). That residue belongs to an executor the generator cannot reach (#145), not to a wider comparison. **Corrected twice in #202**, because it is a list of what checks read and not an intuition: the dirty-tree OID alone misses an amended commit message (08_branch, 09_commits, 11_changelog, 13_adr read branch and history); adding branch and head still misses `git update-ref refs/heads/main HEAD` (six checks resolve a base from `origin/dev dev origin/main main`) and `git rm --cached` (01_source_coherence, 12_secrets, 15_a11y enumerate with `git ls-files`, and `add -A` puts the file back in the tree). Each narrowing tells a generator that fixed one of those that it did nothing, and escalates with the fix in place (ADR-0078). The dirty tree always **excludes `.meta-harness/`**, gitignored or not — it is the driver's own workspace |
| **N4 "I cannot / will not"** | the generator gives up | generator → gate | none — the agent can only stop; the cap does the giving up | exit 0 with the tree **unchanged** ⇒ escalate now (retrying an idempotent generator is wasted attempts); non-zero exit ⇒ `generator-failed`, escalate now |
| **N5 Bounded retry, then a human** | at most CAP attempts per attempt key, then escalation | gate-owned | `CAP=3`, counter in `.meta-harness/stop_attempts/<session_id>`, reset on green or at escalation | same CAP, same counter directory keyed by the driver's run key; the driver's exit is one of `green` / `escalated` / `generator-failed` |
| **N6 Identity in the verdict** | which generator produced the judged change | generator → verdict | `stop_gate.sh` exports `BORROMEANRINGS_GENERATOR=claude-code:<session_id>` before running the gate | the driver exports `headless:<basename of command>` |

**N6 is provenance, not evidence.** `intent.generator` (extends ADR-0056's `Intent`; default
`""` with the same fail-soft parsing, so old verdicts read unchanged) is self-declared by
the adapter that runs the gate, like a git author line. The gate makes **no decision** on
it, never guesses it (absent ⇒ `""`), and never lets it relax anything (ADR-0056 rule 3:
nothing reported ever loosens `ok`). Under a substrate adapter (ADR-0069) the kind is the
substrate's name — `codex:<session_id>` — because the hooked loop is the same generator
adapter under a different event source.

### 2.3 What the gate owns and the generator cannot touch

- **CAP** — one constant, one place: `meta_harness.generator.CAP`, read by both adapters
  (a test asserts neither carries a literal). A generator cannot raise it; an adapter that
  cannot read it falls back to **one** attempt, because the smallest bound still reaches a
  human.
- **The attempt counter** — lives under `.meta-harness/`, which the generator must not
  write. A generator that resets its counter has forged an attempt, and the retry bound is
  the only thing standing between a looping agent and a human's afternoon. Enforced, not
  requested: a write anywhere under `.meta-harness/` during the generator's run ends the
  run as `generator-failed`, detected by **content hash** — size and mtime is one
  `os.utime` away from forgeable (ADR-0078).

  The counter is **readable**, and pretending otherwise would be a comfortable fiction: a
  generator runs as the same user in the same tree and is handed a path inside
  `.meta-harness/` from attempt two (the verdict). What holds is that reading it buys
  nothing — the attempt and the cap arrive as numbers — and that the one-command reset
  no longer works: `stop_gate.sh` takes the attempt as `max(counter + 1, trailing failures
  for this session's label in the append-only verdict history)`, so `rm stop_attempts/*`
  buys nothing on its own.

  **That is a speed bump, not a bound, and the spec says so** rather than leaving a reader
  to assume otherwise. A review defeated the anchor three ways, one command each: delete
  the history, append one forged green row for the label, or relabel the rows — and
  appending is the file's sanctioned operation. The headless driver is not anchored at all
  (its label is per-command, not per-run-key, so counting history there would collapse two
  run keys into one bound); it has the counter file and a resume. A real bound needs the
  count where the generator cannot reach it, or a substrate that enforces the cap: **#218**
  for both adapters.
- **The no-op skip** — the gate's, keyed on the gated-input hash. A generator cannot
  declare "nothing changed"; the hash says.
- **When it is done** — the gate says green; the generator's "done" is a Stop event or an
  exit code, nothing more (HANDOFF §2: the gate decides, not the author).

## 3. The two generators

### 3.1 `claude-code` — the hook-driven agent (today)

The adapter **is** `stop_gate.sh`, unchanged by this spec. Mapping of §2.2 onto it is the
table's third column. Two properties worth stating because they are easy to lose when a
second adapter appears:

- The *retry request* and the *escalation* are both stderr text; only the **exit code**
  distinguishes them (2 vs 0). A substrate that does not honour exit 2 (spec
  `SPEC-substrate-adapter.md` §4, `stop: absent`) has **no** generator loop — enforcement is
  `MANUAL` — and self-status must say so.
- The attempt key is the substrate's `session_id`. Two sessions in one project keep
  separate counters; a session that compacts keeps its counter (the brief re-injection,
  ADR-0053, tells the model where it stands).

### 3.2 `headless` — a scripted generator (for tests and for #144's orchestrator)

**Driver.** `generate.sh` at the repo root, beside `verify.sh`. Exit codes: `0` green,
`1` escalated, `2` generator-failed, `3` **refused** — nothing to drive (no
`borromeanrings.toml`, no declared command) — and `4` **misconfigured**: a config that IS
here and is broken, which is a governed project about to go ungated, not a project nobody
asked to gate. Refusing is not escalating: nothing was attempted. **Refusal is pre-flight
only** — once an attempt is
under way, any failure that stops the driver escalates instead, because an orchestrator
may reasonably skip a worktree that reports "nothing to drive" and must never skip one
where something was attempted (ADR-0078).

**Configuration.** `[generator] command = "<path or argv string>"` in `borromeanrings.toml`.
Absent ⇒ there is no headless generator and the driver refuses to run (never a silent
default to some built-in fixer).

**Invocation.** `<command> <project_path> <last_verdict_path | "">` with
`BORROMEANRINGS_FAILING_CHECKS`, `BORROMEANRINGS_ATTEMPT` (1-based), `BORROMEANRINGS_CAP`,
`BORROMEANRINGS_GENERATOR` in the environment, `cwd = <project_path>`, stdin closed, stdout
and stderr captured to `.meta-harness/generator/<run_key>/<attempt>.log` (a non-`.json`
path outside any receipt dir). Bounded by `BORROMEANRINGS_GENERATOR_TIMEOUT` (default equal
to the gate's 540 s); a timeout is `generator-failed`. `BORROMEANRINGS_GENERATOR` is
`headless:<basename of the program executed>` — a command written as `bash x.sh` therefore
records `headless:bash`; point `command` at the script to be named by it.

**Obligations on the command.** May edit the tree and may commit on the current branch; must
**never** push (draft-before-push is a standing rule, and pushing is not a generating act);
must not run `verify.sh` itself (that is the gate's; a self-run gate is the self-report §4
forbids); must not write under `.meta-harness/`; makes **no model call** in the reference
fixture and needs no key in any case — a headless generator that wraps the user's own
`claude` CLI is allowed by ADR-0030 but is not this fixture.

**The loop (driver).** A pure, unit-tested decision
`next_action(attempt, cap, gate_ok, tree_changed, exit_code) → Green | Retry | Escalate |
GeneratorFailed` and a thin shell driver around it:

```
attempt = 1
loop:
  snapshot .meta-harness/ and (branch, head, dirty tree)
  run <command>                         (N3/N4)
  wrote under .meta-harness/ -> report it as exit 125 (untrusted)
  exit != 0            -> GeneratorFailed, escalate, stop
  tree unchanged       -> Escalate now, stop
  run the gate (through the configured executor, SPEC-executor.md §2.5)
  gate green           -> Green, counter cleared, stop
  attempt >= CAP       -> Escalate, counter cleared, stop
  attempt += 1; deliver verdict + failing ids (N1, N2); loop
```

**Fixture generator** `tests/fixtures/generators/apply_patch.sh`: on attempt N applies
`patches/N.diff` with `git apply`; a missing patch file ⇒ exit 0 with no change; a
malformed one ⇒ `git apply`'s non-zero exit. It reports what it was handed on **stdout**
(which the driver captures), so a test can assert N1/N2 delivery without the fixture
touching the tree to say so. Four scenarios, each an integration test that is shown to
fail when the loop regresses:

| Scenario | Patches | Expected driver result | Also asserts |
|---|---|---|---|
| fixed-on-retry | `1.diff` introduces a lint error, `2.diff` fixes it | `green` at attempt 2 | attempt 1's verdict names `20_lint`; `BORROMEANRINGS_FAILING_CHECKS` received `20_lint`; counter file absent afterwards |
| never-fixed | `1..3.diff` each keep the error | `escalated` after attempt 3 | exactly 3 gate runs; 3 receipt bundles; counter cleared |
| no-change | no patch files | `escalated` after attempt 1 | exactly 0 gate runs beyond the baseline |
| crash | `1.diff` is malformed ⇒ `git apply` exits 1 | `generator-failed` | the generator's log is captured; no receipt bundle for the failed attempt |
| commit-only (added by #202) | `commit_only.sh` commits without touching a file | the gate runs | the dirty-tree OID is unchanged, the snapshot identity is not |
| moved ref (added by #202) | `move_a_ref.sh` runs `git update-ref refs/heads/main HEAD` | the gate runs | branch, head, tree and index are all identical; six checks' diff base is not |
| untracked file (added by #202) | `untrack_a_file.sh` runs `git rm --cached README.md` | the gate runs | the file is unchanged on disk and back in the tree OID; `git ls-files` is not |
| inert (added by #202) | `inert.sh` exits 0 having written nothing | `escalated`, **whether or not the project gitignores `.meta-harness/`** | the case that was reported `green`: the driver's own capture of stdout lived in the gated tree |

Two further negative fixtures, both caught:

| Fixture | What it does | What must happen |
|---|---|---|
| `reset_counter.sh` | reads and rewrites `.meta-harness/stop_attempts/<run_key>` after writing a real change | `generator-failed`, the violation named, no gate run — resetting buys no attempts |
| `edit_receipt.sh` | flips a recorded `fail` to `pass` in an earlier bundle | `generator-failed` **and** the edited receipt no longer matches its own content hash (ADR-0026) |

The receipt fixture's second half is the §4 property demonstrated rather than asserted.
Note the correction it forced: a *later* verdict never reads an earlier bundle (every gate
run writes a fresh `receipt_dir`), so "the next verdict over that bundle is `!TAMPERED`"
is not reachable. What is real, and is what the test shows, is that the edited bundle
stops verifying — `verify_receipt` over it is false, which is exactly what a verdict
reports as `!TAMPERED` when the bundle it is judging has been edited.

## 4. What is NOT a generator concern (and what the gate never takes from it)

- **Self-report is not evidence** (ADR-0049, ADR-0026). "I ran the tests and they pass" in a
  turn, a commit message or a PR body carries zero weight; the only evidence is a receipt
  bundle produced by the executor and verified by the verdict. A generator that runs
  `verify.sh` on its own initiative produces a bundle the gate did not ask for; the gate
  runs its own. This is the whole reason the generator and executor seams are separate:
  an executor the generator cannot reach (`sandbox`, CI) is the backstop for a generator
  that could forge a `local` bundle.
- **Model, prompts, tokens, tool calls** — invisible to the gate. The prompt-rewrite
  directive (ADR-0011) and the compaction brief (ADR-0053) are substrate-side helps for a
  hooked generator; a headless generator gets neither and needs neither.
- **Choosing the executor** — the gate's configuration (`[executor]`), never the
  generator's argument.
- **Deciding it is done, counting its own attempts, resetting its counter, writing
  `last_verdict.json` or the ledger** — all gate-owned (§2.3).
- **Merging and pushing** — `merge.sh` and the human. #144's rule that a worktree cannot
  inherit a sibling's verdict is an orchestrator rule built on N6 and the per-worktree
  bundle, not a generator behaviour.

## 5. Conformance (definition of done for any generator adapter)

1. The four fixture scenarios of §3.2 produce exactly `green` / `escalated` / `escalated` /
   `generator-failed`, with the gate-run counts stated.
2. `intent.generator` is populated in every verdict the adapter produces, and `""` in a
   verdict produced with the variable unset (never a guessed default).
3. Two interleaved attempt keys keep independent counters (already the `session_id`
   design; the test proves the headless driver did not regress it).
4. The adapter's retry text names every failing check id (N2) — asserted against the
   verdict's rows, so a summary format change cannot silently drop a name.
5. No file under `.meta-harness/` is written by the generator command (the driver
   snapshots the directory listing before and after).

For `claude-code` the existing hook tests cover 3 and the exit-2/exit-0 split; #202 added
2 and 4. All five hold for `headless` in `tests/integration/test_generator_loop.py`, and
each was shown to fail against a deliberately regressed loop before being trusted
(ADR-0078 decision 7).

## 6. Honest limits

- **A hooked generator cannot say "I give up"** (N4). Only the cap ends it; three attempts
  of a stuck agent cost three gate runs. The headless contract has the signal; the hook
  does not, and no substrate in the ADR-0069 survey offers one.
- **Identity is self-declared.** `intent.generator` is as trustworthy as the adapter that
  set it — attribution for the ledger and for #144's per-worktree bookkeeping, not a
  security property.
- **The headless driver duplicates the Stop hook's loop shape** in a second place. The
  decision function is shared; the two thin drivers (hook, script) are not, because one is
  driven by events and the other by a process loop. Keeping both correct is the price of
  not forcing the hook through a subprocess driver on every Stop.

## 7. Out of scope

Any model-calling generator beyond the user's own agent (ADR-0030; no keys); a critic or
second model (#68); the orchestrator that runs N headless generators in N worktrees (#144);
the substrate that fires the Stop event (`SPEC-substrate-adapter.md`). The headless driver
and fixture were #202's scope and are built; what remains deferred there is folding
`intent.generator` into ADR-0056's `Intent` once #134 merges.
