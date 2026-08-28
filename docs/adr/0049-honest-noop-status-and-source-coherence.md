# ADR-0049 — Honest no-op status, the source-coherence guard, and self-status

**Status:** Accepted
**Spec:** `docs/specs/SPEC-self-status.md`
**Amends:** ADR-0046 (status defaults to one project; the roster becomes opt-in)

## Context

A governed project reported **`ok: true`, 12/12 green** while **seven** of those checks
had inspected nothing at all. Its `borromeanrings.toml` declared `src_dir = "src"`, but no
`src/` existed — the real code lived in `tools/`. `00_build`, `30_typecheck`,
`32_complexity`, `33_coupling`, `45_docstrings` and `40_test` each logged "greenfield —
nothing to analyze" and exited 0; `50_security` was worse still, running
`bandit -q -r src` against a missing directory, which exits 0 with **completely empty
output** — a clean security receipt produced by scanning nothing.

The root cause is in `checks/_lib.sh`: status is derived solely from the exit code
(`[ "$code" -eq 0 ] && status="pass"`). **"I inspected nothing" and "I inspected
everything and it is clean" were structurally identical.** Every receipt told the truth in
its log; the verdict — the thing anyone actually reads — did not.

borromeanRings had already met this hazard once and fixed it locally: `12_secrets` was
hardened to fail closed on a non-git directory precisely so "can't scan" could not read as
"nothing to scan" (ADR-0042). That reasoning was never generalised. This ADR generalises
it.

Two further gaps surfaced from the same incident. Nothing distinguished a *legitimately
greenfield* project from a *misconfigured* one. And answering "is borromeanRings even
working here?" required reading raw receipts, because the only reporting command
(`status.sh`) defaulted to walking **all of `$HOME`** — a portfolio answer to a
single-project question, and an implicit scan of everything the user owns.

## Decision

**1. A fourth receipt status: `noop`.** A check that ran but had nothing to inspect emits
`noop`, not `pass`. It is non-failing but reported everywhere: the gate prints
`inspected NOTHING: N of M — …`, and the status rides on the persisted verdict and its
history. `_lib.sh` gains `emit_noop`, plus exit code **3** as the convention by which an
embedded Python step signals "nothing to inspect" (a heredoc's only channel back to bash
is its exit code, and 0 there is indistinguishable from a real pass).

**2. Fail-closed by allowlist, never by negation.** `meta_harness.verdict` owns
`NON_FAILING_STATUSES = {"pass", "noop"}` and `is_failing()`; `verify.sh` and every
downstream reader use it. This is the safety-critical part of the change: written as a
negation, a second non-failing status turns any unknown, misspelled, or forged status into
a silent pass. Matching is exact — no case folding, no stripping. A regression test asserts
that `""`, `"?"`, `"skipped"`, `"PASS"` and friends all still fail.

**3. `01_source_coherence` — a guard that fails the gate.** Greenfield stays green
(`noop`); a declared source path that resolves to nothing **while tracked source exists
elsewhere** is a misconfiguration and fails, naming the directories where the code
actually lives. It resolves the configured path with the same semantics as the checks it
protects, so the guard and those checks cannot disagree. "Elsewhere" means git-*tracked*
source — an untracked scratch file must never fail someone's gate — with a bounded
filesystem walk as the fallback for a non-git project.

**4. Self-status is the default; the roster is opt-in.** `status.sh` with no arguments
reports the enclosing project: governed or not, enforcement AUTO/PARTIAL/MANUAL, the last
verdict with its harness version, and the hollow-check count. `--all` (or explicit roots)
requests the portfolio table. A `borromeanrings-status` skill ships to every governed
project via `init.sh`, so any session can be asked "check my borromeanRings status".

Enforcement is detected by borromeanRings's **hook script names**, not by path: a
referenced install spells the command with an absolute `$BORROMEANRINGS_HOME`, while a
repo that governs itself uses `${CLAUDE_PROJECT_DIR}`. Path matching would misreport the
self-governing case — including borromeanRings's own repo — as unenforced.

### What `noop` is NOT for

`emit_noop` is a reporting primitive, not an escape hatch. A check may emit it **only when
it did zero inspection work** — never to soften a finding it did compute. Two existing
decisions stay as they are, and are recorded here so nobody "helpfully" relaxes them
later:

- **A missing tool is `error` (exit 127), never `noop`.** `run_check` already does this.
  Prior art shows why it matters: actionlint silently drops its `shellcheck` and
  `pyflakes` sub-rules when the binary is absent, so the run inspects less than it claims
  and says nothing. "I could not run" is not "there was nothing to run".
- **`12_secrets` still fails closed on a non-git directory** (ADR-0042). "Can't scan" must
  not become "nothing to scan" — least of all in a secret gate.

The scope boundary is likewise deliberate. `01_source_coherence` decides on `src_dir`
only, and counts *implementation* source: tests, packaging shims (`setup.py`,
`conftest.py`, `noxfile.py`), docs scaffolding and vendored trees are excluded. Counting
tests would fail the gate for a project whose only code so far is a failing test — the RED
step of the test-first workflow this harness exists to support. Where the guard cannot
decide, it reports instead of failing: an unset `[project].package` blinds three
package-scoped checks, so the check says so rather than rejecting a legitimately
scripts-only project.

## Consequences

- A green verdict now carries its own caveat. A project cannot report full marks while
  the gate is blind to its code: either the checks did real work, or the run says how many
  did not, or `01_source_coherence` fails outright.
- **Migration:** the guard is opt-in per project (`[checks].required`) like every check,
  and is added to `adopt.py`'s `RECOMMENDED` so `adopt.sh` offers it. Projects that adopt
  it while misconfigured will go red — that redness is the information they were missing.
  Verified against the maintainer's real portfolio: it flags exactly the misconfigured
  projects and leaves genuinely-greenfield and correctly-configured ones untouched.
- Old verdicts (written before `noop`) parse unchanged; a run with no `noop` receipts
  renders exactly as before.
- Existing behaviour is otherwise untouched: `noop` is non-failing, so no project that
  passed yesterday fails today purely from this vocabulary change.
- **Known remaining vacuity (deliberate, deferred).** Three vacuous branches are *not* yet
  converted: `05_hygiene` with an empty `requires` (the adversarial corpus' known-good
  control depends on it reporting `pass`), `07_layout` with all rules unset, and
  `09_commits` with no base branch. Unbaselined ratchets are a third flavour — they do
  measure, just against a permissive baseline — and are not `noop`. Until those land, the
  hollow count is a floor, not a total. Consolidating the three duplicated `_SKIP_DIRS`
  constants is a related follow-up.
