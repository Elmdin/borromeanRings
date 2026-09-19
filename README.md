# borromeanRings

> ## ⚠️ Work in progress — not ready for use
>
> borromeanRings is under active development and is **not in a stable state**. Do not
> install it, adopt it in a project, or rely on its verdict yet.
>
> The specific gaps holding this notice in place, so you can judge for yourself:
>
> - **#236** — `12_secrets` is not in the required set a new project gets from
>   `init.sh`, because it fails closed outside a git repository while `init.sh` must
>   produce a project that gates green. So a freshly initialised project does not gate
>   secrets at all until it is configured to.
> - **#229** — a check that is registered but not required still runs and still writes
>   a `fail` receipt that the verdict never mentions, so the run directory and the
>   verdict disagree about what happened.
> - **#144 / #145** — the gate runs the project's code as your user, so it cannot bound
>   an agent that is actively trying to defeat it. See the trust boundary below.
> - The PR queue is still draining, so `dev` is moving daily.
>
> Closed since this notice was written, and no longer blocking: **#222** (the Stop hook
> could be made to stand down on a red tree), **#230** (`12_secrets` missed the AWS
> *secret* access key — the half that grants access), **#228** (two heavy-lane checks
> audited whatever was installed on the machine rather than the project's own
> dependencies), **#219** (adoption never gave a project the ignore entry the harness
> assumes, which made the secret gate fail on the harness's own logs and stay failing
> after the secret was deleted).
>
> This notice goes when the rest close — not when the feature list is finished.


<p align="center">
  <img src="docs/borromean-rings.png" width="200" alt="Borromean rings — three links that hold only together; remove any one and the whole comes apart">
</p>

> Like the rings, the gates hold only together: remove any one check and the
> guarantee falls apart.

[![borromeanRings gate](https://github.com/3MagicLabs/borromeanrings/actions/workflows/verify.yml/badge.svg)](https://github.com/3MagicLabs/borromeanrings/actions/workflows/verify.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

borromeanRings is a **meta-harness**: a governing quality layer that wraps any AI coding
agent and enforces engineering standards as **deterministic, fail-closed gates** — not
prompt requests. The agent is an interchangeable worker; the gate is the product. It is
**model- and harness-agnostic** (the Claude Code hooks are a thin adapter over a plain
`verify.sh`), governs each project **only if that project opts in**, and governs **by
reference** — the code stays in this checkout; a governed project just points at it
(ADR-0013). It is honest about hollow verdicts: a check that inspected nothing reports
`noop`, never `pass`, and the gate says so out loud (ADR-0049). borromeanRings governs its
own repository from commit one.

## 60-second quickstart

You need Python ≥ 3.11 and the check toolchain on `PATH`
(`pip install -e ".[dev]"` from this checkout installs `ruff mypy pytest pytest-cov bandit`).

```bash
git clone https://github.com/3MagicLabs/borromeanRings.git && cd borromeanRings
./init.sh  /path/to/project     # NEW project: writes borromeanrings.toml + .claude/settings.json there
./adopt.sh /path/to/project     # EXISTING governed project: adds the recommended checks, seeds ratchet baselines
cd /path/to/project && /path/to/borromeanRings/verify.sh   # the gate: exit 0 only if every required check is non-failing
/path/to/borromeanRings/status.sh                          # how is THIS project governed, and was the last green hollow?
```

Every verdict below is real output from [`demo.sh`](demo.sh) (paths abbreviated; the
`harness-version` stamp, run ids and run digests vary per run). Learn to read three of
them.

**A green** — every required check inspected something and found nothing wrong:

```text
$ BORROMEANRINGS_PROJECT=/tmp/borromeanrings-demo.lvUAFn ~/borromeanRings/verify.sh

  borromeanRings gate  (project: /tmp/borromeanrings-demo.lvUAFn)
  harness-version: 8daa73e
  --------------------------
  00_build       PASS
  05_hygiene     PASS
  10_format      PASS
  20_lint        PASS
  30_typecheck   PASS
  40_test        PASS
  50_security    PASS
  --------------------------
  RESULT: PASS
  run-digest: efb83519cf286327865b64ab2cea0c2a53dc3bb21f13d2b49b592c49fb818587
```

**A hollow green** — the same starter gate on an *empty* project. It still passes (a
greenfield project must not be red), but the gate names every check that looked at
nothing, because a green resting on those proves less than it looks like:

```text
  00_build       NOOP
  05_hygiene     PASS
  10_format      PASS
  20_lint        PASS
  30_typecheck   NOOP
  40_test        NOOP
  50_security    NOOP
  --------------------------
  RESULT: PASS
  inspected NOTHING: 4 of 7 — 00_build, 30_typecheck, 40_test, 50_security
```

**A red** — `add()` was changed to `return "oops"`. The gate exits 1; the per-check logs
under `.meta-harness/receipts/<run-id>/` carry the mypy and pytest output:

```text
  00_build       PASS
  05_hygiene     PASS
  10_format      PASS
  20_lint        PASS
  30_typecheck   FAIL
  40_test        FAIL
  50_security    PASS
  --------------------------
  RESULT: FAIL
  run-digest: b82f6c4a7189ccc4cbfebd29d84979cf3c244ce13eac2da16ac1fd3c5fa1f384
  One or more checks failed or produced no receipt; see logs in the run dir.
```

And `status.sh`, run from inside the governed project after `adopt.sh`, answers the
question the raw verdict hides — was that green hollow, and is enforcement actually on?

```text
$ cd /tmp/borromeanrings-demo.lvUAFn && ~/borromeanRings/status.sh

  borromeanRings status — borromeanrings-demo.lvUAFn   (this project only)
  ------------------------------------------------------------
  Governed:     yes · 14 required check(s)
  Last verdict: PASS · run 20260908T153759Z-780660 · by borromeanRings 8daa73e
  ⚠ Hollow:     1 of 14 checks inspected NOTHING —
                04_self_description
                a green resting on these proves less than it looks like.
  Enforcement: AUTO — 4/4 hooks wired to this borromeanRings
  Installed:    borromeanRings 8daa73e at ~/borromeanRings
  Re-gate:      ~/borromeanRings/verify.sh
```

(`04_self_description` is `noop` there because the demo project's README states no
check count — an honest nothing-to-verify, not a pass.)

## Demo: watch the gate go red and back

```bash
./demo.sh          # builds a throwaway project in a temp dir, governs it, and walks every verdict above
./demo.sh --keep   # same, but leaves the project on disk so you can poke at it
```

`demo.sh` is itself a test: each step asserts the exact verdict it expects (hollow green
→ real green → red → green → `adopt.sh` → `status.sh`) and exits non-zero on the first
deviation. The full annotated walk-through, with what each step proves, is in
[`docs/DEMO.md`](docs/DEMO.md).

## Install as a Claude Code plugin (one line)

```bash
claude plugin marketplace add 3MagicLabs/borromeanRings && claude plugin install borromeanrings@borromeanrings
```

Wires the six hooks and the skills into every session; a project is governed only once it
has a `borromeanrings.toml`. See `docs/PLUGIN.md` (ADR-0057).

## Govern another project (portable, by reference)

The counts below are generated by `./describe.sh --readme` from the check registry and
held to it by `04_self_description` (ADR-0052) — a stated number in this README is a
checked claim, never a hand-written one:

<!-- describe:begin -->
**42 checks** across three lanes — 19 shared, 17 Python, 6 heavy/CI — of which **31 are required on this repo** and 6 are threshold-free ratchets.

Governance matrices: AI-agent quality (partial), Security & compliance (partial), Security & compliance (documented), Delivery / DORA (documented), Operational / SRE (documented), Data / ML (documented), Product / UX (documented), Security & compliance (partial), Delivery / DORA (partial), Operational / SRE (partial), Data / ML (archetype), Product / UX (partial).

Run `./describe.sh` for the generated report of every check, what it enforces, and where it applies. This block is generated; `04_self_description` fails the gate if the counts above stop matching the registry.
<!-- describe:end -->

The **shared** lane is language-agnostic (hygiene, layout, branch/commit conventions,
changelog, secrets, ADR discipline, container hygiene, static a11y, self-description);
the **Python** lane covers build, source coherence, format, lint, typecheck, tests with a
coverage ratchet, static security, and complexity / coupling / docstring ratchets; the
**heavy** lane (mutation score, dependency CVEs, licences, secret history) runs only
under `./verify.sh --heavy` and in CI. Which of these gate a project is declared in
that project's `borromeanrings.toml` `[checks].required` / `heavy`. The catalogue — what
each check guarantees, its config keys, how to turn it on — is
**[`docs/CHECKS.md`](docs/CHECKS.md)**.

The required set is declared in `borromeanrings.toml` `[checks].required` (thirty-one gates
on this repo; `06_git_identity` exists but is intentionally excluded so external
contributors pass CI — see ADR-0019). The table above is the v0 core; the full set of
**42 checks** across the shared / Python / heavy-CI lanes — what each enforces, its config
keys, and how to enable it — is catalogued in **`docs/CHECKS.md`**.

- **Fail-closed by allowlist**: only `pass` / `noop` are non-failing; an unknown, misspelled
  or forged status still fails (ADR-0049).
- **Honest about nothing**: a check that inspected nothing reports `noop`, never `pass`.
- **Threshold-free**: ratchets are non-regression against a seeded baseline, never an
  arbitrary target.
- **Tamper-evident receipts** per run, plus a persisted verdict and history
  (ADR-0026 / 0046 / 0047).
- **Governs by reference, per-project opt-in** (ADR-0013).

- `verify.sh` — the gate (the single source of truth, called by humans, CI, and hooks)
- `status.sh` — **this project's** status by default: governed? enforcement actually on (hooks wired vs. disabled)? last verdict, and how many of those checks inspected **nothing** (ADR-0049). `--all` opts into the portfolio table across every governed project; `--run` re-gates, `--list` prints paths (ADR-0046)
- `swe-state.sh` — the **SWE-state report**: what this project *practises*, *lacks* and should *adopt next*, from the spine, the last verdict, the archetype catalog, `adopt.sh`'s recommended set and the matrices' "Enforced by" column — categorical, sourced, no score; `status.sh --swe` appends it to the self-status (ADR-0067, [SPEC](docs/specs/SPEC-swe-state.md))
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
