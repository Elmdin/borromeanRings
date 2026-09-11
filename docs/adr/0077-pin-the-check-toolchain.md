# ADR-0077 — Pin the check toolchain exactly (amends ADR-0008)

**Status:** Accepted

## Context
[ADR-0008](0008-ci-runs-the-gate.md) put the gate in CI so that "the same `verify.sh` should
produce the same verdict on a clean CI runner as on a developer laptop" (QAS-2). It considered
pinning exact tool versions and deferred it: *"lower-bound ranges for now; pin later if CI/local
drift causes a problem."* Its own consequences section named the risk it was accepting: *"a new
tool release could in principle change a verdict."*

The trigger fired. On 2026-09-10 two pull requests were red on GitHub while green locally, on the
same commits:

| PR | Failing check | Cause |
|---|---|---|
| #207 | `10_format` | `ruff` 0.15.8 locally, 0.16.7 in CI — the newer release reformats |
| #208 | `40_test` | `mypy` 1.19.1 locally, 2.3.1 in CI — a major version apart |

Every tool differed. `pytest` 9.0.3 against 9.1.1, `pip-audit` 2.10.0 against 2.10.1, `mutmut`
3.6.0 against 3.7.0, and transitively `coverage` 7.13.4 against 7.16.0. The gate was reporting a
property of the PyPI release calendar, not of the code.

Two further facts shaped the decision.

**An upper bound at the next major is not sufficient.** `78_pins` (ADR-0061, lands with #170)
requires every requirement to carry an upper bound, which would have caught the `mypy` major jump.
It would not have caught `ruff` 0.15.8 → 0.16.7, the one that actually turned #207 red: a
formatter's output is not a semantically versioned interface, so any release can change it. A tool
whose *output is the verdict* needs an exact pin, not a bound.

**Where a tool is read from is part of the guarantee.** The checks do not agree on how they reach
their tools: `10_format` runs `ruff` from `PATH`, `40_test` runs `python3 -m pytest`. On the
maintainer's machine those resolve to different installs of `pytest` (a user-site console script
at 9.0.2 shadowing site-packages at 9.0.3). A drift check reading `importlib.metadata` alone would
certify 9.0.3 while `10_format`-style `PATH` resolution could run something else entirely. So the
observation must mirror each check's own invocation.

## Decision
Pin the check toolchain exactly, verify the pin against what the gate actually runs, and record
the whole closure.

1. `[project.optional-dependencies].dev` pins each tool with `==`, not `>=`.
2. `constraints-dev.txt` pins the full resolved closure (49 distributions), including transitive
   tools like `coverage` that no direct requirement names but whose version moves a ratchet. CI
   installs with `pip install -e ".[dev]" -c constraints-dev.txt`.
3. `meta_harness.toolchain` holds the pure comparison, and a `TOOLS` table records each tool
   alongside **the argv the gate uses to reach it**. `tests/integration/test_toolchain_pins.py`
   observes each tool through that argv and fails closed on any mismatch, on an unreadable
   version, and on any gate tool left unpinned. A separate test derives the tool set from
   `checks/**.sh`, so adding a tool to a check without pinning it fails the suite.
4. CI prints the log of every check that did not pass. The gate's summary names the failing
   check but not the reason, and a runner discards the run dir; diagnosing the two failures above
   required reproducing them locally from scratch.

Moving a pin is a deliberate, reviewed change: bump it, run the heavy lane, and fix whatever the
new release flags **in the same PR**. Widening a pin to make a check pass is a re-baseline and is
not allowed.

## Alternatives considered
- **Upper bounds only (`>=x,<next-major`), as `78_pins` requires** — rejected as insufficient on
  the evidence above: it does not constrain a formatter's minor releases, which is the case that
  broke. Kept as the floor for *runtime* dependencies, where an exact pin would over-constrain
  consumers; the two rules compose rather than conflict.
- **A full lockfile (`pip-tools`, `uv lock`)** — rejected for now: both need a tool this project
  does not install, and `constraints-dev.txt` already pins the same closure with stdlib only. When
  [PR #170](https://github.com/Elmdin/borromeanRings/pull/170) lands, this file is the natural
  value for `[supply_chain].lockfile`, which turns `76_lockfile` from an honest `noop` into a real
  gate. Recorded so the follow-up is not lost.
- **Let CI float and pin only locally** — rejected: it inverts QAS-2. The clean-runner verdict is
  the authoritative one, so it is the one that must be reproducible.
- **Compare versions via `importlib.metadata`** — rejected: it reports what is importable, not
  what the gate executes, and those differ on a machine with a user-site shim.

## Consequences
- (+) The same commit gets the same verdict on a laptop and on a runner. QAS-2 becomes a tested
  property rather than an aspiration.
- (+) A toolchain change can no longer arrive unannounced in an unrelated PR; it arrives as a pin
  bump with its fallout handled in the same change.
- (+) `mutmut` is pinned at 3.6.0, the version whose `copy_src_dir` behaviour the stale-`mutants`
  workaround ([PR #199](https://github.com/Elmdin/borromeanRings/pull/199)) was written and
  verified against. CI had been running 3.7.0, so that workaround's justification and its runtime
  had silently come apart.
- (−) Pins go stale, and nothing here bumps them. That is deliberate: an automated bump would
  re-introduce the unannounced-change problem. The cost is a periodic manual sweep.
- (−) The pins record *this* machine's closure. A contributor on a different platform may find a
  version without a wheel for their Python. Exact pins are the safe case for a yanked release
  (PEP 592 still installs a yanked version when pinned exactly), but a platform mismatch would
  need the pin widened for that marker, deliberately.
- (−) `constraints-dev.txt` must be regenerated whenever a dependency is added. The integration
  test fails closed if it is not, so the failure is loud rather than silent.
