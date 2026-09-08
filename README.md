# borromeanRings

<p align="center">
  <img src="docs/borromean-rings.png" width="200" alt="Borromean rings — three links that hold only together; remove any one and the whole comes apart">
</p>

> Like the rings, the gates hold only together: remove any one check and the
> guarantee falls apart.

[![borromeanRings gate](https://github.com/Elmdin/borromeanrings/actions/workflows/verify.yml/badge.svg)](https://github.com/Elmdin/borromeanrings/actions/workflows/verify.yml)
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
git clone https://github.com/Elmdin/borromeanRings.git && cd borromeanRings
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

## What it enforces

The counts below are generated by `./describe.sh --readme` from the check registry and
held to it by `04_self_description` (ADR-0052) — a stated number in this README is a
checked claim, never a hand-written one:

<!-- describe:begin -->
**29 checks** across three lanes — 11 shared, 14 Python, 4 heavy/CI — of which **20 are required on this repo** and 5 are threshold-free ratchets.

Governance matrices: AI-agent quality (partial), Security & compliance (partial), Delivery / DORA (partial), Operational / SRE (archetype), Data / ML (archetype), Product / UX (archetype).

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

Guarantees, straight from `./describe.sh`:

- **Fail-closed by allowlist**: only `pass` / `noop` are non-failing; an unknown, misspelled
  or forged status still fails (ADR-0049).
- **Honest about nothing**: a check that inspected nothing reports `noop`, never `pass`.
- **Threshold-free**: ratchets are non-regression against a seeded baseline, never an
  arbitrary target.
- **Tamper-evident receipts** per run, plus a persisted verdict and history
  (ADR-0026 / 0046 / 0047).
- **Governs by reference, per-project opt-in** (ADR-0013).

## Commands

| Command | Does |
|---|---|
| `verify.sh [--heavy]` | **The gate.** Runs every check for the project at `BORROMEANRINGS_PROJECT` (default: `$PWD`); exit 0 only if every required check is non-failing. `--heavy` adds the CI-tier lane. |
| `init.sh <dir>` | Govern a **new** project: writes a starter `borromeanrings.toml` and a `.claude/settings.json` whose hooks point back here; installs the skills. |
| `adopt.sh [dir]` | Upgrade an **existing** governed project onto the recommended quality/security checks; seeds each ratchet baseline from the current state so the first run is green (ADR-0041). |
| `status.sh [--all\|--run\|--list]` | This project's governance status: governed? enforcement AUTO / PARTIAL / MANUAL? last verdict, and how many checks were hollow. `--all` is the portfolio roster (ADR-0046 / 0049). |
| `ledger.sh` | The effectiveness view per project: gate runs, failures caught, pass/fail streak, from the verdict history (ADR-0047). |
| `describe.sh [--json\|--readme]` | The generated capability report; `--readme` regenerates the block above (ADR-0052). |
| `merge.sh [--auto] [base]` | Run the gate, then merge into `base` only if green; `--auto` also waits for the PR's CI. Explicitly invoked, never unattended (ADR-0007 / 0009). |
| `install-global.sh` | Optional: install the hooks and skills at the user level so "use borromeanRings" works in any workspace. The hooks no-op in a project without a `borromeanrings.toml`. Once #166 merges there is also a Claude Code plugin install path (`docs/PLUGIN.md`). |
| `demo.sh [--keep]` | The scripted walk-through above; exits non-zero if any step deviates. |

## How governance works

- A governed project's `.claude/settings.json` (written by `init.sh`) wires hooks that
  point at `$BORROMEANRINGS_HOME/.claude/hooks/`: the **Stop** hook runs the gate and
  blocks the agent on FAIL; **PreToolUse** guards protected-branch commits and dangerous
  shell; **PostToolUse** auto-formats edited files; **UserPromptSubmit** injects the
  prompt-rewrite directive. Every hook exits immediately in a project with no
  `borromeanrings.toml` — nothing is governed without opt-in.
- The hooks are an Adapter: `verify.sh` is the single gate, called identically by humans,
  CI (`.github/workflows/verify.yml` runs `verify.sh --heavy`) and hooks, so the verdict
  is the same for any author.
- `borromeanrings.toml` is the policy spine: what is declared there is what is enforced,
  on every run. Each run writes one receipt per check to
  `<project>/.meta-harness/receipts/<run-id>/`, a `last_verdict.json`, and a line in
  `verdict_history.jsonl`, each stamped with the governing harness version (ADR-0048).
- `BORROMEANRINGS_HOME` = where this code lives; `PROJECT_ROOT` = the project being
  governed (`BORROMEANRINGS_PROJECT` | `CLAUDE_PROJECT_DIR` | `$PWD`). They coincide when
  borromeanRings governs itself.

Checks are Python-targeted today (the shared lane is language-agnostic); other stacks
need their own checks behind the same contract. `docs/TESTING.md` walks through
exercising every feature — including the hooks inside a live Claude Code session — on a
fresh project.

## Read next

- **[`docs/CHECKS.md`](docs/CHECKS.md)** — every check, what it guarantees, how to enable and configure it.
- **[`docs/HANDOFF.md`](https://github.com/Elmdin/borromeanRings/blob/docs/handoff/docs/HANDOFF.md)** — the contract for picking this project up cold: definition of done, unbendable rules, build order (on the `docs/handoff` branch until it merges).
- **[`docs/adr/README.md`](docs/adr/README.md)** — the ADR index; every load-bearing decision, with the alternatives it rejected.
- **[`docs/ENFORCEMENT-COVERAGE.md`](docs/ENFORCEMENT-COVERAGE.md)** — the SE best-practice matrix and what is enforced against it. The per-domain governance matrices (security, DORA, SRE, ML, UX) land with #153.
- **[`docs/MANIFESTO.md`](docs/MANIFESTO.md)**, **[`docs/VISION.md`](docs/VISION.md)**, **[`docs/ROADMAP.md`](docs/ROADMAP.md)** — the why, the whole product, and every harness feature with its status.
- **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)** — how the gate is built: checks as a uniform-contract registry, the adapter seam, module secrets.
- **[`examples/textkit`](examples/textkit)** — a governed example library, a different archetype than the harness itself (ADR-0039).
- **[`AGENTS.md`](AGENTS.md)** — the non-obvious rules for humans and agents working here.
- **[Contributing](.github/CONTRIBUTING.md)** · **[Security policy](.github/SECURITY.md)** · **[Changelog](CHANGELOG.md)** · **[`PLAN-v0.md`](PLAN-v0.md)** (the v0 spec and document hub).
