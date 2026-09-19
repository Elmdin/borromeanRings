# ADR-0086 — The full test lane runs in parallel, and tests declare what they share

**Status:** Accepted · 2026-09-19 · issue #253 ·
**Relates to:** ADR-0081 (the fast interactive lane), ADR-0077 (pin the check toolchain),
ADR-0085 (lands with #254), ADR-0033 (heavy lane)

## Context

`40_test` hit the 900s per-check bound on `dev` after a dozen PRs merged, and #252 raised
the bound to 1800s so the queue could drain. Measured on `dev` @ 0220486: the suite takes
**18m 47s** serially, and the top 40 tests account for 451s of it — there is no single
offender to fix. The shape is a long tail: ~950 tests, most of the integration ones
building a fixture project and running the **real gate** against it, several seconds each.

That shape is deliberate. Those end-to-end tests are why the fail-open bugs of the last
two weeks were caught at all, and the project's own rule is that a test which proves the
gate's behaviour is worth more than a fast one that proves a function's. So the goal is
not fewer such tests. It is to stop paying for them one at a time.

## Decision

1. **The full lane runs the suite in parallel** when the governed project's environment
   has `pytest-xdist`: `pytest -n auto --dist loadgroup`. Measured on the same tree and
   machine: **3m 53s** with coverage, against 18m 47s serially, with identical results
   and identical 100% branch coverage.
2. **Absent `pytest-xdist`, the suite runs exactly as before.** The check asks whether
   the import succeeds and says in its log which way it ran. borromeanRings never
   requires a governed project to install anything (ADR-0068's rule for lane tools,
   applied here).
3. **The fast lane stays serial** (ADR-0081). It is already narrowed to the declared
   paths; worker start-up would cost more than it saves.
4. **Tests declare what they share.** Every test is given a scheduling group — its own
   module by default, so a file's tests and its module-scoped fixture project stay on one
   worker. A module that shares a resource with another declares a common
   `XDIST_GROUP`, and one worker runs both. `tests/_scheduling.py` holds the rule and
   `tests/conftest.py` applies it; a serial run ignores the marker entirely.
5. **`pytest-xdist==3.8.0` joins the pinned toolchain** (ADR-0077), bounded exactly like
   every other entry.
6. **`BORROMEANRINGS_TEST_WORKERS`** overrides the worker count for a machine where one
   worker per CPU is the wrong number.

The grouping rule is not theoretical. The first parallel run of this suite failed in two
places: `tests/integration/test_example_governed.py` and `test_harness_version_stamp.py`
both gate the *same* in-repo project (`examples/textkit`) and then read "the newest run
directory" out of it — side by side, each read the other's run. They now share a group.

## Alternatives considered

- **Share more fixtures; gate fewer projects.** Genuinely reduces total work rather than
  spreading it, and it is not excluded by this decision — `test_executor_conformance.py`
  already does it. Rejected as *the* answer: the duplication that remains is mostly
  between files testing different checks, so consolidating it would couple unrelated
  tests to one fixture project and make each of them prove less. Wall time would still
  be linear in the number of checks that must be gated end to end.
- **Let a test run only the checks it cares about.** The biggest single win available:
  `verify.sh` runs every check script in the lane, so a test about two supply-chain
  checks still pays for the rest. Rejected: "every registered check runs; only the
  required set decides the verdict" is a property these tests exist to prove (#229), and
  a test-only switch to skip checks would hollow out exactly the end-to-end fidelity
  that makes them worth their cost.
- **Mark the slow tests and skip them in the fast lane.** Already the case — ADR-0081's
  fast lane runs `tests/unit` only. It does nothing for CI, which must run everything.
- **Raise the bound again.** What #252 did, as a stopgap. A bound that only ever grows
  stops meaning anything; ADR-0085 (lands with #254) makes the growth visible, and this makes it
  unnecessary for now.
- **`--dist loadfile` instead of `loadgroup`.** Keeps a file together, which is most of
  the benefit, but gives no way for two files to say they share a resource — precisely
  the failure that appeared. `loadgroup` with a per-module default is `loadfile` plus
  that ability.

## Consequences

- (+) CI's `40_test` returns to a few minutes, well inside the original 900s bound, and
  the 1800s bound stops being load-bearing.
- (+) Local runs get the same speed-up, which is where the suite is actually painful.
- (+) A test that shares state with another must now say so. That is a real property of
  the suite, written down where the scheduler can act on it.
- (−) A test that assumes it is alone can now fail, and the failure looks like a flake.
  The grouping rule and this ADR are where that is explained; the two known cases are
  fixed and asserted.
- (−) One more pinned dev dependency, and a check that behaves differently depending on
  whether it is installed. The log says which way it ran, every run.
- (−) `-n auto` on a machine with many cores spawns many workers, each running gates.
  `BORROMEANRINGS_TEST_WORKERS` is the escape hatch.
