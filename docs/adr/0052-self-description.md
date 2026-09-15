# ADR-0052 — Capability self-description, generated from the registry

**Status:** Accepted · **Spec:** `docs/specs/SPEC-describe.md` · **Closes:** #132

## Context

Every AI summary of this project lists six to eight quality gates. The real surface is
~30 checks across six governance matrices, threshold-free ratchets, tamper-evident
receipts, an honest `noop` status, portfolio and effectiveness views, an adoption path
and advisory lanes. The truth exists — in the check registry, the policy spine, 50-odd
ADRs and `ENFORCEMENT-COVERAGE.md` — and nothing presents it. An agent reads the
README's "The checks (v0)" table of eight and stops.

This has the same shape as a hollow green: a true thing that is not surfaced. It also
has a concrete cost: the README's stated check count drifted three times in one cycle
("eight" → "nineteen" → "twenty"), and the handoff document managed to state an ADR
count that three readers each got differently wrong.

## Decision

**Generate the description from sources of truth; never write it.** `describe.sh`
renders a capability report whose every fact is traceable to a file:

- checks from the scripts on disk (`id=`/`cmd=`, with the `run_check` fallback for the
  five inline scripts; a script declaring neither is *reported as undeclared*, never
  silently dropped — omission is the drift this exists to stop);
- required/heavy membership from the spine; ratchets derived from the check's own
  description rather than listed by hand;
- decision count from `docs/adr/`; matrices parsed from `ENFORCEMENT-COVERAGE.md` §6,
  the one hand-maintained input and the matrices' single source;
- commands from the root scripts, skills from the installed directory names;
- `--readme` regenerates the README's describe block in place, so the numbers a reader
  sees are the registry's, not a hand edit.

**Guard the counts with a gate.** `04_self_description` fails closed when a count the
README states does not equal the registry — `**N checks**` against scripts on disk,
`(<word> gates` against `len(required)`. No stated count ⇒ `noop`. Equalities, not
targets: the maintainer's threshold-free rule holds because the number is *the* number,
not a goal.

**Point the agents at it.** The `borromeanrings-status` skill and `AGENTS.md` tell a
session to run `describe.sh` before summarising the project.

## Consequences

- A summary produced by an agent given only the repo can name every check and all six
  matrices, because the report does. The acceptance test asserts exactly that.
- The README can no longer quietly under-report: a stale count fails the gate.
- One hand-maintained input remains (the §6 matrix table). It is parsed, not
  transcribed, and its drift is a documented follow-up (regenerate §6 from the check
  registry once checks carry a `matrix=` declaration — not built here, to keep the
  change bounded).
