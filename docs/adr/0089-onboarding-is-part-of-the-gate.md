# ADR-0089 — Onboarding is part of the gate: infer, seed or decline, and disclose

**Status:** Accepted · 2026-09-25 · audit of 2026-09-20 ·
**Relates to:** ADR-0041 (adoption), ADR-0049 (honest `noop`), ADR-0042 (fail closed
outside git), ADR-0068 (language lanes), ADR-0088 (a check that cannot read its inputs
fails), #186

## Context

borromeanRings had only ever gated **its own repository**, whose config and baselines are
hand-maintained. An audit ran it against a fresh external Python project by following the
documented path — `init.sh`, gate, `adopt.sh`, gate — and every step of that path was
broken in a way that is invisible from inside this repo:

1. `init.sh` wrote `package = ""`, described as "optional; skips the import check". It
   also switches off `32_complexity`, `33_coupling` and `45_docstrings`, which then report
   *"no package/source to measure (greenfield)"* about a project with five modules in
   `src/` — while the gate says `RESULT: PASS`. `adopt.sh` then promoted exactly those
   three checks into the required set.
2. `adopt.sh` seeded the coverage baseline from a receipt that rounds to two decimals,
   while `40_test` compares full precision with a 1e-9 epsilon. The next run failed with
   `COVERAGE REGRESSION: 97.37% is below baseline 97.37%` — a clean project turned red by
   adoption itself, with a message that cannot be acted on.
3. `adopt.sh` seeded **no** baseline for the three ratchets it had just made required.
   Their defaults are permissive (100000, 0), so each printed `PASS` and could never fail.
   The audit's injected complexity regression was caught only because the auditor seeded
   the baseline by hand; on the documented path it would have passed.
4. `adopt.sh` promoted `17_prior_art`, whose failure message tells the reader to write a
   survey "see `docs/surveys/TEMPLATE.md`" — a file that exists in the harness and not in
   the governed project.

Two more, from the same audit, about what a run *says*:

5. The `inspected NOTHING` line counted only the required set. On the first run an adopter
   sees — before anything has been added to `[checks].required` — 16 of 36 checks that ran
   had inspected nothing and the verdict said so nowhere. The run directory knew.
6. A `borromeanrings.toml` that will not parse ended the run in a Python traceback, and
   each check's own config read threw another: eighteen tracebacks and no verdict.

## Decision

1. **`init.sh` reads `[project].package` from the layout** (`infer_package`: exactly one
   directory under `src/` holding an `__init__.py`). Two candidates or none leaves it
   empty and says, in the output, what that costs. A default that silently switches off
   the checks which measure the project's code is not a default.
2. **`adopt.sh` seeds a baseline for every ratchet it promotes — or does not promote it.**
   If `[project].package` is unknown it infers it and writes it back; if it still cannot,
   it leaves those checks out of the required set and says why. A required check that
   cannot fail is worse than an absent one, because it reports `PASS`.
3. **A promoted check's prerequisites come with it.** Promoting `17_prior_art` creates
   `docs/surveys/TEMPLATE.md` in the governed project, because the check's own message
   points the reader there.
4. **A receipt records the measurement, not a rounded rendering of it.** `40_test` stores
   the coverage it measured; the log still prints two decimals for a human. Seeding a
   baseline from a receipt is then exact, which is what (2) above depends on.
5. **The verdict discloses hollowness outside the graded set too**, on its own line and in
   its own words, so the first green run cannot hide it (`hollow_outside`).
6. **A config the gate cannot read ends in a verdict, not a traceback.** The run is still
   not refused — ADR-0042's reasoning holds, and every check writes a fail receipt saying
   why — but the verdict step reports the unreadable config as the verdict, and
   `borromeanrings_project_cfg` reports one line instead of a stack trace. When the
   language cannot be read, the fallback to the Python lane **announces itself**, because
   which lane runs is the one thing that fallback silently decides.

## Amendment from this PR's review — an inferred name is an input

The review found the fix worse than the default it replaced. `[project].package` is
interpolated into a command string the shell expands (`00_build` runs
`python3 -c "import $package"` through `bash -c`), and `init.sh`/`adopt.sh` now write that
value **from a directory name read off disk**. A directory called `pkg$(whoami)` is a
valid TOML string, so it would have reached that command. (A double quote cannot: TOML
ends the string first. Command substitution was the live vector.)

So the name is validated where every consumer benefits — the spine refuses a
`[project].package` that is not an importable dotted path (`UnusablePackageName`, kind
`package`), before any check runs — and `infer_package` refuses to *offer* such a name in
the first place. Two layers on purpose: inference is the new risk, and a hand-written
config was always able to do the same thing.

The first version of that validator refused the dotted form `fixturepkg.core`, which is a
real configuration this project's own tests use: a validator tighter than the thing it
guards, which is the same mistake the review of #259 caught. Each segment is checked now,
not the whole string.

Two smaller findings from the same review: the "also inspected nothing" denominator
counted required rows rather than receipts, so a required check that wrote no receipt made
the count undercount (and it could go negative); and the unreadable-config exit left the
project's `last_verdict.json` holding the *previous* run, so `status.sh` reported a green
that had not happened.

## Alternatives considered

- **Document it instead: tell adopters to set `package` and seed the baselines.** The
  cheapest fix, and the reason this went unnoticed for three months — the instructions
  were already there, and following them produced a red gate and three dark checks. A
  harness whose correct use depends on reading its source is not configured, it is
  guessed at.
- **Have `adopt.sh` run the project's test tool to seed the coverage baseline.** Rejected,
  and it is the reason `coverage_seed` reads receipts at all: adoption installs nothing
  and runs no language tooling (ADR-0041). The receipt of a real run is the honest source.
- **Make the coverage comparison tolerant of two decimals.** Rejected: it hides the
  defect rather than removing it, and a ratchet whose comparison is fuzzy by a constant
  is a ratchet with an arbitrary threshold in it.
- **Refuse the run when the config cannot be parsed.** Considered, and close. Rejected
  because the existing behaviour is deliberate and tested
  (`test_supply_chain_gate.py::test_unreadable_spine_fails_closed_not_noop`): N fail
  receipts naming the cause are better evidence than one message and no receipts. What was
  wrong was the *traceback*, not the continuing.
- **Promote the ratchets anyway and let the adopter seed them later.** That is what
  happened, and it is how a required check ends up unable to fail.

## Consequences

- (+) A project adopting borromeanRings by the documented path ends green, with its
  ratchets measuring real numbers — verified end to end by
  `tests/integration/test_onboarding_external_project.py`, which builds a fresh project,
  runs `init.sh`/`adopt.sh`, and injects a real complexity regression.
- (+) The first run an adopter sees now states how much of it looked at nothing.
- (+) The audit that found all of this is kept as a test, so self-governance cannot hide
  the class again.
- (−) `adopt.sh` may now decline to promote three checks, where before it promoted them
  inert. That is a smaller required set and a louder message, and it is the honest trade.
- (−) `coverage_percent` in a receipt is now full precision. Anything that displayed it
  raw shows more digits; the log's own line is unchanged at two decimals.
- (−) One more line in the verdict for most projects.
- (−) One traceback remains on an unreadable config, from a check's own inline config
  read. The ~20 `borromeanrings_project_cfg`-family sites are tracked on #186.
