# ADR-0076 — The `worktree` executor: a separate entry point, proven by conformance

**Status:** Accepted
**Spec:** `SPEC-executor.md` (lands with #203) — §2 (interface), §3.2 (`worktree`), §5 (conformance)
**Issue:** #201 (build phase of #143) · **Unblocks:** #144 (parallel agents, one gate each)
**Relates to:** ADR-0026 (tamper-evident receipts), ADR-0049 (fail-closed by allowlist)

## Context

`SPEC-executor.md` says "run this check against this snapshot and give me a receipt" is a
contract, and that `local` — the gate running in your working tree — is only its *first*
implementation. A contract with one implementation is an assertion. This ADR records the
second one, and what building it taught us that the spec did not know.

The want is #144's: several agents working at once, each with its own working tree,
`.meta-harness/`, `mutants/` and tool caches, each gated on its own snapshot, so one
agent's failure cannot hide behind another's green. A worktree per run is the cheapest
isolation that keeps one object store.

## Decision

### 1. A separate entry point (`run-in-worktree.sh`), not a flag on `verify.sh`

`verify.sh` is what every hook, every CI job and every governed project already invokes.
Its job is to be boring. A `--worktree` flag would put a second code path inside the one
script whose default path must never regress, and would have to be threaded through the
run-id, receipt-dir and verdict logic that the flag exists to relocate.

`run-in-worktree.sh` is instead a *caller of* `verify.sh`: it prepares a tree, runs the
**unmodified** gate there with `BORROMEANRINGS_PROJECT` pointed at it, and copies the
bundle back. `local` is untouched by construction — the "zero receipt change for `local`"
criterion is met by there being no change to prove.

The cost is honest and recorded here: this is *not* yet the `[executor] kind` dispatch the
spec's §2.5 describes. There is no allowlist in `borromeanrings.toml`, no
`BORROMEANRINGS_EXECUTOR` override, and no per-check G5 `error`/125 receipt when the
executor itself cannot run — an entry point that fails before the gate starts has no
receipt dir to write into. It fails closed and loudly (exit 1, the reason on stderr)
instead. Those pieces belong with the in-gate dispatch, and are listed as not-done below.

### 2. G8 (branch identity) — a snapshot repository, not a `git worktree`

**Amended after the PR #212 review, which found the first mechanism broken.** The
original was `git worktree add --detach` at the primary's HEAD followed by
`git symbolic-ref HEAD refs/heads/<branch>`. It passed every sequential test and was
wrong, for a reason worth writing down:

> **A linked worktree shares the repository's ref namespace.** Making
> `git rev-parse --abbrev-ref HEAD` equal the primary's branch means pointing the
> worktree's HEAD at the primary's **live** branch ref. It matches at the instant you
> assert it — and then follows the branch forward the moment the primary commits, while
> the materialised tree stays pinned at the captured snapshot. `09_commits`, `13_adr`,
> `11_changelog` and `34_api_diff` re-derive HEAD and their commit range *live*, so they
> then judge a range that does not correspond to the tree in front of them. It also
> bypasses git's own "already checked out in another worktree" safeguard, which exists
> precisely to stop two working trees sharing one branch ref.

Reproduced in a scratch repo: worktree HEAD `bf833dd` → primary commits → worktree HEAD
`f812edd`, tree unchanged. **Within one repository this is unfixable**: HEAD must be a
symbolic ref to `refs/heads/<branch>` for `--abbrev-ref` to print the branch name, and in
one repository that ref is necessarily the shared, live one. Per-worktree ref hierarchies
(`refs/worktree/*`) do not help — they print under their own name, not the branch's.

**So the worktree executor no longer uses `git worktree`.** It builds a *snapshot
repository*: `git init` in the temp dir, `objects/info/alternates` pointing at the
primary's object store (**no object is copied** — this is what `git clone --shared` does,
without the ref rewriting), every one of the primary's refs copied in **verbatim**, and
`refs/heads/<branch>` pinned there at the captured commit. The five properties the review
asked for, each by construction:

| Property | How |
|---|---|
| HEAD equals the captured SHA and **cannot move** | the branch ref lives in *this* repository; nothing outside the run can write it |
| `--abbrev-ref HEAD` equals the primary's branch | HEAD is a symbolic ref to that pinned local branch (asserted at runtime, fail-closed) |
| the primary's branch ref and reflog are never written | the only primary-side git commands are `rev-parse`, `for-each-ref`, `add -A`/`write-tree` under `GIT_INDEX_FILE`, all read-only on refs. No `worktree add`, so not even `.git/worktrees/` metadata |
| two concurrent runs on one branch both succeed | each run is its own repository with its own refs; there is nothing to contend for |
| objects still shared; cleanup bounded | alternates (a 108 KB `.git` in the fixture); cleanup is `rm -rf` of the temp dir this run made, and `git worktree prune` is now not merely avoided but unnecessary |

**Copying the refs verbatim is load-bearing for conformance, not incidental.** The base
that `09_commits`, `11_changelog`, `13_adr` and `34_api_diff` resolve (`origin/dev`, `dev`,
`origin/main`, `main`) must be the same ref at the same commit as the primary's, for the
whole run. A `git clone --shared` would *not* give that: clone rewrites the source's local
branches as `refs/remotes/origin/*`, so the clone's `origin/main` is the primary's **local**
`main`, which may differ from the primary's own `origin/main` — a silent divergence in four
checks. Verbatim ref copy avoids it, and makes the ref state an explicit part of the
snapshot: `(head, tree, branch, refs)`.

Why it matters concretely: on this base exactly two required checks read the branch
*name* — `08_branch` and `13_adr` (`17_prior_art` joins them with #131). A detached
worktree reports its branch as `HEAD`, which silently flips `13_adr` from fail to pass and
changes `08_branch`'s log. The conformance fixture sits on a `feat/` branch that touches
`src/` precisely so both checks have something to say and a detached run would show. When
the primary is itself detached, the snapshot is detached at the same commit, and G8 holds.

**Honest limits of the new mechanism.** Alternates mean the snapshot repo borrows objects
it does not own: a `git gc --prune` in the primary *during* a run could remove an object
the run still needs (the same exposure a linked worktree has, since it shares the same
object store — the spec already accepts object sharing). A shallow primary's `shallow`
boundary is copied, or history reads would walk into objects that were never fetched. And
the primary's `.git/config` is *not* inherited: the snapshot repo is created from
`git init --template=` with no hooks and no local config, so a check that depended on a
repo-local git setting would see the default instead. None do today.

### 3. The snapshot: dirty tree in, ignored paths out, **and the primary's index restored**

`GIT_INDEX_FILE=<tmp> git add -A && git write-tree` over the primary's tree (starting from
a *copy* of the primary's index, so staged state survives and the primary is never
written to), then `git read-tree --reset -u <tree>` in the worktree.

**This is where the spec is wrong, and the finding is the main thing this build learned.**
`SPEC-executor.md` §3.2 stops at step 2. Step 2 alone leaves the worktree's index equal to
the snapshot tree — which means every **untracked** file is now *tracked* there. Checks
that read the tracked set see a different project than `local` does:

- `12_secrets` scans `git ls-files` only. Under step-2-only materialisation it scans the
  untracked files too, so a worktree run is silently *stricter* than a local one.
- `01_source_coherence` decides "is there tracked source elsewhere?" from the same set.

So the executor copies the primary's index into the worktree after `read-tree`. With it,
`git status --porcelain -uall` and `git ls-files` in the worktree are byte-identical to the
primary's, and the two executors agree. Without it, they do not — and the conformance test
is what would have caught it either way.

**A second spec correction follows from the same place.** §5.3's fixture **D2** expects an
untracked file holding a fake credential to make `12_secrets` **fail in both** bundles.
With the index restored (i.e. with conformance actually holding), `12_secrets` scans
tracked files in both executors and flags it in *neither*. The property worth asserting is
that the untracked file is **materialised and still untracked** — which is what the test
asserts, along with a discriminator that does not depend on the tracked/untracked
distinction: the untracked file carries a lint error, so `20_lint` names it in both logs,
and its uncovered lines move `40_test`'s `coverage_percent`, which is compared exactly.

### 4. Reader-side log resolution (the transported-bundle hazard)

A receipt's `log` is an absolute path in the executor's namespace, and it is *inside* the
content hash. Copy a bundle back to the primary and today's reader finds nothing at that
path, hashes `""`, and reports every receipt `!TAMPERED`. `SPEC-executor.md` §2.3 adopted
reader-side resolution and said it lands with the first executor that needs it. It does,
here: `receipts.resolve_log_path()` falls back to `<receipt dir>/<basename(log)>` when the
recorded path is gone, and `verify.sh`'s verdict and `receipts.verify_dir()` both use it.

Tamper evidence is unweakened: the hash still covers the log's *content* and the recorded
path *string*. Resolution finds where the bytes are; it never changes what they must be.
Both directions are tested — a moved bundle verifies, a moved bundle with an edited log
still fails — at unit level and end to end against a real worktree run whose worktree has
been removed (with the worktree kept alive the fallback is never exercised, and a test
that does not remove it passes vacuously; that mistake was made and caught here).

### 5. Cleanup, bounded

The worktree and its temp dir go away on **every** exit path — success, failure, and
interrupt (`trap cleanup EXIT` plus `INT`/`TERM`/`HUP` traps that exit into it). The
removal is bounded the way `60_mutation` bounds `mutants/`: the temp dir this run created
is resolved with `pwd -P` at creation, re-resolved at cleanup, and removed **only** if the
two match — otherwise the script refuses and says so. The worktree is deregistered with
`git worktree remove --force` on exactly its own path; `git worktree prune` is deliberately
**not** run, because it is repo-wide and this executor touches nothing belonging to another
run. `--keep` opts out for inspection and prints the exact commands to clean up by hand.

This deviates from spec §3.2 step 4 ("on an executor failure keep the worktree for
inspection"): an orchestrator running N of these must not accumulate temp trees when
things go wrong, so the failure *reason* is printed instead of preserved on disk, and
`--keep` is there when you want the tree.

### 3b. A third SPEC correction: §3.2's prescribed mechanism cannot hold G8

`SPEC-executor.md` §3.2 step 1 offers `git worktree add --force <branch>` **or**
`--detach` + re-pointing HEAD, "the builder's choice", with the contract being that
`rev-parse HEAD` and `--abbrev-ref HEAD` equal the primary's. Both options are the same
option — both end with the worktree's HEAD on the repository's shared live branch ref —
and **neither holds the contract for the life of a run** once the primary can commit,
which is exactly the situation #144 creates. The guarantee wording needs to say *when*:

> **G8 (branch identity).** Branch-reading checks see the primary's branch name and the
> commit captured in the snapshot, and **neither can change for the duration of the run**,
> whatever happens in the primary meanwhile.

and §3.2's materialisation should prescribe a private ref namespace (a snapshot repository
sharing the object store), not `git worktree add`.

## The editable-install hazard, and what we can honestly offer

A Python project installed editable (`pip install -e .`) can resolve its imports to the
**primary** checkout, not the worktree's. `40_test` would then test the primary's code and
write a valid receipt against the worktree's snapshot — precisely the false green this
project exists to prevent.

The spec's mitigation is `PYTHONPATH=<dir>/src` "ahead of any editable install". That is
**not sufficient and this ADR says so**: modern setuptools editable installs register a
`MetaPathFinder` via a `.pth` file, and `sys.meta_path` is consulted *before* `sys.path` —
so `PYTHONPATH` beats an old-style path install and loses to a finder-based one.

What the executor does, therefore:

1. exports `PYTHONPATH=<worktree>/<src_dir>` (wins for uninstalled and path-installed
   packages — the common cases);
2. **asks** where the package actually resolves (`importlib.util.find_spec(...).origin`,
   evaluated inside the worktree) and **refuses to run at all** if the answer is outside
   the worktree (`executor.import_shadow_violation`). Detection is honest where mitigation
   is not: a run that would report on the wrong tree does not happen.

The fixture project carries the same tripwire as one of its own tests, so the property is
asserted from inside a governed project too.

## Alternatives considered

- **`git worktree add --force <branch>`**, and **`--detach` + `symbolic-ref`** (the spec's
  two options for G8, and this ADR's original decision). Both rejected now: they share the
  primary's live branch ref, so HEAD follows the primary's next commit (see §2).
- **`git clone --shared --no-checkout`** + pinning the branch there. Has all five
  properties, and was the shape the review suggested. Rejected for a narrower reason:
  clone rewrites the source's local branches as remote-tracking refs, so the base refs the
  four range-reading checks resolve are no longer the primary's — a conformance divergence.
  `git init` + alternates + a verbatim ref copy is the same cost with exact ref fidelity.
- **A per-worktree ref hierarchy** (`refs/worktree/*`) inside the primary. Rejected: those
  refs shorten to their own names, so `--abbrev-ref HEAD` would not print the branch name.
- **Relaxing G8** (run detached and accept `HEAD` as the branch name). Rejected: it changes
  the receipts of every branch-reading check, which is the thing conformance forbids. It
  stays on the table only if a future host cannot give a private ref namespace.
- **A `--worktree` flag on `verify.sh`.** Rejected above: it puts a second path inside the
  script whose default path must not regress.
- **Emitting relative `log` paths** (the other fix for the transported bundle). Rejected in
  the spec and here: it changes `_lib.sh` and the shape of every receipt ever written.
- **Copying `last_verdict.json` / the ledger back** with the bundle. Not done: whether a
  worktree run counts as the primary's verdict is #144's decision, not the executor's. A
  worktree run therefore does **not** mark the primary green (its `record_green` write
  lands in the worktree and dies with it) — a conservative default.

## Consequences

- The Executor interface has two implementations, and `tests/integration/test_executor_conformance.py`
  proves the second matches the first: same receipt set, every field equal (extras
  included, `log` and `content_sha256` excluded), every log equal after canonicalisation,
  over the whole fast lane on a fixture built to discriminate. A log diff that survives
  canonicalisation fails the test with the diff printed — new noise gets added to the
  canonicaliser deliberately, on the record, never by loosening the comparison.
- #144 has its isolation primitive: N runs, N working trees, N `.meta-harness/`s, one
  object store, and receipts that mean the same thing as a local run's.
- The equivalence relation is now code (`meta_harness.executor`), not prose, and is unit
  tested to exact values.
- **A moving primary is now a tested property, not an assumption.** Three cases the
  original single-sequential-run suite structurally could not catch: HEAD immovability
  while the primary commits (deterministic — no race in the test), an in-flight commit
  during a run leaving `09_commits`/`13_adr` receipts untouched, and two concurrent runs
  on one branch producing equivalent bundles. All three fail against the first mechanism;
  the first two were run against it to prove they do.
- **Honest limits.** `local` and `worktree` share the host, so a check that reads outside
  `PROJECT_ROOT` sees the same state under both. The snapshot excludes ignored paths, so
  the two executors are equivalent only for checks that do not read ignored files — a tool
  that walks the filesystem without consulting git (mypy, bandit) *would* diverge on an
  ignored file inside `src/`; no check does today, and the conformance test would catch it
  the day one does. Determinism is still conditional on an unrecorded toolchain. A
  determined generator with filesystem access can still forge a `worktree` bundle exactly
  as it can a `local` one (ADR-0026's threat model); only a sandbox or CI moves receipts
  out of reach, and that is #145.
- **Not done here** (the rest of #201, deliberately, so this stays reviewable):
  `[executor] kind` + `BORROMEANRINGS_EXECUTOR` with a fail-closed allowlist; `verify.sh`
  dispatching through `executors/<kind>.sh`; per-check G5 `error`/125 receipts on executor
  failure; the `35_architecture` contract that `checks/` never references `executors/`;
  self-status reporting the kind; §5.4's fault-injection, bound and order-independence
  cases. Each needs the in-gate dispatch to exist first.
