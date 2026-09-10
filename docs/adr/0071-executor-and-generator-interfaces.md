# ADR-0071 — Executor and generator interfaces: one gate, pluggable where-it-runs and who-generates

**Status:** Accepted (decision only — nothing is built by this ADR; build phases are #201
and #202, each on an explicit go) · 2026-09-10 · issue #143 ·
**Specs:** `docs/specs/SPEC-executor.md`, `docs/specs/SPEC-generator.md` ·
**Sibling:** ADR-0069 (substrates) · **Builds on:** ADR-0026 (receipts), ADR-0049 (honest
status), ADR-0056 (`intent`)

## Context

Issue #143 asks for the wrapped agent (the *generator*) and the environment checks run in
(the *executor*) to sit behind explicit interfaces, so that swapping either is a
configuration change with the gate's guarantees intact. Two sibling issues cannot be
specified without that seam: #144 (parallel agents, each in an isolated worktree with its
own gate run and receipts) and #145 (a disposable container or remote sandbox for heavy or
untrusted runs).

Today both are implicit. `verify.sh`'s inner loop — `bash "$check"` sequentially in
`$PROJECT_ROOT` — *is* the executor, unnamed; every check assumes a local path, the
process's own `PATH`, `git` in the tree and write access to the working tree. Two
concurrent runs in one checkout share `mutants/`, tool caches, `last_verdict.json` and the
Stop-hook attempt counter. `stop_gate.sh` *is* the generator loop: the retry request is a
stderr string with exit 2, the "change ready" signal is the Stop event, CAP is a literal,
and no verdict records which agent produced the change it judged — ADR-0056's `intent`
carries branch, head and input digest, the *what* and not the *who*.

ADR-0069 settled a **different** axis — where hook *events* fire. This ADR is about where
*checks* run and who *generates*. The three compose: a Claude Code substrate can drive a
worktree executor; a headless generator can drive a local executor with no substrate (that
is CI). Stating the axes separately is half the value of writing them down.

One acceptance criterion in #143 turned out to be unfulfillable as written: "byte-identical
receipts for the same input." A receipt's `log` field is an absolute path and is inside
the hash; `run_id` is a timestamp and pid; test logs carry durations. Two `local` runs are
not byte-identical either. The specs replace it with an equivalence relation that is
actually a property of the system.

## Decision

1. **Two seams, named and specified; the verdict is the fixed point.** `verify.sh`'s
   verdict step — read one receipt per required id from `$RECEIPT_DIR`, re-verify each hash
   against its log, fail closed by allowlist — is unchanged for every executor and every
   generator. The executor's whole job is to fill that directory; the generator's whole job
   is to change the tree and say so.

2. **The Executor contract** (`SPEC-executor.md` §2): inputs are a snapshot identity
   `(head, tree, branch)` — `tree` being the dirty-tree OID from a temporary-index
   `write-tree`, so untracked-not-ignored files are in and `.gitignore`d paths are out — a
   check id, the config, a wall-clock bound and the harness commit; outputs are the receipt
   `emit_receipt` already writes, its log byte-exact, and an `executor.txt` sidecar (never
   a `*.json`). Eight guarantees: isolation between runs and between checks, determinism as
   equivalence, boundedness with `_lib.sh`'s exact 124 shape, **fail-closed on executor
   failure** — an `error` / `exit 125` receipt with the reason, never a missing one — no
   rewriting in transit, same harness, same branch identity. Three executors: **`local`**
   (today, extracted, the reference every other must match receipt-for-receipt),
   **`worktree`** (a git worktree per run on the same branch and commit with the dirty tree
   applied; shares only the object store; the basis for #144), **`sandbox`** (contract and
   conformance only; the repository's own Dockerfile is the first candidate; #145 builds it
   — nothing is provisioned here, by the no-spend / nothing-off-machine rules).

3. **The Generator contract** (`SPEC-generator.md` §2): the gate must be able to deliver the
   verdict and the bundle location, request a retry naming the failing checks, learn "a
   change is written" and "I cannot", and it alone owns CAP, the attempt counter, the no-op
   skip and the decision that the work is done. Two generators: **`claude-code`** (the Stop
   hook as it is; a substrate adapter from ADR-0069 carries the same generator under
   another event source) and **`headless`** (`[generator] command`, invoked with the
   project path and the last verdict, failing ids in the environment, exit 0 with a changed
   tree meaning "gate me", unchanged tree meaning "escalate now"; no model call in the
   reference fixture, which applies patch N on attempt N).

4. **Generator identity is provenance, not evidence.** `intent.generator` extends
   ADR-0056's `Intent` with a fail-soft default; the adapter that runs the gate exports
   `BORROMEANRINGS_GENERATOR=<kind>:<id>`; absent ⇒ `""`, never guessed. The gate makes no
   decision on it. What the gate never takes from a generator is stated in the spec's §4:
   no self-report counts (ADR-0049), no self-run gate, no counter reset, no push.

5. **A conformance test is the definition of done for any executor or generator.** For an
   executor: the whole fast lane on a fixture project under the candidate and under
   `local`, receipts compared field-by-field ignoring `log`, `content_sha256` and the
   executor namespace, logs compared after canonicalisation, four discriminating fixtures
   (dirty tracked edit, untracked secret, ignored forged receipt, editable-install hazard),
   fault injection for the `error`/125 guarantee, boundedness, order independence, and the
   reader-side log resolution both ways. For a generator: four fixture scenarios yielding
   exactly `green` / `escalated` / `escalated` / `generator-failed`. **Until a conformance
   test exists for another executor, `local` is the only executor; until #202 lands, the
   hooked agent is the only generator.** Self-status says which.

6. **Selection is by allowlist in the spine.** `[executor] kind` (default `local`) and
   `[generator] command` in `borromeanrings.toml`; `BORROMEANRINGS_EXECUTOR` as an
   orchestrator override; an unknown kind refuses to run — never a fallback to `local`.

7. **One reader-side change is required and named now, built with #201:** the verdict
   resolves a receipt's `log` by basename under the run's receipt dir when the recorded
   path does not exist. The hash still covers the recorded path string and the log
   content, so tamper evidence is not weakened; without this, every transported bundle
   would read `!TAMPERED`.

8. **Follow-ups filed:** **#201** worktree executor + executor conformance test; **#202**
   headless fixture generator + generator loop conformance. Both carry the label
   `enhancement` and are build-on-go.

## Alternatives considered

- **Bake worktree and sandbox logic into `verify.sh`** (`if [ "$KIND" = worktree ]; then
  git worktree add …`). Rejected. `verify.sh` is the deep module whose secret is "how a
  verdict is computed"; branching on *where* inside it spreads the executor's secret into
  the gate, gives each branch its own untested path, and leaves the conformance test with
  nothing to compare — the reference would be tangled with the candidate. The
  `ARCHITECTURE.md` secrets table gains two rows instead of `verify.sh` gaining two
  branches.
- **A plugin system** — executors and generators discovered from a directory or a
  registry, third parties drop in their own. Rejected. There are three executors and two
  generators, all known, none third-party; discovery would invite the exact vacuity this
  project fights (an executor "installed" but never conformance-tested, silently selected).
  An explicit allowlist that refuses unknown kinds is the ADR-0049 shape applied to seams.
- **Let the generator run the gate itself** (aider's `--test-cmd` model; the agent calls
  `verify.sh` and reports). Rejected outright: it is the self-report ADR-0049 forbids. A
  bundle the generator produced on its own initiative is not the gate's evidence.
- **Make the worktree the substrate's job** (Claude Code's own worktree isolation, cited in
  #144). Rejected as the *mechanism*: it isolates the agent, not the checks, and does not
  exist on other substrates; the executor contract is substrate-neutral and #144 can still
  use the substrate's isolation for the generator side.
- **Do nothing.** Rejected as the permanent answer, accepted as the current one: nothing is
  built by this ADR (ROADMAP Phase 2). But #144 and #145 were unspecifiable without the
  seam, `local`'s sharing hazards were undocumented, and #143's byte-identical criterion
  was unfulfillable as written. This ADR fixes the price without paying it — the same shape
  as ADR-0069.

## Consequences

- (+) Where checks run and who generates are contracts with tests, not properties of two
  scripts. #144 and #145 now have a foundation and acceptance criteria drawn from it.
- (+) The verdict is untouched; every existing receipt, ledger row and hook test stays the
  evidence for `local` and `claude-code`. Extracting `local` is proven zero-change by the
  `local`-vs-`local` conformance run.
- (+) A verdict will say who generated the change it judged — attribution the ledger and
  #144's per-worktree bookkeeping need, honestly labelled as self-declared.
- (+) Three real hazards are on the record before anyone builds into them: a detached
  worktree changes six checks' receipts (branch identity is a guarantee, G8); an editable
  Python install makes a worktree run test the *primary's* code (discriminating fixture
  D4); a transported bundle reads `!TAMPERED` without the reader-side log resolution.
- (−) `local` stays the only executor and concurrent `local` runs stay unsupported until
  #201 lands. Self-status must not imply otherwise.
- (−) `#143`'s "byte-identical receipts" criterion is replaced by §5.2's equivalence
  relation; the issue is updated to cite the spec rather than closed against a criterion
  the system cannot meet.
- (−) The headless driver reproduces the Stop hook's loop shape in a second thin driver
  (the decision function is shared; the drivers are not). Two places to keep correct.
- (−) Determinism is conditional on the toolchain, and only `sandbox` records it. Two
  hosts with different `ruff` versions legitimately differ; the spec says so instead of
  promising otherwise.
- (−) A `sandbox` executor's network and what-leaves-the-machine policy is per-project
  opt-in and must be declared; the fast lane runs without network, `70_pip_audit` does not,
  and the conformance test will show that divergence rather than hide it.
- (−) `35_architecture` gains a contract only when `executors/` exists (#201): `checks/`
  never references it; only `verify.sh` dispatches. Until then the seam is documentation.
