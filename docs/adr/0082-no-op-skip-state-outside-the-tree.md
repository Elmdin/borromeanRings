# ADR-0082 — The Stop hook's no-op skip must not rest on anything the project can write

**Status:** Accepted

## Context
The Stop hook skips the gate when the governed input state is byte-for-byte identical to the
state that last passed it — the content-hash-cache pattern. That is sound in principle: the
verdict is a deterministic function of the gated inputs, so an identical input set has an
identical verdict.

The implementation was not sound. `should_skip_gate` compared `compute_state_hash(project)`
against the text in `<project>/.meta-harness/last_green_state`, and:

- the hash is **unkeyed**, and the hashing function is in this repository;
- the record is **inside the governed tree**, which the agent writes to freely.

So an agent could compute the current hash itself — or simply `import compute_state_hash` —
write it to that file, and the hook would conclude "unchanged since the last green run" and
stand down. No secret, no cleverness: one file, on any tree, including a red one (#222,
route 1).

Two sibling routes reached the same exit:

- **Route 2** — `borromeanrings_claim stop … || exit 0` treats a recent marker under
  `.meta-harness/hook_markers/` as another hook instance already handling this event.
  `claim` compared `now - mtime` against the freshness window, so a marker dated in the
  *future* made that difference negative and compared as "fresh" **forever**. One
  `touch -d tomorrow` and the gate never ran again.
- **Route 3** — the hook's Python imported from the project directory, so a planted
  `meta_harness/` or `json.py` replaced the hook's own modules. Closed already by ADR-0080
  (`borromeanrings_py`, neutral cwd); this ADR adds the regression test that keeps it closed.

This is the same problem ADR-0079 solved for the retry count, one exit further along. #218
lets an agent *retry* more than it should; this let it skip verification entirely.

## Decision
**The last-green record lives beside the retry count, outside the governed tree**, at
`${XDG_STATE_HOME:-$HOME/.local/state}/borromeanrings/<digest>/last_green_state`, keyed by
the first 32 hex characters of the sha256 of the project's *resolved* absolute path.

- The location arithmetic moves to `meta_harness.state_home` — `state_root`,
  `project_digest`, `project_state_dir`, `StateUnavailable` — and `retry_state` re-exports
  those names. One module owns "where harness state lives"; neither consumer imports the
  other, so the module graph stays acyclic (`35_architecture`).
- **Fail closed, never fall back into the tree.** With no absolute `XDG_STATE_HOME` or
  `HOME`, `record_green` records nothing and `should_skip_gate` returns `False`. Failing to
  record costs one gate run; recording in the tree would cost the guarantee — and a
  fallback would restore the forgeable location on exactly the machines least able to
  notice it had happened.
- **An in-tree record is never read**, and a green run deletes it, so nobody later "fixes"
  the skip by reading it again.
- **A future-dated claim marker is not a claim.** `claim` now treats a negative age like a
  stale one: reclaim, refresh the mtime, proceed. No claimant can have started after now,
  so the only thing a future mtime can express is a forgery or a clock that already
  invalidates the window.

## Consequences
- The skip keeps its real purpose: a session that only answered a question still does not
  re-run a green gate.
- The record no longer travels with the project. Moving a checkout to a new absolute path,
  or to another machine, costs one gate run. That is the intended trade.
- Each of the three routes has a test that **first asserts the forgery is live** — that the
  planted artefact is exactly what the old code believed — and only then asserts the gate
  ran anyway. Verified by reverting the source fixes: routes 1 and 2 then exit 0 with empty
  stderr on a red tree.
- **What this must never be called.** It defeats an agent confined to the project directory
  — the realistic case, and the one the local feedback loop exists for. It is **not** a
  bound against intent: the gate runs the project's own test code as the user, and that
  code can reach `$HOME` like any same-user process. A real bound needs isolated execution
  (#144/#145). ADR-0079 states the same limit for the retry count; nothing here narrows it.

## Alternatives considered
- **Key the hash (HMAC) and keep the record in the tree.** The key must be readable by the
  hook, which runs as the same user, so it is readable by the agent. It raises the cost of
  the forgery from "write a file" to "read a file and write a file". Rejected: it buys
  little and reads as security.
- **Delete the skip.** It exists for a measured reason — the full lane is ~450s, and a turn
  that answered a question changes nothing the gate examines. Deleting it would make every
  Stop pay that. Rejected in favour of moving the record; ADR-0081's fast lane cuts the
  cost of the runs that do happen.
- **Store the record in the receipt directory instead.** Same tree, same problem.
