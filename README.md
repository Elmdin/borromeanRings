# borromeanRings

> ## ⚠️ Work in progress — not ready for use
>
> borromeanRings is under active development and is **not in a stable state**. Do not
> install it, adopt it in a project, or rely on its verdict yet.
>
> The specific gaps holding this notice in place, so you can judge for yourself:
>
> - **#230** — `12_secrets` does not detect an AWS *secret* access key, and `init.sh`
>   leaves the secret check out of a new project's required set entirely.
> - **#228** — two heavy-lane checks audit whatever is installed on the machine rather
>   than the project's own dependencies, so the same commit gets different verdicts.
> - **#229** — `06_git_identity` cannot pass under this project's own merge model and
>   was dropped from the required set instead of being reconciled.
> - **#144 / #145** — the gate runs the project's code as your user, so it cannot bound
>   an agent that is actively trying to defeat it. See the trust boundary below.
>
> This notice goes when those close — not when the feature list is finished.


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

The required set is declared in `borromeanrings.toml` `[checks].required` (thirty gates
on this repo; `06_git_identity` exists but is intentionally excluded so external
contributors pass CI — see ADR-0019). The table above is the v0 core; the full set of
**41 checks** across the shared / Python / heavy-CI lanes — what each enforces, its config
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

## What borromeanRings guarantees, and what it does not

A gate that is not honest about its own limits is worse than no gate, because the
people relying on it stop looking. So, plainly:

**It resists accident, mistake, and naive forgery.** A change cannot reach `dev` or
`main` without the full gate passing in CI, on GitHub's runners, against the same
`verify.sh` a human runs locally. Branch protection requires that check and requires
the branch to be up to date first. A failing test, a type error, an unformatted
file or a broken architectural rule all stop the merge, and no amount of an agent
insisting the work is done changes that. Locally, the Stop hook keeps an agent from
declaring a task finished on a red tree, and the records that decide whether it runs
— the retry count and the last-proven-green hash — live **outside** the project, so
an agent confined to the project directory cannot rewrite them (ADR-0079, ADR-0082).

Secret scanning is the one required check whose coverage is **partial**, and it is
worth being specific rather than reassuring: `12_secrets` catches well-formed provider
tokens and private-key blocks — an AWS access key *ID*, a GitHub PAT, a Slack token, a
`BEGIN PRIVATE KEY` block — and by design does not guess at high-entropy strings. It
does not yet catch the AWS secret access key, and `init.sh` does not put the check in a
new project's default required set at all. Both are #230, and both are open.

**It does not resist an agent that deliberately forges its verdict.** The gate runs
the governed project's own test code, as your user, on your machine. That code can do
anything your user can do — including reaching the state directory above, or the
interpreter, or `verify.sh` itself. No arrangement of files inside a tree the agent
can write can close that, and we have not pretended otherwise: every hardening in
this repository raises the cost of a forgery, and none of them make it impossible.

The distinction that matters is **confinement, not good intentions**. A real bound
needs the gate to run somewhere the agent cannot reach — isolated execution in a
worktree or sandbox, with the verdict produced outside the agent's blast radius.
That is tracked as #144 and #145 and is not built yet.

**What follows from this.** Treat a green local gate as strong evidence, and CI's
green as the thing you act on: CI checks out the commit on a runner the agent never
touched, which is precisely the confinement the local run lacks. If you are running
an agent you have reason to distrust, borromeanRings is not the control you want —
you want isolation, and this is a quality layer running inside it.

## Design

See `docs/` — the `.claude/` hooks are an Adapter over `verify.sh` (what makes
borromeanRings harness-agnostic); checks are a uniform-contract registry; the tool a
check uses and the substrate are module secrets. The gate is a mechanized
Definition of Done.

<!-- describe:begin -->
**42 checks** across three lanes — 19 shared, 17 Python, 6 heavy/CI — of which **31 are required on this repo** and 6 are threshold-free ratchets.

Governance matrices: AI-agent quality (partial), Security & compliance (partial), Security & compliance (documented), Delivery / DORA (documented), Operational / SRE (documented), Data / ML (documented), Product / UX (documented), Security & compliance (partial), Delivery / DORA (partial), Operational / SRE (partial), Data / ML (archetype), Product / UX (partial).

Run `./describe.sh` for the generated report of every check, what it enforces, and where it applies. This block is generated; `04_self_description` fails the gate if the counts above stop matching the registry.
<!-- describe:end -->
