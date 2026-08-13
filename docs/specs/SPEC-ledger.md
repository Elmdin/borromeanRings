# SPEC — Effectiveness ledger (verdict history)

**Status:** Implemented · **Realized by:** `src/meta_harness/verdict.py` (history
persistence), `src/meta_harness/ledger.py`, `ledger.sh` · ADR-0047

## Problem
`status` shows whether a governed project is green *now*; it can't show whether the gate
has ever *caught anything*. A gate that is always green is indistinguishable, from the
outside, from one that is decorative. Answering "is borromeanRings effective here?" needs
a record of what the gate has done over time — not a point-in-time verdict, and not an
arbitrary score.

## Contract

### History persistence (`verdict.py`)
On every run, `verify.sh` appends the run's `Verdict` as one JSON line to
`.meta-harness/verdict_history.jsonl` (best-effort — a write failure never turns a PASS
into a FAIL; same guard as the last-verdict write).

- `append_history(project_root, verdict)` — append one line (creates dirs).
- `read_history(project_root) -> list[Verdict]` — all recorded verdicts, oldest first.
  Fail-soft: missing file → `[]`; blank / non-JSON / wrong-shape lines are skipped, never
  raises.

### Ledger view (`ledger.py` + `ledger.sh`)
`ledger.sh [PATH ...]` renders one row per governed project (discovery reuses
`status.discover_projects`; default root `$HOME`):

- **RUNS** — number of recorded gate runs.
- **CAUGHT** — how many of those runs failed, i.e. failures the gate caught (the
  evidence it is load-bearing).
- **STREAK** — the current consecutive pass (`green`) or fail (`red`) run count; `—`
  when there is no history.

Plus a one-line tally (`N governed · G with history · R gate runs · C failures caught`).
Read-only; always exits 0. Threshold-free.

## Guarantees
- **Reuses single sources of truth** — the gate's own `Verdict` for history,
  `discover_projects` for the roster. No duplicated policy.
- **Fail-soft** — a missing or partially-corrupt history degrades to `[]` / skipped
  lines; the ledger never crashes on bad data.
- **Pure core** — `summarize_history` and `render` are pure and fully unit-tested (the
  streak logic, failure counting, and rendering); only discovery and the file read touch
  I/O.
- **Threshold-free** — counts and a streak, never a blended effectiveness score.

## Dogfood
`verify.sh` on borromeanRings itself now appends to its own history every run; `ledger.sh`
renders the portfolio's recorded runs and failures-caught (e.g. spaceThink's caught
`12_secrets` failures once it has been re-gated).

## Deferred
Ratchet-baseline movement over time (how coverage/complexity/etc. tightened, from the git
history of the `.borromeanrings-*-baseline` files) composes on top of this and is a
follow-up, not part of v1.
