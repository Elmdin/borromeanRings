# Survey — reporting where a gate run's time went

**Question.** #253 asks the gate to say which check spent the run's time, after a 900s
bound fired on `dev` and was raised to 1800s with nothing in the run to say why. Did
anything in this repo, a declared dependency, or the ecosystem already report that?

## What already exists

| Where | What was found | Fit |
|---|---|---|
| This repo | `meta_harness.receipts` — `finalize_receipt`, `verify_receipt`. The per-check record and its tamper-evident hash. | **Extend, don't duplicate.** The duration belongs *in* the receipt, under the hash that already protects the rest of it; ADR-0085 says why a second, unsealed place would be worse than none. No new record type. |
| This repo | `meta_harness.ledger` — per-project gate runs, failures caught, pass/fail streak, from the recorded verdict history. | **Not a fit, and adjacent.** It answers "is the gate catching anything", over many runs; this answers "where did *this* run's time go". The ledger reads verdict history, which has no timings; if a trend view is wanted later, it should read the receipts this PR writes rather than grow its own clock. |
| This repo | `checks/_lib.sh` — `borromeanrings_run_bounded`, which already times a check to *enforce* `BORROMEANRINGS_CHECK_TIMEOUT`. | **Not reusable as-is, and the reason is the point.** It measures to kill, bounding one command inside a check, and reports nothing when the command survives. The bound is what fired here; what was missing was the measurement behind it. |
| This repo | `meta_harness.executor` — `DURATION_MASK`, `canonicalise_log`. Masks `\b\d+\.\d+s\b` in logs so two honest runs compare equal. | **Confirms the shape of the answer, and was updated.** The project already treats a duration as run-local noise for comparison; `duration_ms` joins `VOLATILE_FIELDS` for the same reason. |
| A declared dependency | `pytest` `--durations=N`. Ranks the slowest tests of a run. | **Reuse where it applies, not as the answer.** It covers one check (`40_test`) in one language lane; the next surprise will be elsewhere. ADR-0085 keeps it available inside that check. |
| Python standard library | `time.monotonic`, `datetime.timedelta`, `str(timedelta)`. | **Used for the clock, not the wording.** The measurement is taken in bash (the checks are shell), so the stdlib clock is not reachable at the point of measurement; `timedelta`'s `0:01:32.400000` is not what the one-line report should read like. |
| Ecosystem | `humanize`, `pytimeparse`, `rich`'s time formatters (advisory — no key-free search exists; ADR-0051). | **Not a fit.** Roughly 25 lines here, against a new runtime dependency in a project whose toolchain is pinned exactly (ADR-0077) and whose gate must run with nothing installed beyond that pin. The formatting rule is also specific: tenths under a minute, `m ss` above. |

## Decision

**Build**, and it is small: one module of pure functions (`format_duration_ms`,
`slowest`, `timings_line`) over a field added to a record that already exists. The
capability nothing here had was *recording* the duration where it can be trusted — the
receipt, under its hash. Once it is recorded, ranking and rendering it is a few lines,
and a dependency for them would cost more than it saves. The parts that did exist are
reused rather than re-implemented: the receipt and its digest, and the executor's
existing treatment of durations as run-local.

## Sources

- `grep -rn "duration\|timedelta\|humanize" src/ checks/` — the repo's existing clocks.
- `docs/adr/0026-tamper-evident-receipts.md`, `docs/adr/0077-pin-the-check-toolchain.md`,
  `docs/adr/0051-*` (key-free ecosystem search), `docs/specs/SPEC-executor.md` §5.2.
- `pytest --durations=40 tests` on `dev` @ 0220486 — the run that produced the numbers in
  #253.
