# ADR-0062 — Application archetypes: required-feature gates, playbooks, and archetype-forced non-`noop`

**Status:** Accepted
**Spec:** `docs/specs/SPEC-archetypes.md`
**Refs:** #79 (epic), #130 §"honest problems", #138 (governance matrices), ADR-0049 (`noop`),
ADR-0010 (opt-in spine), ADR-0024 (profiler)

## Context

The gate decides *how well* code is written (build, lint, types, tests, security) and
*what engineering surround exists* (`[hygiene].requires`), and adjusts per language
(ADR-0015). It has no opinion on whether an application has what an app **of its kind**
must have. An agent asked for a web API ships something clean, typed and tested — with no
health endpoint, no structured logging, no auth mechanism — because nothing says what
"complete" means for that archetype (#79).

The governance matrices (#138) made the gap concrete: most rows of the SRE (#4), Data/ML
(#5) and Product/UX (#6) matrices are marked `archetype` — legitimately `noop` for a
library or CLI, and only *required* once a project says it is a service, an ML project or
a web app. And #130 raised the vacuity problem: a check that finds nothing to inspect emits
`noop`, which is non-failing by design (ADR-0049) — but for a declared web app, `15_a11y`
inspecting *no HTML at all* is precisely the hollow green the harness exists to catch. The
archetype declaration is what turns "inspected nothing" from legitimate into a failure.

The determinism question (#79) is the crux. "Does this API have *good* rate limiting?" is
not statically decidable. What is decidable is *declare-and-verify*: a required capability
either has a file/config artefact behind it or it does not.

## Decision

**1. A closed archetype vocabulary in the spine.** `[project].archetypes = [...]` (a list,
not a single `kind` — a CLI built on a library is both). The names live in
`spine.ARCHETYPES` because the spine is an architecture leaf (ADR-0027) and imports no
domain module; the catalog is keyed by exactly those names and a unit test binds the two.
An unknown name **fails closed at config time** (`load_config` raises), and `verify.sh` now
refuses a config the spine rejects instead of falling back to `python` and running checks
the verdict would refuse anyway. Hyphenated names follow the issue; the profiler's advisory
`PROFILES` keys stay a separate namespace.

**2. A catalog of binary, deterministic features (`meta_harness.archetypes`).** Immutable
data (frozen dataclasses), versioned (`CATALOG_VERSION`). A `Feature` is present when a
file matches one of its presence globs, or a file matching one of its content globs matches
a regex. Nothing else: no model, no network, no build, no execution. **If a requirement
cannot be decided that way it is not a feature** — it goes in the archetype's *playbook*,
the advisory prose the wrapped agent reads (the durable "what" stays in the gate; the
volatile "how" lives in the playbook and can change without a gate change). Every feature
cites the matrix row or issue that justifies it. Vendored/generated trees are never
evidence.

**3. `21_archetype` gates presence.** No archetypes ⇒ `noop` (rule off). Every required
feature present ⇒ `pass` with the evidence path per feature. Any absent ⇒ `fail`, listing
each. Per-project opt-in like every check; added to `adopt.py`'s `RECOMMENDED` because it
is inert until a project declares archetypes.

**4. An archetype can require a check to be non-`noop`.** Each archetype carries
`must_be_non_noop`. In `verify.sh`'s verdict block — the one place that sees every receipt —
`non_noop_violations()` turns the run FAIL for a listed check whose receipt is `noop`
(*"required to inspect something by archetype X"*), or which is absent from the expected
set (required-to-inspect implies required-to-run). This is the only override of a check's
own non-failing status, and it is driven by declaration, never inferred. A project without
archetypes gets an empty tuple: behaviour unchanged.

**5. `15_a11y` reports `noop` on no HTML** (it exited 0 as `pass` before). This is ADR-0049
applied, and it is what makes the `web-app` clause real: the integration test drives the
gate on a declared web app with no HTML and asserts every receipt is non-failing yet the
run is FAIL.

**6. This repo declares `archetypes = ["cli", "library"]`** and requires `21_archetype`.
The six features are true of it today with evidence (`adopt.sh:1` shebang, `README.md:21`
"Run the gate", `LICENSE`, `CHANGELOG.md`, `pyproject.toml`, `VERSION`); nothing was added
to make them pass. `00_build` and `40_test` are the checks it must keep non-`noop`.

## Alternatives considered

- **One global checklist** — rejected (#79): a CLI needs no rate limiter; an MCU does not
  allocate on the heap.
- **Playbooks only** — rejected: the harness turns standards into gates, not suggestions.
- **A behavioural half ("the health endpoint responds")** — deferred: needs a running
  process, belongs on the heavy lane once a governed service exists ("justified building").
- **Validating the vocabulary in `archetypes.py` and having the spine import it** —
  rejected: it breaks the spine's leaf contract (`35_architecture` would fail).
- **Failing `21_archetype` itself on a hollow check** — rejected: a check cannot see other
  checks' receipts; the verdict is the only honest place, and it keeps one owner for the
  pass/fail classification (`verdict.is_failing` + this clause).

## Consequences

- Matrix rows now backed by a deterministic feature (phase 1): O5 (positive half), O6, O7,
  O11, M1, M5, M6, M9 (recorded), M11, M12, M16, U10 (static half), U12 (declaration),
  U14 (static half), U17, and the `web-api` rows of #2 (input validation, auth, rate limit,
  error handling, secrets from environment). Rows that need a run, a browser or a baseline
  (M7, M8, M10, U13, U15, U16, O8, O9) are playbook-only and stay open under #79 / #157.
- A declared archetype makes the run stricter, never looser: a project that passed without
  a declaration still passes; one that declares `web-app` and has no HTML now fails until
  it either has HTML or stops claiming to be a web app.
- The catalog is data: adding a feature, retiring one, or moving a check into
  `must_be_non_noop` is a data edit plus a `CATALOG_VERSION` bump and a changelog entry.
- **Deferred (phase 2):** per-project relaxation with recorded rationale and catalog
  version pinning (#79 "flexibility"); the `embedded` archetype's `must_be_non_noop` joins
  `18_api_contracts` when #130 lands; a bundle-size ratchet (U12) and evaluation-receipt
  ratchets (M7/M8) once a governed project of that archetype exists.
- Known limitation, stated on purpose: content regexes are *declare-and-verify*, not
  proof — `rate_limiter_declared` proves a limiter is named, not that it is wired to every
  public route. The playbook says how; the gate says whether the declaration exists.
