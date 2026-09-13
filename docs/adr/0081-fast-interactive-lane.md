# ADR-0081 — A fast (interactive) lane, so the Stop gate is not the whole test suite

**Status:** Accepted

## Context
`.claude/hooks/stop_gate.sh` ran `verify.sh` — the full required set — on every Stop where
the gated state changed. Measured on `origin/dev` (#226):

| | measured |
|---|---|
| full gate, wall clock | 445 s |
| `40_test` alone | 404 s — **91% of the gate** |
| every other required check combined | ~41 s |
| `tests/unit` alone | 3 s |
| `tests/integration` (24 files, subprocess gate runs) | ~400 s |
| pytest without coverage | 400 s (coverage is ~11%, not the cause) |

So an agent that edited anything waited over seven minutes before it could report finished,
and `CAP=3` retries put the worst case near 22 minutes in one session. The second-order cost
is larger than the latency: when the gate fires, attention moves off the user's task and onto
whatever the full suite surfaced, including pre-existing failures unrelated to the change.

The verification was not wrong, only mis-placed. A whole test suite belongs on the path where
nothing is blocked on it — pre-merge and CI.

## Decision
`verify.sh --fast` is a third lane beside the default full lane and `--heavy` (ADR-0033). It
runs the **same required check set**; it only exports `BORROMEANRINGS_LANE=fast`, which lets a
check narrow its scope to what the project declared. One check reads it today: `40_test` runs
only the paths in `[test].fast_paths` (new `Config.test_fast_paths`), without `--cov`. The Stop
hook runs this lane. This repo declares `fast_paths = ["tests/unit"]`.

`meta_harness.lane` owns every lane decision — precedence, path validation, the labels — so the
shell asks a question instead of reproducing policy.

Empty `fast_paths` (the default) means **no fast lane**: `--fast` then runs exactly what the
full lane runs. Nothing changes for a project that configures nothing. `--heavy` always wins
over `--fast`: heavy *is* the pre-merge lane and must never be narrowed.

### The honesty requirement
Speed bought by a silently weaker verdict would be worse than the slow gate. A fast-lane pass is
therefore labelled as one in four places, all asserted by tests:

1. the gate's verdict line — `RESULT: PASS (FAST LANE)`, followed by `FAST_LANE_NOTE`, which
   names what was skipped and where it is caught;
2. the check's row — `40_test  PASS (FAST LANE — only tests/unit; full suite pre-merge)`;
3. the receipt — `lane: "fast"`, `fast_paths`, and a `summary`, and **no** `coverage_percent`
   (a subset's coverage is not the project's coverage);
4. the persisted `last_verdict.json` — `lane: "fast"` — so a status view reading evidence after
   the console has scrolled away still sees a partial green as partial.

The label follows the verification that happened, not the flag that was typed: `--fast` in a
project with no declared paths reports as a full run, because it *was* one.

### What the fast lane does not catch, and where it is caught
- **Tests outside `fast_paths`.** Here: `tests/integration` (24 files, ~400 s) and `tests/e2e`.
  Caught by `./verify.sh` (full lane), by `./verify.sh --heavy`, and by CI on every push/PR —
  CI is unchanged by this ADR and still runs everything it ran before.
- **Coverage regression.** The ratchet needs a whole-suite number; it is not evaluated on the
  fast lane and the baseline is never written there. Caught on the full lane and in CI.
- Nothing else. Every other required check runs in full on the fast lane (~41 s total, of which
  `16_shellcheck` is 3 s), because the measurements say they are not the problem.

`record_green` still records a fast-lane green, and only `stop_gate.sh` reads that marker — to
skip a redundant *fast* gate. No full-lane or CI decision consults it, so a fast green cannot
stand in for a full one anywhere.

## Alternatives
- **Drop `40_test` from the interactive lane entirely** (#226's option 1). Rejected: an agent
  could then finish a turn with the code it just wrote untested. The unit suite is 3 s; at that
  price, keeping a real test signal in the loop is nearly free.
- **Run the suite without `--cov`** (option 2). Rejected on the measurement: 400 s vs 404 s.
  Coverage is ~11% of the cost, so this buys 1% of the gate.
- **Select tests affected by the changed files** (option 3). Rejected for now: it needs an
  import-graph-to-test mapping, is only as honest as that mapping, and would have to fail open
  (run everything) whenever the mapping is unsure — which is most edits to shared modules. A
  declared path list is legible, auditable, and a project can widen it. Revisit if the declared
  fast set itself grows slow.
- **A per-check `fast` flag in `[checks]`, like `heavy`.** Rejected as over-engineering today:
  every non-test check is ~0 s, so a mechanism for dropping checks would add config surface and
  a second way for a lane to under-verify, with no measured gain. `40_test` is the whole problem.

## Consequences
- The Stop gate on this repo goes from 445 s to ~12 s: the whole point.
- A failing integration test is now surfaced at `./verify.sh`, PR time, or CI rather than on the
  turn that broke it. That is the trade being made, and it is the trade CI exists for.
- Projects governed by borromeanRings opt in by declaring `[test].fast_paths`; until they do,
  their gate behaves exactly as it does today.
