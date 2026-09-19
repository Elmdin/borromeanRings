# ADR-0061 — Supply-chain hardening: lockfile integrity, pinned dependencies, SBOM

**Status:** Accepted (the CI-dependent items below are **deferred to the maintainer**)
**Spec:** `docs/specs/SPEC-supply-chain.md`
**Issue:** #58 · **Matrix:** #2 (security & compliance) rows S6–S9

## Context

Issue #58 asks for pinned/locked dependencies, Dependabot, `pip-audit` in CI, and a
review note on the executable supply chain (skills/hooks). Matrix #2 refines that into
four rows: an SBOM matching the declared closure (S6), attested build provenance (S7),
pinned dependencies + a lockfile whose integrity the gate checks (S8), and configured
dependency-update proposals (S9).

Two of those were already covered when this ADR was written: `70_pip_audit` runs
pip-audit on the heavy lane (ADR-0034), and #52 puts every shell script under a static
linter (ADR-0050, in flight on `feat/shellcheck-gate` — the "review skills/hooks for
unsafe patterns" half of #58).
What remained was the dependency *declaration* side — and a constraint from the
maintainer that shapes this build: **no new GitHub Actions workflows, no growth of
`verify.yml`, no publishing/packaging steps, nothing that phones home beyond the
existing pip-audit lookup.** Anything that needs CI or a remote service is a maintainer
decision, documented here with the exact config, not added.

Facts about this repository that the decision had to respect:

- It has **no lockfile** and no tooling that produces one. CI runs
  `pip install -e ".[dev]"`; there is no `uv.lock`, `poetry.lock` or `requirements.lock`.
- Its only dependencies are the **dev toolchain** (`[project.optional-dependencies].dev`),
  every entry of which was `>=`-only. Those tools *are* the supply chain of a gate that
  parses their output and exit codes.
- The maintainer rejects arbitrary numeric targets (ADR-0006 lineage; HANDOFF §3).

## Decision

**1. `76_lockfile` — lockfile integrity as a heavy-lane check.** If the project declares
`[supply_chain].lockfile`, a dependency manifest (`pyproject.toml`, `package.json`;
configurable) that changed relative to the merge-base without the lockfile changing
**fails**, naming both. Working-tree and untracked changes count. No lockfile declared
⇒ `noop`. Declared-but-missing lockfile, non-git project, or a git error inside a repo
⇒ **fail** (the 12_secrets doctrine: "cannot tell" is never "nothing to tell"). No base
branch ⇒ `noop`, as `13_adr` does.

**2. `78_pins` — pinned dependencies, binary per requirement.** Every requirement in
`[project].dependencies` (plus optional groups when `[supply_chain].pin_optional = true`)
must carry `==`, `===`, `~=`, `<` or `<=`; a direct URL must carry a commit hash or a
`sha256=` fragment. Each unpinned line is reported verbatim with its reason. Zero
requirements ⇒ `noop`; `dynamic = ["dependencies"]` or malformed TOML ⇒ **fail**.
There is no ratio and no score — threshold-free by construction.

**3. `sbom.sh` — a CycloneDX 1.5 document from the stdlib.** `tomllib` reads the
declared roots; `importlib.metadata` walks `Requires-Dist` through the *installed*
closure; `uuid5` of the closure is the serial number (no timestamp ⇒ deterministic).
Unresolved unconditional requirements are listed in `metadata.properties`, never
dropped. The document states `borromeanrings:attestation = none` and
`borromeanrings:signed = false`: it is an inventory, not provenance.

**4. Applied to this repository.** `[supply_chain].lockfile = ""` with the reason in
the config comment (no lockfile exists; inventing one that nothing regenerates would be
the stale-lock hazard itself). `pin_optional = true`, and all eight dev requirements now
carry an upper bound at the next major. Both checks are in `[checks].heavy`.

**5. Not added to `adopt.py`'s RECOMMENDED set.** RECOMMENDED writes into
`[checks].required` (the fast lane); a `checks/ci/` script never produces a receipt on
the fast lane, so recommending a heavy check there would make every adopter's gate
fail with `MISSING`. The heavy lane is adopted deliberately (its existing policy, ADR-0041).
Governed projects **should** add both to `[checks].heavy` — `76_lockfile` wherever a
lockfile exists, `78_pins` for any project with runtime dependencies.

## Deferred to the maintainer (needs CI or a remote service)

Each item below is what the matrix row asks for, why it cannot be built under the
constraint, and the exact configuration the maintainer would add. None of it is
committed by this ADR.

### S9 — Dependabot (automated dependency-update proposals)
Needs GitHub to act on the repo (a remote service; creates PRs). File to add:
`.github/dependabot.yml`
```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
    labels: ["dependencies", "security"]
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    labels: ["dependencies", "ci"]
```
With `78_pins` in place, every Dependabot bump that crosses an upper bound will be a
*visible* PR that fails the gate until the bound is moved deliberately — which is the
intended interaction, not a conflict.

### S7 — Build provenance / signed releases (SLSA, Sigstore)
Needs a CI build that signs. There is no release workflow today and `verify.yml` may not
grow jobs. When the maintainer decides to publish releases, the SLSA generic generator
is the smallest correct step (new file `.github/workflows/release.yml`, on `push: tags`):
```yaml
name: release
on:
  push:
    tags: ["v*"]
permissions:
  contents: write
  id-token: write   # OIDC for Sigstore / SLSA
jobs:
  build:
    runs-on: ubuntu-latest
    outputs:
      hashes: ${{ steps.hash.outputs.hashes }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install build && python -m build
      - run: ./sbom.sh --optional --out dist/sbom.cdx.json
      - id: hash
        run: echo "hashes=$(sha256sum dist/* | base64 -w0)" >> "$GITHUB_OUTPUT"
      - uses: actions/upload-artifact@v4
        with: { name: dist, path: dist/ }
  provenance:
    needs: [build]
    permissions:
      actions: read
      id-token: write
      contents: write
    uses: slsa-framework/slsa-github-generator/.github/workflows/generator_generic_slsa3.yml@v2.0.0
    with:
      base64-subjects: ${{ needs.build.outputs.hashes }}
      upload-assets: true
```
This yields SLSA Build L3 provenance for the wheel/sdist **and** the SBOM
(`sbom.cdx.json` is one of the signed subjects). The generator's tag should be pinned
to a commit SHA per the pinned-actions rule below. Until this exists, the SBOM is
unsigned and says so.

### Pinned GitHub Actions (Scorecard `Pinned-Dependencies`, actions half)
`verify.yml` uses `actions/checkout@v4` and `actions/setup-python@v5` — mutable tags.
The Scorecard-recommended form pins the commit SHA with the tag as a comment, e.g.
`uses: actions/checkout@<40-hex sha> # v4`. That is an edit to `verify.yml`, which this
build may not touch; it is a two-line maintainer change, and Dependabot's
`github-actions` ecosystem (above) keeps the SHAs current.

### S6 — SBOM *per release*
`sbom.sh` produces the document; attaching it to each release is the `release.yml` step
above. Until then it is an on-demand artifact (`./sbom.sh --optional`).

## Alternatives considered

- **Add a lockfile to this repo now** (`uv lock` / `pip-compile`) so `76_lockfile` is
  live here. Rejected: nothing in the maintainer's tooling regenerates it, so it would
  rot; CI installs from `pyproject.toml`, so the lock would not even be what CI uses.
  Declared honestly as `noop` instead.
- **Make the pin rule a ratio** ("≥ 90 % pinned"). Rejected: a number gate; the rule is
  naturally binary per line.
- **Exact `==` pins only.** Rejected: an upper bound is what stops the unreviewed major
  bump; exact pins on a *tool* chain would fight every patch release and push people to
  disable the check.
- **`cyclonedx-bom` / `syft` for the SBOM.** Rejected: a new dependency (or a binary
  download) for a document the stdlib can produce; the closure walk is ~100 lines.
- **Run `78_pins` on the fast lane.** It is cheap enough, but the task placed both checks
  on the heavy lane and the fast Stop gate should stay minimal; a project may move it.

## Consequences

- Two new heavy checks, one entry point, two new pure modules (100 % line + branch
  covered), one integration file (mutmut-ignored like every other shell-driving test).
- This repo's dev toolchain now has upper bounds; a future major of ruff/mypy/pytest/…
  requires a deliberate commit that moves the bound and re-runs the heavy lane.
- `76_lockfile` is a `noop` here until a lockfile exists — visible in every heavy run's
  `inspected NOTHING` line, which is the honest state.
- Matrix #2 rows: S6 `now` → *built (unsigned inventory)*; S8 `now` → *built*; S7, S9
  → *maintainer decision, config above*. The matrix file lives on `#138`'s branch and
  must be updated there.
