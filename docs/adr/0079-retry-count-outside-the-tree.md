# ADR-0079 — Keep the Stop hook's retry count outside the governed tree

**Status:** Accepted

## Context
The Stop hook (`stop_gate.sh`) bounds the generate → verify → retry loop: after `CAP` (3)
failed gates it stops blocking and escalates to the human. The count behind that bound
lived at `<project>/.meta-harness/stop_attempts/<session_id>`, and a missing or unreadable
file read as `0`. The agent being governed has write access to its project, so
`rm .meta-harness/stop_attempts/*`, or one write of `0`, bought it unlimited attempts (#218).
Nothing distinguished that from ordinary tidying, and the failure was silent.

The review on #217 showed that no mechanism *inside* the tree can close this. A per-row
authenticator needs a key the agent can read; a monotonic counter needs storage the agent
cannot reach; the receipt hash has no secret. Every one of them is same-user writable.

#218 then proposed moving the count out of the tree, on the argument that the agent is a
*same-tree* adversary (confined to the project by its tooling) rather than a *same-user*
one. The review of #221 showed that distinction does not hold for this hook (D3 below):
the gate itself runs the project's code as the user.

## Decision
**The count lives at `${XDG_STATE_HOME:-$HOME/.local/state}/borromeanrings/<digest>/stop_attempts/<session>`**,
where `<digest>` is the first 32 hex characters of the sha256 of the project's *resolved*
absolute path.

- The derivation and every decision — where the count lives, how much it is, retry or
  escalate, the migration below — live in `meta_harness.retry_state`: pure functions plus
  thin, injected I/O, unit-tested to 100% line and branch coverage. `stop_gate.sh` only
  dispatches on the one line it prints (`retry N`, `escalate N`, anything else).
- **Keyless.** No secret, no key file.
- **Resolved path.** A project reached through a symlink, `..` or a trailing slash shares
  its count with the real path. A bind mount is a distinct path to `realpath`, so a project
  reached through two bind-mount aliases gets two counts. The harness chooses that path, not
  the agent, so this is documented rather than handled.
- **Session ids** that are not plain `[A-Za-z0-9_-]{1,128}` are hashed into the filename,
  so a hostile id cannot walk out of the counter directory. The borromeanRings-owned
  directories are created `0700`.
- **Fail closed.** No absolute `XDG_STATE_HOME` or `HOME`, a state root that is a file or
  unwritable, an unreadable or corrupt counter, **a state root that resolves inside the
  project** (which would silently put the count back in the tree), or a symlink on the
  legacy path: each yields `unrecorded`, and the hook escalates to the human on that Stop,
  printing the gate failure and the reason. The old hook counted from zero in every one of
  these cases, silently.
- **No hook imports from the project.** Hooks run with the project as their working
  directory, and `python3 -c` / `python3 -` put it first on `sys.path`, so a planted
  `json.py` was imported by the Stop hook's payload parse and handed it a fresh session id
  on every Stop (#221 review, D2). Every Python a hook starts now goes through
  `borromeanrings_py` in `.claude/hooks/_lib.sh`, which runs it from `/` and leaves
  `PYTHONPATH` alone. The interpreter's `-P` flag would do the same, but it only exists from
  Python 3.11 and `requires-python` is 3.10, where it is an unknown option; CI runs 3.12
  only, so that break would be invisible. `-I` also discards `PYTHONPATH`, which is how the
  hooks find `meta_harness`. A test bans both flags and any hook that names the interpreter
  outside the helper.

### What this buys, and what it does not
- **Resistance to accident and to a naive reset.** Deleting the counter file, deleting
  `.meta-harness/stop_attempts/` or all of `.meta-harness/`, writing `0` there, and writing
  `0` while restoring the mtime with `os.utime` no longer reset the count.
  `tests/integration/test_retry_bound_reset.py` runs each of those, plus a planted
  `meta_harness/` package, a planted `json.py` and a symlinked legacy path, and each asserts
  the attack took effect before asserting the outcome.
- **Failing closed instead of counting from zero** when the state directory is broken. That
  was a real bug on `dev`, independent of any adversary.
- **It is not a bound against intent, and it does not stop an in-tree agent that means to
  reset the count.** The gate runs the project's tests, and a `tests/conftest.py` that
  deletes the state digest directory reset the count on every Stop in review (D3). pytest
  runs project code as the user, so an in-tree agent becomes a same-user adversary on every
  gate run of any project with tests. Anything else running as the user can reset the count
  the same way; the test file pins that as a control. Closing this needs the test run
  isolated from the state it could forge — a separate account, a privileged executor, or a
  sandboxed test run. That is executor work (M7), not something the hook can do.
- **Self-governance is weaker still.** When borromeanRings governs its own repository, the
  hook and `meta_harness/` are themselves inside the tree.

### Migration from the in-tree counter
A project upgraded mid-retry has a count in `.meta-harness/stop_attempts/<session>`. On the
next failure the hook reads it, takes `max(out-of-tree count, in-tree count)`, records the
result out of tree, and then removes the in-tree file (and its directory once empty). A
passing gate removes both.

The legacy path is walked with `O_NOFOLLOW` directory descriptors, and the read and both
removals go through those descriptors. A symlink at `.meta-harness`, at `stop_attempts` or
at the counter file is refused as hostile (`unrecorded`, so the hook escalates); `clear()`
leaves it in place. The first version followed links, and a
`.meta-harness/stop_attempts -> <state>/stop_attempts` link planted before the first Stop
made the migration delete the real count on every Stop (#221 review, D1).

`max` means a *legacy file's value* cannot lower the count. It does not make the in-tree
location harmless: D1 lowered the count through that path, which is why a link there is
now refused rather than followed. Garbage or unreadable legacy content counts as `0`. The
legacy file is removed only after the out-of-tree write succeeds. An agent can still write
a large number there to escalate early; that hands control to the human with the failing
gate on screen, the fail-safe direction.

## Alternatives considered
- **An evidence guard over the in-tree counter** (content hash, `lstat` coverage, the #217
  approach). Rejected: detection inside the tree is same-user writable, and the #217 review
  defeated its history anchor with one forged append, the file's own sanctioned operation.
- **An authenticator or monotonic counter in the tree.** Rejected: both need something the
  agent cannot read or reach, and the tree has nothing of the kind.
- **A privileged executor, or a test run isolated from this state.** The only designs that
  make the bound hold against intent, including D3. Deferred to executor work.
- **Document the limit and leave the count in the tree** (the state before this ADR).
  Rejected: moving it is cheap, stops accidental and naive resets, and the fail-closed paths
  fix a real bug.

## Consequences
- (+) Tidying `.meta-harness/` or a naive reset no longer buys more attempts.
- (+) A broken state directory escalates loudly instead of counting from zero.
- (+) No hook imports modules from the project directory any more.
- (−) The count can still be reset by intent, through the gate's own test run (D3) or any
  same-user process. It is a speed bump against accident, not a bound against intent.
- (−) **State outside the repository.** A governed project's retry history can no longer be
  read by opening the repository. The count is short-lived (one session's failures, cleared
  on a pass or an escalation), so little is lost, but it is a trade this project had
  otherwise avoided, made here on purpose.
- (−) Escalation is still not a durable record: the count is removed when it escalates,
  as before.
- **Still open on #218.** The headless generator driver from #217 is not on `dev` yet. When
  it lands, it must call `meta_harness.retry_state` rather than keep its own count, so both
  adapters share one implementation, as #218's acceptance criteria require.
- **Other in-tree state the hook trusts is out of scope here.** A forged
  `.meta-harness/last_green_state` makes the no-op guard (ADR-0016) skip the gate, and a
  future-dated `.meta-harness/hook_markers/stop-*` makes the dedupe claim yield; both exit 0
  silently. This ADR claims nothing about them.
