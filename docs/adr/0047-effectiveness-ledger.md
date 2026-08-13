# ADR-0047 — Effectiveness ledger (verdict history)

**Status:** Accepted

## Context
`status` (ADR-0046) answers "is each governed project green *now*". It does not answer
the harder, more important question a maintainer eventually asks: **"is this governance
actually doing anything?"** A gate that is always green might be genuinely protecting a
clean codebase — or it might be decorative, never having caught a thing. Coverage and a
green verdict prove conformance at a point in time; they are not evidence of *impact over
time*. Without a record, "is borromeanRings effective?" can only be answered with
anecdotes ("it caught fire's missing lang once").

The gate already computes a verdict every run and (ADR-0046) persists the *last* one.
The material for an effectiveness record is therefore already produced — it just wasn't
being kept.

## Decision
Record an **append-only history** of every gate verdict and summarise it:

- **`verify.sh`** appends each run's `Verdict` as one JSON line to
  `.meta-harness/verdict_history.jsonl` (alongside the existing last-verdict write, same
  best-effort guard — a write failure never turns a PASS into a FAIL).
- **`meta_harness.verdict`** gains `append_history` / `read_history` (fail-soft: a
  missing file → `[]`, a malformed line is skipped, never raises).
- **`meta_harness.ledger` + `ledger.sh`** render, per project: how many times the gate
  **ran**, how many of those runs **caught a failure** (the evidence the gate is
  load-bearing), and the current pass/fail **streak**. Reuses `discover_projects`
  (status) and `read_history` (verdict); pure summary + rendering, unit-tested.

Threshold-free by construction — counts and a streak, no blended "effectiveness score".

## Alternatives considered
- **Infer effectiveness from git history / CI logs** — rejected: those are lossy,
  host-specific, and don't survive a squash or a runner rotation. A verdict history kept
  with the project is self-contained and portable, the same principle as receipts.
- **A single "effectiveness score" per project** — rejected for the usual reason
  (no-absolute-target): a blended number invites gaming and hides *what* was caught. Runs
  / failures-caught / streak are concrete and each independently meaningful.
- **Persist rich per-run detail (full logs, timings) in the history** — deferred: the
  compact `Verdict` (ok + per-check statuses) is enough to answer the effectiveness
  question and keeps the JSONL small and append-cheap. The receipts already hold the full
  per-run detail for the last run; deep history mining is a later concern.
- **Include ratchet-baseline movement (how coverage/complexity tightened over time)** —
  deferred to a follow-up: it's a genuinely different data source (git log of the
  `.borromeanrings-*-baseline` files) and composes cleanly on top of this once the
  verdict trend exists. Noted so it isn't silently dropped.

## Consequences
- (+) "Is borromeanRings doing anything here?" becomes a recorded, per-project fact
  (runs, failures caught, streak) instead of an anecdote — directly answering the
  effectiveness question `status` can't. The data starts accruing the moment this lands,
  which is why persistence is the time-sensitive half.
- (+) Reuses everything already built (the gate's verdict, `discover_projects`,
  `read_history`); pure core keeps it fully tested and low-coupling.
- (−) History only reflects runs made *after* this lands and is **local** to each
  checkout (`.meta-harness/` is git-ignored, like receipts) — it is a maintainer's
  local record, not a shared audit trail. A team-wide history would need a shared store
  (out of scope; the same locality trade-off receipts already make).
- (−) The file grows one line per gate run. It is compact JSONL and never read on the
  hot gate path (only by `ledger.sh` on demand), so unbounded-but-slow growth is
  acceptable; a rotation policy can be added if it ever matters.
