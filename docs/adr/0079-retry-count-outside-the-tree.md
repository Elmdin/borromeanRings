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

The correction on #218 separated two adversaries that the first argument had merged:

- a **same-tree** adversary: a wrapped coding agent, confined to the project directory by
  its tooling rather than by its user account. This is the realistic one.
- a **same-user** adversary: anything running under the user's account, with no reason to
  stay inside the project.

## Decision
**The count lives at `${XDG_STATE_HOME:-$HOME/.local/state}/borromeanrings/<digest>/stop_attempts/<session>`**,
where `<digest>` is the first 32 hex characters of the sha256 of the project's *resolved*
absolute path.

- The derivation and every decision — where the count lives, how much it is, retry or
  escalate, the migration below — live in `meta_harness.retry_state`: pure functions plus
  thin, injected I/O, unit-tested to 100% line and branch coverage. `stop_gate.sh` only
  dispatches on the one line it prints (`retry N`, `escalate N`, anything else).
- **Keyless.** No secret, no key file, nothing to leak or read back.
- **Resolved path.** A project reached through a symlink shares its count with the real
  path. Otherwise a second route to the same project would be a second, fresh budget.
- **Session ids** that are not plain `[A-Za-z0-9_-]{1,128}` are hashed into the filename,
  so a hostile id cannot walk out of the counter directory. The payload is untrusted input.
- **Private.** The borromeanRings-owned directories are created `0700`.
- **The helper cannot be shadowed from the tree.** `python3 -` puts the working directory,
  which is the project, first on `sys.path`. The hook strips it before importing, otherwise
  a planted `meta_harness/` package in the project would replace the counter logic.
- **Fail closed.** No absolute `XDG_STATE_HOME` or `HOME`, a state root that is a file or
  unwritable, an unreadable or corrupt counter: each yields `unrecorded`, and the hook
  escalates to the human on that Stop, printing the gate failure and the reason. Treating
  an unrecordable count as zero would make every Stop attempt 1, which is the unbounded
  loop the bound exists to stop. There is no fallback to the in-tree location.

### What this buys, and what it does not
- **It defeats the same-tree adversary for the retry count.** Deleting the counter file,
  deleting `.meta-harness/stop_attempts/` or all of `.meta-harness/`, writing `0` there,
  and writing `0` while restoring the mtime with `os.utime` all leave the bound intact.
  `tests/integration/test_retry_bound_reset.py` runs every one of those routes, plus the
  shadow-module route, and each asserts the attack changed something before asserting that
  the bound held.
- **It does not defeat a same-user adversary.** Anything running as the user can write
  the state directory and reset the count by the same four routes. The same test file pins
  that as a control rather than hiding it. Closing it needs storage the user cannot reach,
  meaning a privileged executor, which is a different design (#218, option 2).
- So this is more than *a speed bump against accident*, because it stops the adversary the
  hook actually faces. It is still *not a bound against intent*: an agent that deliberately
  goes looking outside its project can find the count and reset it.
- **Self-governance is weaker.** When borromeanRings governs its own repository, the hook
  and `meta_harness/` are themselves inside the tree, and an agent there can edit the code
  that keeps the count. The same-tree claim holds for a project that references
  borromeanRings from outside (ADR-0013), not for borromeanRings governing itself.

### Migration from the in-tree counter
A project upgraded mid-retry has a count in `.meta-harness/stop_attempts/<session>`. On the
next failure the hook reads it, takes `max(out-of-tree count, in-tree count)`, records the
result out of tree, and then removes the in-tree file (and its directory once empty). A
passing gate removes both.

Why `max` and not "import once, then ignore": the in-tree location can then only ever
*raise* a count, never lower it, so there is no window in which an agent that writes `0`
there gains anything. Garbage or unreadable in-tree content counts as `0`, again because it
can only raise. The in-tree file is removed only after the out-of-tree write succeeds, so a
failed write never loses the count it was carrying. The one thing an agent can still do
through the old location is write a large number and escalate early. That hands control to
the human with the failing gate on screen, which is the fail-safe direction.

## Alternatives considered
- **An evidence guard over the in-tree counter** (content hash, `lstat` coverage, the #217
  approach). Rejected: detection inside the tree is same-user writable, and the #217 review
  defeated its history anchor with one forged append, the file's own sanctioned operation.
- **An authenticator or monotonic counter in the tree.** Rejected: both need something the
  agent cannot read or reach, and the tree has nothing of the kind.
- **A privileged executor holding the count.** The only design that defeats a same-user
  adversary. Deferred: it is a much larger change to how the hook runs.
- **Document the limit and keep the bound advisory** (the state before this ADR). Rejected
  because a cheap step defeats the realistic adversary.

## Consequences
- (+) An in-tree agent can no longer reset the retry bound by any route it has.
- (+) Fails closed and loudly when the count cannot be kept.
- (−) **State outside the repository.** A governed project's retry history can no longer be
  read by opening the repository. The count is short-lived (one session's failures, cleared
  on a pass or an escalation), so little is lost, but it is a trade this project had
  otherwise avoided, made here on purpose.
- (−) Escalation is still not a durable record: the count is removed when it escalates,
  as before. A durable escalation log would be a separate, append-only file in the same
  state directory.
- **Still open on #218.** The headless generator driver from #217 is not on `dev` yet. When
  it lands, it must call `meta_harness.retry_state` rather than keep its own count, so both
  adapters share one implementation, as #218's acceptance criteria require.
- **Other same-tree routes remain, and they skip the gate outright rather than resetting
  the count.** The count is now safe, but the hook still trusts other in-tree state: a
  forged `.meta-harness/last_green_state` makes the no-op guard (ADR-0016) skip the gate,
  and a future-dated `.meta-harness/hook_markers/stop-*` makes the dedupe claim yield. Both
  exit 0 silently. The hook's other `python3 -` calls can also be shadowed from the tree.
  They need the same treatment and are tracked separately. This ADR claims nothing about
  them.
