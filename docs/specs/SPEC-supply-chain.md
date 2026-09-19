# SPEC — Supply-chain hardening: lockfile integrity, pinned dependencies, SBOM

**Status:** Implemented · **Realized by:** `src/meta_harness/supply_chain.py`,
`src/meta_harness/sbom.py`, `checks/ci/76_lockfile.sh`, `checks/ci/78_pins.sh`, `sbom.sh` ·
ADR-0061 · Issue #58 · Matrix #2 rows S6, S8 (S7, S9 deferred — see the ADR)

## Problem
Dependencies were declared but never *held*: a `>=`-only requirement floats to whatever
the index serves tomorrow; a lockfile, where one exists, can silently drift from the
manifest that is supposed to generate it; and nothing produced a machine-readable
inventory of what actually ships. All three are text facts derivable from the repo —
threshold-free, deterministic, no network — and belong on the gate, not in a checklist.

## Contract

### 1. `76_lockfile` — lockfile integrity (heavy lane)
Config `[supply_chain]`: `lockfile` (default `""`), `manifests` (default
`["pyproject.toml", "package.json"]`).

| Situation | Receipt |
|---|---|
| `lockfile` empty | **noop** — "no [supply_chain].lockfile declared" (honest: rule off) |
| declared `lockfile` does not exist | **fail** — a misconfiguration never reads as "nothing to check" |
| project is not a git repository | **fail** — cannot tell what changed (12_secrets doctrine) |
| no base branch (`origin/dev`, `dev`, `origin/main`, `main`) to diff against | **noop** — same as `13_adr` |
| `git diff` against the merge-base fails inside a repo | **fail**, log says "failing closed" |
| no manifest changed relative to the merge-base | **pass** |
| a manifest changed **and** the lockfile changed | **pass** |
| a manifest changed and the lockfile did **not** | **fail**, naming every changed manifest and the lockfile |

"Changed" = committed since the merge-base **or** modified in the working tree **or**
untracked (a freshly generated, not-yet-added lockfile counts). Paths are compared after
stripping a leading `./`.

### 2. `78_pins` — pinned dependencies (heavy lane)
Config `[supply_chain].pin_optional` (default `false`). Reads `pyproject.toml`
`[project].dependencies`, plus every `[project.optional-dependencies]` group when
`pin_optional = true`. **Binary per requirement** — there is no ratio, no score:

- **pinned**: the specifier carries at least one of `==`, `===`, `~=`, `<`, `<=`
  (so `>=0.6,<1`, `~=0.6`, `==0.6.*` all pass); a direct URL is pinned only by a commit
  hash (`@<7–40 hex>`) or a `#sha256=` fragment;
- **unpinned** (one finding per line, quoting the exact requirement + the reason): a bare
  name; a specifier containing only `>=` / `>` / `!=`; an unparseable clause or
  requirement; a URL with a branch/tag or no ref.

| Situation | Receipt |
|---|---|
| no `pyproject.toml` | **noop** |
| zero requirements in scope | **noop** ("no runtime [+ optional] dependencies declared") |
| `[project].dynamic` contains `dependencies` | **fail** — the check was required but cannot see them; declare statically or drop the check |
| malformed TOML / dependency table not a list of strings | **fail** (fail-closed) |
| any finding | **fail**, every line listed |
| otherwise | **pass** ("all N declared requirement(s) are pinned or bounded above") |

`package.json` is **not** judged for pins (npm's `^`/`~` ranges are the lockfile's job —
`76_lockfile` covers that side).

### 3. `sbom.sh` — CycloneDX-shaped SBOM (entry point, not a gate)
`./sbom.sh [MANIFEST=pyproject.toml] [--optional] [--out FILE]` prints CycloneDX **1.5**
JSON of the declared dependency closure, resolved through `importlib.metadata` of the
**current environment**. Stdlib only, no network, exit `0` ok / `1` unreadable manifest /
`2` usage.

Pinned shape (unit-tested):
```
bomFormat = "CycloneDX"      specVersion = "1.5"      version = 1
serialNumber = "urn:uuid:<uuid5 of the closure>"          (no timestamp — deterministic)
metadata.component = {type: application, name, version, purl, bom-ref}
metadata.properties = [borromeanrings:attestation = none, borromeanrings:signed = false,
                       borromeanrings:unresolved = "a, b" (only when something is unresolved)]
components[] = {type: library, name, version, purl = "pkg:pypi/<name>@<version>", bom-ref}
dependencies[] = {ref, dependsOn[]}   (the application first, then each component)
```
Names are PEP 503-normalized. Closure rules: `Requires-Dist` lines with an `extra ==`
marker are not followed; a requirement with an environment marker that is not installed
is skipped as conditional; an **unconditional** requirement that is not installed is
reported under `borromeanrings:unresolved` — never dropped silently. The document says
in its own metadata that it is **not signed or attested**.

## Guarantees
- **Deterministic & native** — `tomllib`, `re`, `importlib.metadata`, `uuid`; no
  `packaging`, no network, no external tool, no new dependency.
- **Threshold-free** — every decision is per-file or per-requirement yes/no.
- **Honest about nothing** — every "nothing to inspect" path is a `noop` receipt
  (ADR-0049); every "cannot inspect" path is a `fail`.
- **Pure decision logic** — `supply_chain.py` and `sbom.py` are 100 % line- and
  branch-covered; the shell scripts only gather git/file facts and map a result to a
  receipt. Integration tests drive the real `verify.sh --heavy` on fixture repos.

## Dogfood — this repository
- `[supply_chain].lockfile = ""` → `76_lockfile` is **noop**. borromeanRings has **no
  lockfile**: it is a source-installed tool whose only dependencies are the dev toolchain,
  and no maintainer tooling produces one. Inventing a lockfile that nothing regenerates
  would be exactly the stale-lock hazard this check exists to catch.
- `pin_optional = true` → the `dev` group is judged (it *is* this project's supply chain:
  every check parses those tools' output). All eight entries were `>=`-only and now carry
  an upper bound at the next major.
- `./sbom.sh --optional` on a `pip install -e ".[dev]"` environment yields ~50 components,
  none unresolved.
