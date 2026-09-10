# SPEC — executor (where the checks run; one contract, three executors)

**Status:** Specified, not built — `local` is the only executor and is the reference
implementation (issue #143; build phase #201, on an explicit go) ·
**Decision:** ADR-0071 · **Sibling:** `SPEC-generator.md` (who produces the change),
`SPEC-substrate-adapter.md` (where the hooks fire) ·
**Gate:** `verify.sh` (its verdict step is unchanged by this spec) · **Receipts:**
`checks/_lib.sh`, `src/meta_harness/receipts.py`, `SPEC-receipts.md`

## Three axes, not one

borromeanRings has three things that can each be swapped without touching the gate, and
they are different axes:

| Axis | Question | Today | Spec |
|---|---|---|---|
| **Substrate** | where do the hook *events* fire? | Claude Code hooks | `SPEC-substrate-adapter.md` (ADR-0069) |
| **Executor** | where do the *checks* run and produce receipts? | bash on this machine in `$PROJECT_ROOT` | **this file** |
| **Generator** | who produces the *next change*? | the wrapped agent behind the Stop hook | `SPEC-generator.md` |

They compose freely: a Claude Code substrate can drive a `worktree` executor; a `headless`
generator can drive a `local` executor with no substrate at all (that is CI); #145's
sandbox is an executor, not a substrate. The gate's verdict step is the fixed point all
three meet at: it reads receipts from one directory and decides. Nothing here changes it.

## User story

As a maintainer running several agents at once (#144) or wanting a heavy or untrusted run
off my working tree (#145), I want "run this check against this project state and give me
a receipt" to be a contract with a conformance test, so that swapping where checks run is a
configuration change and the receipts a reviewer reads mean the same thing whichever
executor produced them.

## 1. Today's executor, derived from the code

This is what `verify.sh` + `checks/_lib.sh` do now. It is the `local` executor, unnamed.

1. **Resolution.** `PROJECT_ROOT = BORROMEANRINGS_PROJECT | CLAUDE_PROJECT_DIR | $PWD`;
   `BORROMEANRINGS_HOME` is where `verify.sh` lives; `HARNESS_VERSION` is `git describe`
   on that checkout. Both are exported to every check.
2. **Run identity.** `run_id = <UTC timestamp>-<pid>`; `RECEIPT_DIR =
   $PROJECT_ROOT/.meta-harness/receipts/$run_id`, created empty.
3. **Scheduling.** For `checks/shared`, `checks/<language>` and (under `--heavy`)
   `checks/ci`, in glob order, `bash "$check" || true` — sequential, in-process, in the
   same working tree.
4. **Per check.** The script sources `_lib.sh`. `run_check <id> <tool> <cmd>` requires
   `<tool>` on `PATH` (absent ⇒ receipt `error`, exit 127 — never a skip);
   `borromeanrings_run_bounded` runs `cd $PROJECT_ROOT && bash -c "$cmd"` under coreutils
   `timeout -k 10 $BORROMEANRINGS_CHECK_TIMEOUT` (default 300 s; 124 ⇒ `TIMED OUT` line
   appended to the log); `emit_receipt` writes `$RECEIPT_DIR/<id>.json` with
   `content_sha256` over every field plus the log bytes (`finalize_receipt`).
5. **Verdict.** `verify.sh` reads `$RECEIPT_DIR/<id>.json` for every required check id,
   re-verifies the hash against the log at the recorded `log` path, fails closed on
   missing / tampered / non-allowlisted status (ADR-0026, ADR-0049), prints the summary,
   persists `last_verdict.json` and the ledger row.

**Every check therefore assumes:** a local path it can `cd` into; tools on the executor
process's own `PATH`; `python3` that can import `$BORROMEANRINGS_HOME/src`; `git` usable in
`$PROJECT_ROOT` (`06`, `08`, `09`, `11`, `12`, `13`, `17`, `34` read branch, base and
history); write access to `$RECEIPT_DIR` and to the working tree (tool caches, `mutants/`);
a wall clock. Nothing records *where* the run happened; two concurrent runs in one
`PROJECT_ROOT` get distinct `RECEIPT_DIR`s but share the tree, the caches, `mutants/`,
`last_verdict.json` and `stop_attempts/`. That sharing is why `local` cannot host #144.

## 2. The Executor interface

### 2.1 Contract in one line

> **Fill `$RECEIPT_DIR` with exactly one receipt and one log per requested check, for
> this snapshot, within the bound — or with an `error` receipt saying why you could not.**

The verdict step never learns which executor ran. It sees a directory of receipts.

### 2.2 Inputs

| Input | Definition | Where it comes from today |
|---|---|---|
| **Snapshot** | `(head, tree)`: `head` = `git rev-parse HEAD` (`""` outside a repo); `tree` = the OID of the **dirty tree** — `GIT_INDEX_FILE=<tmp> git add -A && git write-tree` over the primary working tree, so tracked edits and untracked-not-ignored files are in, `.gitignore`d paths (`.meta-harness/`, `mutants/`, caches, venvs) are out. Plus the **branch name** (`git rev-parse --abbrev-ref HEAD`) because branch-reading checks are part of the required set. | implicit — it is whatever is in `$PROJECT_ROOT` at the moment |
| **Check id** | e.g. `20_lint`; resolves to exactly one file `$BORROMEANRINGS_HOME/checks/{shared,<language>,ci}/<id>.sh`. | the glob in `verify.sh` |
| **Config** | the governed project's `borromeanrings.toml` (it is inside the snapshot; the executor also receives the resolved `language`) and the pass-through knobs `BORROMEANRINGS_CHECK_TIMEOUT`, `BORROMEANRINGS_MUTATION_TIMEOUT`. | env + file |
| **Bound** | wall-clock seconds for this check. | `BORROMEANRINGS_CHECK_TIMEOUT` inside `_lib.sh` only |
| **Harness identity** | the exact `BORROMEANRINGS_HOME` commit (`HARNESS_VERSION`). A remote executor must run *this* harness, not "a" harness. | exported by `verify.sh` |

`tree` is the executor's snapshot identity. It is deliberately not ADR-0056's
`intent.input_digest` (`change_detect.compute_state_hash` over the *gated paths* only):
that digest is the no-op-skip key and stays so; `tree` is git-native, costs one
`write-tree`, needs no new code, and is what a `worktree` executor checks out. A receipt
bundle records both.

### 2.3 Outputs

- **Receipt** `$RECEIPT_DIR/<id>.json`: the object `emit_receipt` writes today — `check`,
  `command`, `exit_code`, `log`, `status ∈ {pass, fail, error, noop}`, any check-specific
  extras (`score`, `regressed`, `evaluated`, …) and `content_sha256` — such that
  `verify_receipt(receipt, log_text)` is **true** on the caller's side.
- **Log** `$RECEIPT_DIR/<id>.log`, byte-exact as the check wrote it.
- **Sidecar** `$RECEIPT_DIR/executor.txt` (one per bundle, like `harness_version.txt`):
  `kind`, `head`, `tree`, `branch`, and for `sandbox` the toolchain digest. Never a
  `*.json` — every `*.json` in a run dir is read as a receipt (receipt-dir rule, HANDOFF
  §11).

**The transported-log problem (a real design finding).** `log` is an absolute path in the
executor's namespace and it is *inside* the hash. A `worktree` or `sandbox` bundle copied
back to the primary's `.meta-harness/receipts/<run_id>/` has a `log` field pointing where
the log *was*; today's verdict reads that path, finds nothing, hashes `""` and reports
`!TAMPERED`. Two fixes were considered:

- *Emit relative log paths* — changes `_lib.sh` and every existing receipt's shape; rejected.
- *Reader-side resolution* — when the recorded path does not exist, the verdict resolves
  the log as `<receipt dir>/<basename(log)>`. The hash still covers the log **content** and
  the recorded path string, so nothing about tamper evidence weakens; an edited log still
  fails. **Adopted.** `local` never exercises the fallback; it lands with the first executor
  that needs it (#201) together with a regression test in both directions.

### 2.4 Guarantees every executor must give

| # | Guarantee | Meaning | How `local` meets it today |
|---|---|---|---|
| **G1 Isolation between runs** | Two runs never share a working tree, `.meta-harness/`, `mutants/` or tool caches. | Only when runs are sequential. Concurrent `local` runs are **unsupported**, and self-status must not claim otherwise. |
| **G2 Isolation between checks** | A check writes only `<id>.json`, `<id>.log` and tool caches; it reads no other check's receipt or scratch. Equivalently: the bundle is **order-independent**. | By convention (the receipt-dir rule); the conformance test §5 proves it by shuffling. |
| **G3 Determinism** | Same `(head, tree, branch)` + same config + same `HARNESS_VERSION` + same toolchain ⇒ receipts **equivalent** under §5.2 (fields equal; logs equal after canonicalisation). | Holds run-to-run; the toolchain is unrecorded, so "same toolchain" is the operator's promise, not the executor's. |
| **G4 Boundedness** | `execute` returns within `bound + 10 s` grace. On timeout the receipt is `fail`, `exit_code 124`, log ends with the `TIMED OUT after Ns` line — exactly `borromeanrings_run_bounded`'s shape. An executor MUST enforce the bound itself even where the check's own runner does not (a tool that ignores SIGTERM, a remote that hangs). | `timeout -k 10`; unbounded if coreutils `timeout` is absent (documented, not fixed). |
| **G5 Fail-closed on executor failure** | If the executor cannot run the check at all — worktree creation fails, container will not start, upload fails, script missing — it still writes a receipt for that id: `status: error`, `exit_code: 125`, `command` = the invocation it attempted, `log` = the reason. **Never a missing receipt.** Missing means "never scheduled"; an executor that could not run must be distinguishable from one that was never asked. `error` (not `fail`) is the ADR-0049 vocabulary: "I could not run" is neither "there was nothing to run" nor "it ran and found a violation"; both `error` and `fail` fail the verdict by allowlist. `125` is git's and Docker's "could not run" code, distinct from `124` (timeout) and `127` (tool missing). | The only executor failure `local` has is a missing script, which the glob silently skips ⇒ MISSING. Extracting `local` per #201 makes it emit the `error` receipt instead. |
| **G6 No rewriting** | The receipt is finalised by `emit_receipt` inside the check process. The executor transports receipt and log byte-exact and never re-finalises, re-hashes or edits either. | Trivially — nothing is transported. |
| **G7 Same harness** | The check code that runs is `$BORROMEANRINGS_HOME` at `HARNESS_VERSION`; `harness_version.txt` in the bundle equals the primary's. | Trivially. |
| **G8 Branch identity** | Branch-reading checks see the primary's branch name and commit. | Trivially. (Non-trivial for `worktree`; see §3.2.) |

### 2.5 Selecting an executor

`[executor] kind = "local"` in `borromeanrings.toml` (the policy spine; default `local`),
overridable by `BORROMEANRINGS_EXECUTOR` for an orchestrator that owns the run (#144).
Unknown kind ⇒ the gate refuses to start, exit 1 with the allowlist in the message — an
allowlist, never a fallback to `local`, for the ADR-0049 reason. Self-status reports the
kind. The shape when built: `verify.sh` replaces its inline `bash "$check"` loop with a
dispatch to `executors/<kind>.sh`; `checks/` never references `executors/` (a
`35_architecture` contract, added in #201).

## 3. The three executors

### 3.1 `local` — the reference implementation

Exactly §1, extracted into a file and made to emit the G5 `error` receipt. **Every other
executor must match `local` receipt-for-receipt under §5.** It is the oracle; it is
never itself "conformed" against anything but its own previous behaviour (the
`local`-vs-`local` run in §5 is the zero-change proof for the extraction).

Honest limits, unchanged by naming it: G1 only sequentially; G3 with an unrecorded
toolchain; G4 only with coreutils `timeout` present.

### 3.2 `worktree` — a git worktree per run (the basis for #144)

**Materialisation.** From the snapshot `(head, tree, branch)`:

1. `git worktree add <dir> <branch>` **on the same branch name** as the primary, forcing
   past git's "already checked out" safeguard (`--force`), or `--detach` at `head` followed
   by pointing the worktree's `HEAD` symbolic ref at `refs/heads/<branch>` — the builder's
   choice; the **contract** is that `git rev-parse HEAD` and `git rev-parse --abbrev-ref
   HEAD` inside the worktree equal the primary's (G8). A detached worktree would report
   `HEAD` as its branch and change the receipts of the two checks that read the branch
   *name* on this base — `08_branch` and `13_adr`. `06_git_identity`, `09_commits` and
   `11_changelog` resolve `base..HEAD` by commit SHA alone and are unaffected;
   `17_prior_art` also reads the name but lands with #131, so the set grows to three then.
2. `git read-tree --reset -u <tree>` in the worktree — the dirty tree, including untracked
   files, is now present; ignored paths are not.
3. Run the checks with `PROJECT_ROOT=<dir>` and `RECEIPT_DIR=<dir>/.meta-harness/receipts/<run_id>`.
4. Copy the bundle to `<primary>/.meta-harness/receipts/<run_id>/`, write `executor.txt`,
   then `git worktree remove --force <dir>`. On an executor failure keep the worktree for
   inspection and name its path in the `error` receipt's log.

**Shared:** the object store and refs (read; the executor never commits, never moves a
ref, never `prune`s another worktree), `$BORROMEANRINGS_HOME`, the host `PATH` and
toolchain, the wall clock.

**Not shared:** the working tree, the index, `.meta-harness/` (receipts, `last_verdict.json`,
`stop_attempts/`, the no-op state hash), `mutants/`, `.ruff_cache` / `.mypy_cache` /
`.pytest_cache` and every other ignored path. The worktree run writes **nothing** outside
`<dir>` except the copied bundle; whether and how the primary's `last_verdict.json` and
ledger attribute the run to a worktree is #144's decision, not this executor's.

**The toolchain hazard (real, and the reason the discriminating fixture exists).** A Python
project installed editable (`pip install -e .`) resolves imports to the *primary* checkout's
`src/`, not the worktree's. A `worktree` run of `40_test` would then test the primary's
code and report on the wrong snapshot with a valid receipt — precisely the false green this
project exists to prevent. The executor MUST make the language toolchain resolve the
worktree's source (for Python: `PYTHONPATH=<dir>/src` ahead of any editable install, or a
per-worktree environment); the conformance test's discriminating fixture (§5.3) has a
failure that exists **only** in the worktree's copy and must be reported.

**Concurrency.** N worktrees ⇒ N independent runs, each its own `run_id`, `RECEIPT_DIR`,
`mutants/`. Heavy-lane cost multiplies by N (mutation runs ~30 min per worktree); the
executor does not schedule, #144's orchestrator does.

### 3.3 `sandbox` — a container or remote sandbox (contract and conformance only; #145 builds it)

Nothing is provisioned by this spec: the no-spend, no-keys, nothing-off-machine-by-default
rules (HANDOFF §3, #145 AC 3) forbid it here. The **first** sandbox is the repository's own
`Dockerfile` run locally — a container is an executor whose filesystem and `PATH` are not
the host's; a remote sandbox is the same contract over a transport.

**Transport in:** the snapshot materialised exactly as §3.2 steps 1–2 (a clone or bundle of
the object store sufficient for `base..HEAD` — at least `main`/`origin/main` and the branch
— plus the dirty tree from `tree`); `$BORROMEANRINGS_HOME` at `HARNESS_VERSION` (G7); the
config. **Toolchain identity** is part of the snapshot for this executor: the image digest
is recorded in `executor.txt`, and G3 is claimed only for equal digests.

**Transport out:** the bundle (`<id>.json`, `<id>.log`, `harness_version.txt`,
`executor.txt`) byte-exact (G6); the caller verifies every receipt with the §2.3 reader-side
log resolution. A transport failure is an executor failure: G5 `error`/125 receipts for
every check that was requested, never a partial bundle presented as complete.

**Policy the sandbox must declare, per project:** network (`70_pip_audit` needs it; the
fast lane does not — a sandbox with no network runs the fast lane fully and reports
`70_pip_audit` as `error`, which the conformance test surfaces as a divergence from
`local`, honestly); what leaves the machine (opt-in per project via `[executor]`, default
`local`); secrets (none are mounted; `12_secrets` and `74_secret_history` read the tree,
not the environment). A missing tool inside the image is an `error`/127 receipt exactly as
on the host — the image is *required* to carry the fast-lane toolchain, and the
conformance test is what proves it does.

## 4. What is NOT the executor's concern

- **Deciding.** The verdict (`verify.sh`'s Python step) is the same for every executor and
  reads only the bundle. An executor never computes `ok`, never writes `last_verdict.json`.
- **Scheduling generators, merging, rebasing** — #144's orchestrator.
- **Trusting anything the generator says** — `SPEC-generator.md` §4. An executor exists,
  in the `sandbox` case, precisely so that receipts are produced somewhere the generator
  cannot reach; that is the one place the two seams touch.
- **Firing hooks** — the substrate's.

## 5. Conformance test (definition of done for any executor)

`tests/integration/test_executor_conformance.py`, parametrised over the executor allowlist,
`local` always included. **Fixture project** `tests/fixtures/executor_project/`: a minimal
governed Python project whose `borromeanrings.toml` requires the fast lane, built by the
test into a temporary git repo on a `feat/` branch with one commit over `main`, one
**uncommitted tracked edit**, one **untracked** file, and one **ignored** file — so every
class of path the snapshot definition names is present.

### 5.1 Same bundle

Run the whole fast lane under `local` (bundle A) and under the candidate (bundle B).
Assert: the set of `*.json` basenames is identical (no MISSING, no extra receipt); both
bundles carry `harness_version.txt` with equal content; B carries `executor.txt`.

### 5.2 Field-by-field equivalence

For each receipt id: `verify_receipt` is true for A and for B against their own logs;
every field is equal **except** `log` (a path), `content_sha256` (covers the path and the
log) and any `executor`-namespaced extra; check-specific extras (`score`, `regressed`,
`evaluated`, …) are compared exactly. Logs are compared after canonicalisation: the
primary's and the candidate's `PROJECT_ROOT` ⇒ `<ROOT>`, `RECEIPT_DIR` ⇒ `<RUN>`, durations
matching `\b\d+\.\d+s\b` ⇒ `<T>`. A log diff that survives canonicalisation is a
divergence and fails the test — with the diff printed, so a legitimate new source of noise
is added to the canonicaliser deliberately, on the record, never by loosening the field
comparison.

(This replaces #143's original "byte-identical receipts" criterion, which is unattainable
even `local`-vs-`local`: `log` and `run_id` differ per run and test logs carry timings.)

### 5.3 Discriminating fixtures (the candidate must see what `local` sees)

| Variant | Change to the fixture | Expected in **both** bundles | Proves |
|---|---|---|---|
| D1 | the uncommitted edit introduces a lint error | `20_lint` = `fail` | tracked dirty state is transported |
| D2 | the untracked file contains a fake credential from the ADR-0025 corpus | `12_secrets` = `fail` | untracked-not-ignored files are transported |
| D3 | the ignored file is a forged `pass` receipt at `.meta-harness/receipts/old/20_lint.json` | absent from both bundles; `20_lint` unaffected | ignored paths are **not** in the snapshot |
| D4 | the fixture's package is installed editable from the *primary* path; the worktree/sandbox copy alone carries a failing test | `40_test` = `fail` in B | the toolchain resolves the executor's tree, not the primary's (§3.2 hazard) |

### 5.4 Guarantees under fault

- **G5 injection:** point the candidate at an impossible target (unwritable dir, absent
  image, unreachable transport). Every requested id has an `error` receipt with
  `exit_code 125` and a non-empty reason in its log; the verdict is `FAIL` with **zero**
  `MISSING` rows.
- **G4 bound:** a fixture check that sleeps past the bound yields `fail`/124 with the
  `TIMED OUT` line, and the executor returns within bound + 10 s (measured).
- **G2 order:** run the candidate with the check order reversed; bundle equivalent under
  §5.2.
- **G8 branch:** `08_branch` and `13_adr` receipts equal `local`'s — the two checks that
  read the branch name, so a detached checkout shows in both. (`09_commits` would *not*
  discriminate here: it resolves `base..HEAD` by SHA and is identical either way.) The
  fixture is on a `feat/` branch that touches `src/`, so both checks have something to say.
- **Reader-side log resolution (§2.3):** move bundle B to a fresh directory; the verdict
  still verifies every receipt; edit one log; that receipt is `!TAMPERED`.

The test installs nothing and provisions nothing: `worktree` needs only `git`; the
`sandbox` case is `skip`ped (reported, not silently passed) when the declared runtime is
absent on the host, and CI runs it only where the runtime exists.

## 6. Honest limits

- **Determinism is conditional on the toolchain**, and only `sandbox` records it. Two
  `local` runs on machines with different `ruff` versions can legitimately differ; the spec
  does not pretend otherwise. Recording the host toolchain in `executor.txt` for `local` and
  `worktree` too is a cheap follow-on, not promised here.
- **`local` and `worktree` share the host.** A check that reads outside `PROJECT_ROOT`
  (global git config, `~/.cache`) sees the same host state under both; only `sandbox`
  isolates that, and only as far as its image does.
- **Heavy lane in a worktree is expensive** — `60_mutation` runs the whole suite per mutant
  per worktree; `mutants/` is per worktree by design (sharing it would let one run's
  mutants poison another's score).
- **Byte-identical is off the table**; §5.2's equivalence is the real property.
- **A determined generator with filesystem access can still forge a `local` or `worktree`
  bundle** (ADR-0026's threat model). Only `sandbox` (or CI) moves the receipts out of
  reach; this spec names that as the reason to build one, not as something `worktree`
  delivers.

## 7. Out of scope

The orchestrator (#144: N generators, rebase-early, merge rules, ledger attribution per
worktree); provisioning or choosing a sandbox (#145); the substrate
(`SPEC-substrate-adapter.md`); the generator (`SPEC-generator.md`); building `worktree`
(#201) or `sandbox` (#145) — this spec is the contract they build to.
