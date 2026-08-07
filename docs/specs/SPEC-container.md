# SPEC — Container (Dockerfile) hygiene gate

**Status:** Implemented · **Realized by:** `src/meta_harness/container.py`,
`checks/shared/14_container.sh` · ADR-0044

## Problem
A project shipped as a container carries operational invariants no *code* check covers:
it should run non-root (least privilege), pin its base image (reproducible builds), and
— for a long-running service — declare a HEALTHCHECK. This is the deterministic,
threshold-free slice of the SRE/operational matrix (#4); true DORA/flow telemetry is
out of scope (it needs deploy history borromeanRings doesn't collect).

## Contract
`14_container` reads the Dockerfile at `[container].dockerfile` (default `Dockerfile`,
relative to the project root) and fails closed on any violation among the enforced
rules `[container].require` (default all three):

1. **`non_root`** — the **final** build stage must end on a `USER` that is not
   `root`/`0`. No `USER` in the final stage ⇒ root ⇒ violation. A non-root `USER` in an
   earlier build stage does not satisfy it.
2. **`pinned_base`** — every *external* `FROM` must pin a non-`latest` tag or a digest
   (`@sha256:...`). Skipped: a `FROM` referencing an earlier stage alias, `scratch`
   (self-pinned), and a `$`-variable base (can't be resolved statically). A registry
   `host:port` is not mistaken for a tag (tag = `:` after the last `/`).
3. **`healthcheck`** — at least one `HEALTHCHECK` other than `HEALTHCHECK NONE`.

No Dockerfile at the declared path ⇒ **pass** (not a container project). Off unless
`14_container` is in `[checks].required`.

Config `[container]`: `dockerfile` (default `Dockerfile`), `require` (default
`["non_root", "pinned_base", "healthcheck"]`).

## Guarantees
- **Deterministic & native** — stdlib Dockerfile parse (line-continuations, comments,
  multi-stage, case-insensitive instructions); no docker/hadolint dependency.
- **Threshold-free** — each rule is a yes/no fact; no arbitrary size/count target.
- **Role-aware** — `require` lets a run-and-exit gate-runner omit `healthcheck` while a
  service keeps the full set. borromeanRings's own gate-runner uses
  `["non_root", "pinned_base"]`.
- **Right floor** — presence, not quality (it doesn't judge whether a HEALTHCHECK
  command is meaningful — that's a T2-critic concern). Unit-tested (13 cases) +
  adversarially verified (bad Dockerfile fails all three; absent Dockerfile passes).

## Dogfood
- **borromeanRings** (`require = ["non_root", "pinned_base"]`) — its own Dockerfile was
  root (no `USER`); this build adds a non-root `USER` so it passes. Pinned base already
  held.
- **AutoApply** (a service; full rule set) — passes non-root + pinned, correctly flags
  the missing HEALTHCHECK (the justified need this check was built for).
