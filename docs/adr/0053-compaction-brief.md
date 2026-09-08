# ADR-0053: Governance state must survive compaction (PreCompact + SessionStart hooks)

**Status:** Accepted · 2026-09-08 · closes #137

## Context
borromeanRings wired four hook events. Context compaction is where a session's knowledge
of the last gate verdict, the obligations still open (a failing `13_adr`, a `17_prior_art`
that wants a survey, a hollow green) and the commit-identity policy is folded into a
summary that keeps or drops it at the summariser's discretion. That is the hollow-green
failure class (ADR-0049) one layer up: the evidence is intact on disk; the agent's
awareness of it is gone. The 2026-09-02 tooling survey listed this among its top five.

## Decision
1. A pure module `meta_harness.compaction_brief` renders a short, bounded, honest brief
   from the same evidence the self-status view reads.
2. `PreCompact` snapshots it to `.meta-harness/compaction_brief.txt` (the event cannot
   inject context; the snapshot is the record of what was known at compaction).
3. `SessionStart` with matcher `compact|resume` re-injects a **fresh** brief via stdout.
   Fresh, not the snapshot: a gate that ran in between must win.
4. Both are advisory (exit 0 always, never `blockCompaction`), inert outside a governed
   project, and listed in `HOOK_SCRIPTS`, so the self-status view reports partial wiring
   when either is missing. `init.sh`, `install-global.sh` and this repo's settings wire them.
5. Every other hook event was inventoried (`docs/HOOK-EVENTS.md`); the ones not wired own
   no borromeanRings state, or would duplicate an existing point.

## Consequences
- Post-compaction turns start from evidence, not from whatever the summary retained.
- Two more hook processes per compaction/resume (each a sub-second Python read).
- `SubagentStop` remains an open gap, recorded in the inventory rather than hidden.
- Enforcement mode now counts six events; older reports saying "4/4" are superseded.
