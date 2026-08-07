# ADR-0044 — Container (Dockerfile) hygiene gate

**Status:** Accepted

## Context
borromeanRings governs *code* thoroughly, but a project that ships as a container
carries operational invariants no code check can see. The image runs as **root**
unless told otherwise (a least-privilege violation — our #2 value priority is
security); an unpinned base (`:latest`, or no tag) makes the build **non-reproducible**
and silently drifts; and a long-running service with **no `HEALTHCHECK`** gives an
orchestrator nothing to distinguish live from wedged. These are matrix **#4 (SRE /
operational)** concerns, and — unlike true DORA telemetry — each is a deterministic,
threshold-free fact derivable from the Dockerfile text.

Building this surfaced a real gap in borromeanRings's *own* image: its Dockerfile had
**no `USER`**, so the gate-runner ran as root. A container project already in the
roster (AutoApply, a local dashboard + CLI) is well-formed on non-root and pinned base
but declares **no HEALTHCHECK** — the exact justified-need this check targets.

## Decision
Add `14_container` + `meta_harness.container`: a native (stdlib) Dockerfile parse that
reports hygiene violations for a per-project rule set (`[container].require`):

- `non_root` — the **final** build stage must end on a `USER` that is not `root`/`0`
  (a non-root `USER` in an earlier build stage does not count).
- `pinned_base` — every *external* `FROM` (not an earlier-stage reference, not
  `scratch`, not a `$`-variable we can't resolve) must pin a non-`latest` tag or a
  digest.
- `healthcheck` — at least one `HEALTHCHECK` (not `HEALTHCHECK NONE`) is declared.

No Dockerfile at `[container].dockerfile` (default `Dockerfile`) ⇒ pass (not a
container project). Off unless `14_container` is in `[checks].required`. borromeanRings
fixes its own root container and dogfoods the two universal rules
(`require = ["non_root", "pinned_base"]`); the full set — including `healthcheck` — is
validated against AutoApply's real service Dockerfile, where it correctly flags the
missing HEALTHCHECK.

## Alternatives considered
- **Shell out to `hadolint`** — rejected as the gate's engine: it's an external
  binary (a new heavy-lane dependency and install surface) and its default rule set is
  broad/opinionated. The three rules here are the high-value, unambiguous core; a
  `hadolint` heavy-lane check remains a possible later addition, not a substitute.
- **Require `healthcheck` universally** — rejected as too blunt. A run-and-exit
  container (borromeanRings's own gate-runner; a batch job; a CLI) has no liveness to
  probe, and a meaningless `HEALTHCHECK true` is worse than none. Per-project
  `require` is the fix — the same lever the spine uses everywhere (empty/opt-in rules).
- **Digest-pin *required* (reject even a concrete tag)** — rejected as too strict for
  a first build; a concrete non-`latest` tag is a reasonable reproducibility floor,
  and forcing digests fights common base-image update workflows. Projects that want
  digest-only can layer that later.
- **Parse `docker-compose` / k8s manifests too** — deferred: those are separate
  surfaces (and healthcheck often lives in the orchestrator there). The Dockerfile is
  the single, always-present artifact for the container archetype; start there.

## Consequences
- (+) A container can no longer silently run as root or float its base image. borromeo
  dogfoods it on its own (now non-root) image; AutoApply gets a real, actionable
  finding (missing HEALTHCHECK) the moment it opts in.
- (+) Deterministic, threshold-free, native (no docker/hadolint), unit-tested (13
  cases incl. multi-stage, registry-port, digest, scratch, `$`-var, continuations) and
  adversarially verified (bad Dockerfile fails on all three; absent Dockerfile passes).
- (−) Static text analysis: it can't follow a `$`-variable base or judge whether a
  `HEALTHCHECK` command is *meaningful* — presence, not quality. That's the right floor
  for a deterministic gate; semantic judgment is a T2-critic concern, not this tier.
- (−) Opt-in and role-dependent: each project picks its `require` set. That's a feature
  (a gate-runner ≠ a service), but it means the check is only as good as the declared
  rules — omitting `14_container` entirely leaves the container ungoverned.
