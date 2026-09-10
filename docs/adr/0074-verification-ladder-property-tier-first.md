# ADR-0074 — The verification ladder, property tier first

**Status:** Accepted
**Spec:** `docs/specs/SPEC-verification-ladder.md`
**Issue:** #140 (epic) · follow-ups #204 (tier 2, SMT) and #205 (tier 3, formal)
**Relates to:** ADR-0022 (why never a number), ADR-0049 (vacuity, `noop`),
ADR-0042 (fail closed when the input is missing), ADR-0068 (never install a project's
toolchain), #146 (self-assurance, which this feeds)

## Context

Every correctness signal in this gate is a statement about **examples**. `40_test`
proves the examples someone wrote pass; `60_mutation` proves those examples would
*notice* a change to the code. Both are claims about the finitely many inputs a human
thought of. A **property** — "for every list, `sort` returns a sorted permutation" — is a
different kind of statement, and three mechanisms can back one: randomized search
(Hypothesis), a solver deciding a bounded domain (z3/CrossHair), and a machine-checked
proof (Lean/Dafny). #140 asks for that ladder, opt-in per project, and explicitly says
**research/spec first, build only on an explicit go**.

What is actually on this machine decided how much of it could be built honestly:
`hypothesis 6.156.6` and `pytest 9.0.3` are importable; `z3` and `crosshair` are not, and
this build's rule is **install nothing**.

## Decision

**1. Ship the specification for all three tiers; build tier 1 only.**
`docs/specs/SPEC-verification-ladder.md` covers property-based, SMT and formal with the
same seriousness — declaration, verdict rules, receipt evidence, and the honest limit of
each. Tiers 2 and 3 ship as that spec plus issues #204 and #205, with acceptance criteria
drawn from it. Building a tier-2 check here would mean shipping a check whose only
exercised path is "tool missing ⇒ `noop`" — an untested branch presented as a feature.

**2. Tier 1 is a binary, threshold-free rule.** `checks/python/27_properties.sh` runs the
suite the project declares at `[verification].properties` and reports pass/fail/noop. It
**never counts properties, never ratchets on how many exist, and never targets a number
of examples.** ADR-0022 chose a mutation ratchet over a coverage percentage because a
number invites gaming; "number of properties" is the same trap one rung up — forty
tautological properties would beat three sharp ones on any count. The file probe is
`find … -print -quit`: the check is structurally unable to see a count. It also does not
decide what "a property" *is* — no `@given` sniffing — because that would misjudge
hand-rolled properties and smuggle counting back in. The project's declaration is what
makes a directory the property suite.

**3. A declared-but-empty suite FAILS.** `[verification]` has **no defaults**, so writing
`properties` is an affirmative claim: *this project's universal statements live here.*
The three candidate verdicts were weighed:

- `pass` is the ADR-0049 defect verbatim — "inspected everything, found nothing wrong"
  from a check that inspected nothing;
- `noop` is honest about the inspection but not about the claim: `noop` means "no rule
  was declared", and this project declared one. It would make the declaration free —
  write the key, never write a property, and the verification row stays permanently
  green-ish;
- `fail` is the claim and the evidence disagreeing, which is what a gate is for. The fix
  is one line in either direction: write the first property, or delete the declaration.

This is the same shape as ADR-0042 (`12_secrets` fails closed on a non-git directory) and
ADR-0022 (`60_mutation` fails closed on zero evaluated mutants). The contrast that makes
it precise: `[container].dockerfile` *defaults* to `"Dockerfile"`, so its presence is not
a claim, and `14_container` correctly reports `noop` when there is no Dockerfile.

**4. Unknown keys under `[verification]` fail config loading closed.**
`spine.VERIFICATION_KEYS` is the allowlist. `propertys = "tests/properties"` would
otherwise read as "nothing declared" and switch a verification claim off in silence —
a self-disabling gate, the exact hazard ADR-0049 exists to remove. Validation lives in
`load_config`, not in the check, so the typo cannot hide by the project simply not
requiring `27_properties`.

**5. A missing runner is `noop` naming it, not `error`.** This is the one place this ADR
narrows a previous one, so it is recorded explicitly. ADR-0049 fixed "a missing tool is
`error` (exit 127), never `noop`" for tools invoked through `run_check` — tools
borromeanRings itself requires (ruff, mypy, bandit). The property runner is not one of
those: it belongs to the *governed project's* declared verification stack, which
borromeanRings deliberately does not install (see ADR-0068), exactly as `tsc` and `go` do for
the TypeScript and Go lanes, which already report `noop` naming the tool. `noop` here is
not a soft pass: it is printed on the gate line (`inspected NOTHING: N of M`), carried on
the persisted verdict, counted by `status.sh`, and the receipt names the missing module.
`error` would fail every CI job that has not installed Hypothesis — which is how an
opt-in ladder becomes a mandatory one by accident. **Reversal condition, made
operational:** the trigger is a governed project whose gate reported `27_properties noop`
for a runner-absent reason on a run where a declared property suite existed — i.e. the
project claimed properties and the gate let a green through without executing them. That
is detectable from the evidence already on disk: a `noop` receipt whose log names a
missing runner while `[verification].properties` resolves to a non-empty directory
containing property files. Whoever finds one files it against this ADR; the fix is to
make that combination `error` and require projects to pin their runner. Until then the
combination is simply not known to have occurred, which is a weaker claim than "it does
not happen" and is stated that way deliberately.

**6. Order of evaluation is part of the contract.** Everything decidable *without* a
runner — nothing declared, path missing, directory empty — is decided **first**, so an
absent tool can never mask a broken claim. A machine with no Hypothesis still fails a
project that declared a suite it never wrote.

**7. borromeanRings declares the check and no property directory.** `27_properties` is in
`[checks].required` with `[verification].properties = ""`, so this repo's own gate reports
`noop — rule off` and says so on the gate line. It is registered rather than omitted
because the ladder is a standing invitation this project intends to answer (#146), and a
visible `noop` is the honest rendering of "not opted in yet". No property suite was
invented for this repo to make the check look busy — that fabrication is precisely the
vacuity the check exists to reject. `adopt.py`'s `RECOMMENDED` set is **unchanged**:
adopting a verification tier is a decision a project makes, not one a migration makes
for it.

## Alternatives considered

- **Build tier 2 as well, with a `noop`-only path** — rejected: no positive-path
  evidence, and the no-install rule forbids provisioning z3 to get any.
- **Count properties, or ratchet on the count** — rejected on ADR-0022's reasoning; see
  decision 2.
- **Detect `@given` to verify the tests really are property-based** — rejected: it
  misjudges hand-rolled and metamorphic properties, and re-introduces counting.
- **Pin `--hypothesis-seed` / `max_examples` for a deterministic gate** — rejected. A
  fixed seed shrinks the guarantee to "these inputs, forever" while looking stronger, and
  choosing `max_examples` is choosing a number to hit. The consequence is stated instead
  of hidden: the gate is deterministic about the *rule* it applies; the search underneath
  it is not, so a property may be falsified on a later run than the commit that broke it.
  A project that wants determinism sets `derandomize` in its own Hypothesis profile.
- **Declared-but-empty ⇒ `noop`** — rejected; see decision 3.
- **Validate `[verification]` keys inside the check instead of `load_config`** —
  rejected: a typo would then go unnoticed in any project that had not required the
  check.

## Consequences

- (+) The gate can, for the first time, run a project's *universal* statements, and it
  rejects a verification claim with nothing behind it. Tiers 2 and 3 have a written
  contract and acceptance criteria instead of a roadmap line.
- (+) The honest limits are on the record, including the one that matters most: **none of
  the three tiers tell you the specification is right** — each only raises the cost of
  being wrong in a different direction (SPEC §"What this ladder cannot do").
- (−) This repo's own gate now reports one permanent `noop`, which is honest but is
  standing noise in `inspected NOTHING: N of M`. If that dulls the signal, the remedy is
  to drop `27_properties` from this repo's required set — not to fabricate a suite.
- (−) A machine without Hypothesis reports `noop` where a project may have expected
  enforcement; mitigated by naming the module in the receipt, and by the reversal
  condition in decision 5.
- (−) One more `[verification]` key means one more place `VERIFICATION_KEYS` must be
  kept in step; the fail-closed test is what keeps that honest.
