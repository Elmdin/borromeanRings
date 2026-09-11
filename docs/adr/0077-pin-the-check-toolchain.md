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
Pin exactly **what decides a verdict**, verify the pin against what the gate actually runs, and
leave the rest of the closure free.

1. `[project.optional-dependencies].dev` pins each tool with `==`, not `>=`.
2. Two transitive packages are named in `dev` as well, because they decide verdicts even though
   no check invokes them: `coverage`, which measures the ratchet, and `libcst`, which generates
   mutmut's mutants. Either one moving changes a score. Depending on them is real, so it is
   declared rather than inherited.
3. Everything else in the closure is left to resolve current. See the correction below.
4. `meta_harness.toolchain` holds the pure comparison, and a `TOOLS` table records each tool
   alongside **the argv the gate uses to reach it**. `tests/integration/test_toolchain_pins.py`
   observes each tool through that argv and fails closed on any mismatch, on an unreadable
   version, on any gate tool left unpinned, and on any `dev` requirement that is not exact. A
   separate test derives the tool set from `checks/**.sh`, so adding a tool to a check without
   pinning it fails the suite.

> **Corrected by CI before merge.** The first version of this decision pinned the **full resolved
> closure** (49 distributions) via a `constraints-dev.txt`. CI rejected it, and was right to.
> Freezing the closure to the maintainer's machine also froze `click`, `idna`, `msgpack` and
> `urllib3` at versions carrying known CVEs, and `70_pip_audit` went red naming all four. The
> local heavy lane had not caught it: `70_pip_audit` always fails locally on unrelated packages
> in a shared conda environment, so its signal was being discarded as noise.
>
> The lesson is that "pin everything" and "keep dependencies patched" are in direct conflict, and
> the tie-breaker is what the pin is *for*. A pin exists to stop the release calendar changing a
> verdict. Networking and CLI plumbing does not change a verdict; it only carries vulnerabilities
> forward. So the line is drawn at the deciders, and the constraints file was deleted.
>
> Accepting the CVEs through `[audit].ignore_vulns` was the other way out and was rejected: that
> is re-baselining a ratchet to make a check pass, which this project forbids on principle and
> which this ADR forbids by name two paragraphs below.
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
- **A full lockfile (`pip-tools`, `uv lock`), or a hand-written constraints file** — tried, then
  rejected on the evidence above: a frozen closure is a frozen set of vulnerabilities, and this
  repo has no mechanism that would ever refresh it. A lockfile is the right tool where something
  regenerates it on a schedule; nothing here does. That leaves
  [PR #170](https://github.com/Elmdin/borromeanRings/pull/170)'s `[supply_chain].lockfile`
  correctly set to `""` and `76_lockfile` an honest `noop`, which is the accurate report.
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
  re-introduce the unannounced-change problem. The cost is a periodic manual sweep, and
  `70_pip_audit` is what will force it — a pinned tool that develops a CVE turns the heavy lane
  red until someone moves the pin, which is the correct pressure.
- (−) The pinned tools are exempt from the floating-closure argument, so a CVE in `ruff` or
  `mutmut` itself blocks the gate rather than being patched silently. Accepted: a security fix to
  a verdict-deciding tool is exactly the kind of change that should arrive as a reviewed bump.
- (−) The pins record *this* machine's closure. A contributor on a different platform may find a
  version without a wheel for their Python. Exact pins are the safe case for a yanked release
  (PEP 592 still installs a yanked version when pinned exactly), but a platform mismatch would
  need the pin widened for that marker, deliberately.
- (−) Adding a dev dependency now requires pinning it. The integration test fails closed if it is
  not pinned, so the failure is loud rather than silent — it caught `html5lib>=1.1` arriving from
  #211 while this branch was open.
