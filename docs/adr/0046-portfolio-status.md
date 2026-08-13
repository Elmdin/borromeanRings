# ADR-0046 — Portfolio status (roster health) command

**Status:** Accepted

## Context
borromeanRings governs invariants thoroughly *inside* a repo, but a maintainer running
it across a portfolio has **no view across repos**. Answering "which of my projects are
governed, what does each enforce, was the last gate green, has any drifted behind the
recommended set, and are any not even a git repo?" today requires `cd`-ing into each
project and running the gate by hand. That state is invisible and easy to lose track of
— the exact "I'm lost on which projects have it and whether it's working" problem this
addresses. Building it was motivated by a real ad-hoc sweep across 10 governed projects
that had to be scripted from scratch each time.

The gate already computes a fail-closed verdict every run, but persists nothing durable
beyond per-check receipts and the `last_green_state` hash — so there was no compact,
readable "last outcome" for an outside view to consume.

## Decision
Add two pieces:

- **`meta_harness.verdict`** — a compact `Verdict` record (`ok` + per-check statuses +
  run id + digest) that `verify.sh` persists **best-effort** to
  `.meta-harness/last_verdict.json` on every run (a write failure never turns a real
  PASS into a FAIL). Reads are fail-soft: absent/unreadable/malformed ⇒ `None`.
- **`meta_harness.status` + `status.sh`** — the roster view. It discovers governed
  projects (any dir with `borromeanrings.toml`, depth-bounded, vendor/cache pruned) and
  prints one row each: git-or-not, required-check count, last verdict
  (`pass`/`fail`/never-gated), config drift (uncommitted `borromeanrings.toml`), and
  adoption drift (recommended checks not yet required). `--run` re-gates each project
  first (authoritative, CI-usable exit code); the default read-only report always exits
  0 (it reports, it does not gate); `--list` prints paths.

It **reuses the single sources of truth** — `load_config` for the required set,
`plan_adoption`/`RECOMMENDED` (ADR-0041) for drift, and the gate's own persisted verdict
for health — so no policy is duplicated. A pure core (`build_status`, `render`) with a
thin impure shell (`gather`, `discover_projects`) keeps it fully unit-tested; the module
is a top-level consumer nothing imports, so the graph stays acyclic.

## Alternatives considered
- **Re-gate every project on every `status`** — rejected as the default: gating 10
  projects (test suites and all) is too slow for a glance-able dashboard, and a
  dashboard that's slow to run won't get run. Persist-and-read makes the common case
  instant; `--run` remains for when freshness matters. Standard CI-dashboard shape
  (show last run, refresh on demand).
- **A numeric "portfolio health score"** — rejected. A single blended number is exactly
  the arbitrary-metric gate borromeanRings refuses (no-absolute-target principle); it
  hides which project is red behind a vanity figure. The table names each project and
  its concrete state instead.
- **Extract the gate's verdict logic into a shared function and recompute from receipts
  in `status`** — deferred. Recomputing means re-reading and re-verifying every run
  dir's receipts from outside the gate — more coupling and duplicated verdict logic for
  little gain over reading one compact record the gate already knows. Persisting a
  summary is the smaller, lower-risk change to THE GATE (one guarded write, no change to
  how the verdict is computed).
- **A static roster config file listing project paths** — rejected as the primary
  source: it goes stale the moment a project is added/moved. Filesystem discovery
  (governed = has `borromeanrings.toml`) is self-maintaining; explicit path args remain
  available to scope or override.

## Consequences
- (+) One command answers "what's governed and is it green" across the whole portfolio,
  surfacing non-git repos (history checks fail closed there), stranded uncommitted
  adoption, and drift — no manual `cd`. Dogfooded on the maintainer's real 10-project
  portfolio (reproduces the manual sweep: 9/10 green, flags the one non-git repo).
- (+) The gate now leaves a durable, readable trace of its last outcome — useful beyond
  status (debugging, tooling) — at the cost of one best-effort file write.
- (−) The default view reports **last-known** state, which can be stale if a project
  changed since its last gate; `--run` is the authoritative mode. The table shows
  never-gated projects explicitly so stale-vs-fresh is never silently conflated.
- (−) Discovery walks the filesystem under the given roots (default `$HOME`); it is
  depth-bounded and prunes vendor/cache dirs, but a huge tree is still a walk. Passing
  explicit roots scopes it.
