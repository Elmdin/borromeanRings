# borromeanRings

> ## ⚠️ Work in progress — not ready for use
>
> borromeanRings is under active development and is **not in a stable state**. Do not
> install it, adopt it in a project, or rely on its verdict yet. Known gaps that must
> close first are tracked in the issues, including verdict-integrity and retry-bound
> hardening. This notice will be removed when the harness is ready to be used.


<p align="center">
  <img src="docs/borromean-rings.png" width="200" alt="Borromean rings — three links that hold only together; remove any one and the whole comes apart">
</p>

> Like the rings, the gates hold only together: remove any one check and the
> guarantee falls apart.

[![borromeanRings gate](https://github.com/Elmdin/borromeanrings/actions/workflows/verify.yml/badge.svg)](https://github.com/Elmdin/borromeanrings/actions/workflows/verify.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

A model- and harness-agnostic **meta-harness**: a governing quality layer that
wraps any AI coding agent and enforces engineering standards as **deterministic
gates** — not prompt requests. The agent is an interchangeable worker; the gate
is the product. A change cannot pass until every declared standard is satisfied.

This is **v0**: one repo, one stack (Python), one gate, on Claude Code. borromeanRings
governs its own repo from commit one (it must pass its own gate).

## Run the gate

```bash
./verify.sh        # exit 0 only if every check passes; fail-closed otherwise
```

Each run writes one receipt per check to `.meta-harness/receipts/<run-id>/`, plus
a config cross-check against `borromeanrings.toml`: a required check that never ran (crash/skip) ⇒ overall fail.

## Merge (gated, explicitly requested)

```bash
./merge.sh [base]          # run the gate, then merge immediately if green
./merge.sh --auto [base]   # run the gate, then WAIT for the PR's CI to pass, then merge
```

Run from a feature branch: borromeanRings runs the gate and merges into `base` **only**
if it passes. It executes your merge decision — it never merges on its own. `--auto`
waits for the PR's CI checks too, but is still explicitly invoked per-merge (no
standing, unattended mode). See `docs/adr/0007-gated-explicit-merge.md` and
`docs/adr/0009-command-orchestrated-auto-merge.md`.

## Install as a Claude Code plugin (one line)

```bash
claude plugin marketplace add Elmdin/borromeanRings && claude plugin install borromeanrings@borromeanrings
```

Wires the six hooks and the skills into every session; a project is governed only once it
has a `borromeanrings.toml`. See `docs/PLUGIN.md` (ADR-0057).

## Govern another project (portable, by reference)

borromeanRings can govern *any* project without being copied into it — its code stays here,
the target just references it:

```bash
./init.sh /path/to/your-project       # writes borromeanrings.toml + .claude/settings.json there
# edit your-project/borromeanrings.toml ([project] package/src_dir, required checks, hygiene)
cd /path/to/your-project && /path/to/borromeanrings/verify.sh    # borromeanRings governs it
```

Any agent prompted in that project is now governed (its `.claude/settings.json` hooks
point back at this borromeanRings, and the `borromeanrings-research` skill is installed). `BORROMEANRINGS_HOME`
= where borromeanRings lives; `PROJECT_ROOT` = the project being governed.
See `docs/adr/0013-portability-reference-model.md`, and **`docs/TESTING.md`** for a full
step-by-step way to exercise every feature on a fresh project.

## The checks (v0)

| # | Check | Tool |
|---|---|---|
| 00 | build / importable | `python -m compileall` + import |
| 05 | hygiene | required engineering surround (docs, CI, container, license) exists |
| 07 | layout | repo layout — specs dir, root-`.md` allowlist, grouped test suites |
| 10 | format | `ruff format --check` |
| 20 | lint | `ruff check` |
| 30 | typecheck | `mypy` (strict) |
| 40 | test + coverage **ratchet** | `pytest --cov` (no absolute % target) |
| 50 | security | `bandit` |

The required set is declared in `borromeanrings.toml` `[checks].required` (twenty-five gates
on this repo; `06_git_identity` exists but is intentionally excluded so external
contributors pass CI — see ADR-0019). The table above is the v0 core; the full set of
**34 checks** across the shared / Python / heavy-CI lanes — what each enforces, its config
keys, and how to enable it — is catalogued in **`docs/CHECKS.md`**.

## Layout

- `verify.sh` — the gate (the single source of truth, called by humans, CI, and hooks)
- `status.sh` — **this project's** status by default: governed? enforcement actually on (hooks wired vs. disabled)? last verdict, and how many of those checks inspected **nothing** (ADR-0049). `--all` opts into the portfolio table across every governed project; `--run` re-gates, `--list` prints paths (ADR-0046)
- `ledger.sh` — the **effectiveness view**: per project, gate runs / failures caught / pass-fail streak from the recorded verdict history — is the gate actually catching anything (ADR-0047)
- `checks/` — one script per check under a uniform contract (`borromeanrings.toml` declares the required set); catalogued in `docs/CHECKS.md`
- `VERSION` — the declared release marker; every gate run is stamped with the governing borromeanRings version (ADR-0048)
- `borromeanrings.toml` — the policy spine: declared invariants enforced on every run
- `.claude/` — Claude Code hook **adapters** over the substrate-neutral gate
- prompt rewriting: `.claude/hooks/prompt_rewrite.sh` (UserPromptSubmit) injects a spine-driven rewrite directive; toggle in `borromeanrings.toml`
- `src/`, `tests/` — the governed code
- `docs/MANIFESTO.md` — **the why**: the north star; borromeanRings is the meta-harness (it enhances agent capabilities incl. deep research); the notes/Kernel is a separate product built *with* it
- `docs/VISION.md` — the whole product borromeanRings (the meta-harness) is meant to become
- `docs/ROADMAP.md` — **every harness feature, with status** (plus the separate products built with borromeanRings)
- `docs/SELF-ASSESSMENT.md` — **the evidence-based self-assessment**: how the gate works, what one cycle of sub-agent reviews found (defects by class, and whether a mechanism or only review catches each), gaps in the platform's own order, prioritised improvements
- `docs/` — requirements, architecture, ADRs, test plan, process (CS130-grounded)
- `PLAN-v0.md` — the v0 spec and document hub

## Design

See `docs/` — the `.claude/` hooks are an Adapter over `verify.sh` (what makes
borromeanRings harness-agnostic); checks are a uniform-contract registry; the tool a
check uses and the substrate are module secrets. The gate is a mechanized
Definition of Done.

<!-- describe:begin -->
**34 checks** across three lanes — 14 shared, 16 Python, 4 heavy/CI — of which **25 are required on this repo** and 5 are threshold-free ratchets.

Governance matrices: AI-agent quality (partial), Security & compliance (documented), Delivery / DORA (documented), Operational / SRE (documented), Data / ML (documented), Product / UX (documented), Security & compliance (partial), Delivery / DORA (partial), Operational / SRE (partial), Data / ML (archetype), Product / UX (partial).

Run `./describe.sh` for the generated report of every check, what it enforces, and where it applies. This block is generated; `04_self_description` fails the gate if the counts above stop matching the registry.
<!-- describe:end -->
