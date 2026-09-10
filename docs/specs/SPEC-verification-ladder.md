# SPEC — The verification ladder: property-based → SMT → formal

**Status:** Tier 1 implemented · Tiers 2 and 3 specified, **not built** ·
**Realized by (tier 1):** `checks/python/27_properties.sh`, `[verification]` in
`src/meta_harness/spine.py` · ADR-0074 · Issue #140

## Problem

Every correctness signal borromeanRings enforces today is about **examples**. `40_test`
proves the examples someone wrote pass. `60_mutation` proves those examples would
*notice* a change to the code (ADR-0022) — a much stronger claim than coverage, and
still a claim about the finitely many inputs a human thought of.

A **property** is a different kind of statement: not "`sort([3,1,2]) == [1,2,3]`" but
"for every list, `sort` returns a permutation in non-decreasing order". Three mechanisms
can back a statement like that, at increasing cost and increasing strength:

| Tier | Mechanism | Quantifies over | Cost | Status here |
|---|---|---|---|---|
| **1 — property-based** | randomized search + shrinking (Hypothesis) | many inputs it *sampled* | seconds | **built** |
| **2 — SMT** | a solver decides a contract over a bounded domain (z3/CrossHair) | *all* inputs in that domain | seconds–minutes, tool install | specified |
| **3 — formal** | a machine-checked proof (Lean/Dafny/Coq) | *all* inputs, unbounded | days–months of human effort | specified |

The ladder is **opt-in per project, per tier**. Nothing on it is a default: a throwaway
script must not carry a proof obligation, and a fintech ledger should be able to reach
for one. This is the same right-sizing rule as `docs/ENFORCEMENT-COVERAGE.md` §1 law 2.

## Non-goals (standing, all three tiers)

- **Never a count.** The gate never counts properties, never ratchets on how many exist,
  and never targets a number of examples. ADR-0022 chose a mutation ratchet over a
  coverage percentage precisely because a number invites gaming; "number of properties"
  is the same trap one rung up — 40 tautological properties would beat 3 sharp ones.
  Tier 1 is therefore **binary**: the declared suite passes, or it does not.
- **Never installs anything.** If a tier's runner is not on the machine, the check says
  so by name and inspects nothing. borromeanRings does not provision a governed
  project's toolchain (the rule the multi-language lanes established — #67 / ADR-0068).
- **Never contacts a network or a model.** Solvers and proof checkers must run offline.

---

## Tier 1 — property-based (built)

### Declaration

```toml
[verification]
properties = "tests/properties"   # project-relative dir holding the property suite
                                  # absent or "" ⇒ the rule is OFF for this project
```

`[verification]` has **no defaults**. Writing `properties` is an affirmative claim: *this
project's universal statements live here.* That is what makes the empty case a failure
(below), and it is the difference from `[container].dockerfile`, which defaults to
`"Dockerfile"` and so is never a claim — a project with no Dockerfile never said it had
one, so `14_container` correctly reports `noop`.

**Unknown keys under `[verification]` fail closed** in `load_config`. A typo
(`propertys = "tests/properties"`) would otherwise read as "nothing declared" and turn a
verification claim off in silence — a self-disabling gate, which is the exact hazard
ADR-0049 exists to remove.

### The rule (`27_properties`, fast lane, `checks/python/`)

Evaluated in this order. The order is part of the contract: everything decidable
*without* a runner is decided first, so a missing tool can never mask a broken claim.

| Situation | Verdict | Why |
|---|---|---|
| `[verification].properties` absent or empty | **`noop`** — "rule off" | The project has not opted in. Nothing was claimed and nothing was inspected; say exactly that. |
| Declared path is not a directory | **`fail`** | A claim pointing at nothing. |
| Declared directory holds no test file (`test_*.py` / `*_test.py`, recursive) | **`fail`** — vacuity | See below. |
| Runner absent (`hypothesis` or `pytest` not importable) | **`noop`** naming the missing module | "I could not run" is reported, never disguised as a pass. |
| Runner ran, suite passed | **`pass`** | |
| Runner ran, suite failed (including a counterexample) | **`fail`** | Fail closed on a falsified property. |
| Runner ran, collected nothing (pytest exit 5) | **`fail`** — vacuity, second layer | Files that look like tests but contain none. |

The check **does not classify a test as "property-based"**. It does not look for
`@given`, and it cannot see how many tests exist — the file probe is
`find … -print -quit`, which stops at the first hit by construction. What makes the
directory a property suite is the project's declaration, not borromeanRings's opinion.
Sniffing for `@given` would both misjudge hand-rolled properties and re-introduce
counting through the back door.

### Why declared-but-empty **fails**

A `[verification].properties` directory with no tests is a verification claim with no
evidence behind it. The three candidate verdicts:

- **`pass`** — the ADR-0049 defect verbatim: "I inspected everything and found nothing
  wrong" emitted by a check that inspected nothing. Rejected outright.
- **`noop`** — honest about the *inspection* but not about the *claim*. `noop` means "no
  rule was declared here"; a project that wrote the key declared one. Accepting `noop`
  would make the declaration free: write the key, never write a property, and the
  verification row of the project's evidence stays permanently, silently green-ish.
- **`fail`** — the claim and the evidence disagree, and disagreement is what a gate is
  for. The fix is one line in either direction: write the first property, or delete the
  declaration (governance here is opt-in, and un-declaring is always legitimate).

This is the same shape as `12_secrets` failing closed on a non-git directory (ADR-0042)
and `60_mutation` failing closed on zero evaluated mutants (ADR-0022): *a check whose
input is missing must not report the shape of success.*

### Why a missing runner is `noop` and not `error`

ADR-0049 fixed "a missing tool is `error` (exit 127), never `noop`" for tools invoked
through `run_check` — tools borromeanRings itself requires (ruff, mypy, bandit). The
property runner is not one of those. It belongs to the governed project's own declared
verification stack, which borromeanRings deliberately does not install, so a machine
without Hypothesis is a machine where this lane cannot look — the same situation the
TypeScript and Go lanes are already in for `tsc` and `go` (#67, ADR-0068), and they
report `noop` naming the tool.

`noop` is not a soft pass here: it is printed on the gate line
(`inspected NOTHING: N of M`), carried on the persisted verdict, counted by `status.sh`,
and the receipt names the missing module. The alternative — `error` — would fail every
CI job that has not installed Hypothesis, which is how an opt-in ladder becomes a
mandatory one by accident. **Reversal condition:** if a real project is ever found
passing CI on a `noop` it should have failed on, this becomes `error` and the project
pins its runner.

### What tier 1 deliberately does not control

Hypothesis's search is **randomized**. borromeanRings does not pass `--hypothesis-seed`,
does not set `max_examples`, and does not select a profile:

- fixing the seed would shrink the guarantee to "these inputs, forever", while looking
  stronger;
- setting `max_examples` is choosing a number to hit — the thing this ladder refuses.

The consequence is stated rather than hidden: **the gate is deterministic about the rule
it applies; the search underneath it is not.** A property may be falsified on a later run
than the commit that broke it. That is a property of property testing, not a defect in
the gate, and it is still strictly more than the example suite would have found. A
project that wants determinism sets `derandomize` in its own Hypothesis profile — its
call, in its own repo, on the record.

### Test plan (tier 1)

*Unit* (`tests/unit/test_spine.py`) — `[verification].properties` parses; absent section
⇒ `""`; empty section ⇒ `""`; **unknown key ⇒ `ValueError` naming the key**. Exact
values, 100% line+branch on the added code.

*Integration* (`tests/integration/test_properties_gate.py`) — the real `verify.sh` over
fixture projects: nothing declared ⇒ `noop`, gate green · declared + a passing property
⇒ `pass` (the negative control: this must be a real pass, not a `noop`) · declared + a
falsified property ⇒ `fail` · declared but empty ⇒ `fail`, log carries the vacuity
message · declared path missing ⇒ `fail` · runner shadowed by a stub that raises
`ImportError` ⇒ `noop` whose log names `hypothesis`.

### Dogfood

borromeanRings declares `27_properties` in `[checks].required` with
`[verification].properties = ""`, so on its own repo the check reports **`noop` — rule
off**, and the gate line says so. It is registered rather than omitted because the ladder
is an open invitation this project intends to answer (#146), and a visible `noop` is the
honest rendering of "not opted in yet". No property suite was invented for this repo to
make the check look busy; a fabricated suite would be exactly the vacuity this check
exists to reject.

---

## Tier 2 — SMT (specified, **not built**)

### What a project would declare

```toml
[verification]
properties = "tests/properties"
smt = [
  { module = "meta_harness.ratchet", function = "decide_ratchet",
    contract = "contracts/ratchet.py", bounds = "int:-1000..1000" },
]
```

Each entry names **one function**, the file carrying its pre/post-conditions, and the
**bounded domain** the solver must decide it over. Bounds are mandatory: unbounded
integers, unbounded collections and floats are where symbolic execution stops
terminating, and a check that sometimes never finishes is not a gate. A timeout is
**`fail`**, never `pass` — "the solver gave up" is not "the contract holds".

### What it would prove

For every input in the declared bounds, the post-condition follows from the
pre-condition — or here is a concrete counterexample. That is categorically stronger than
tier 1 over the same domain: tier 1 samples, tier 2 decides. CrossHair is the intended
front end (it reads ordinary Python `assert`/`icontract` conditions and drives z3), so a
project writes contracts in its own language rather than in SMT-LIB.

### What the receipt would carry

`{ "check": "28_smt", "status": …, "functions": [{"name": …, "verdict": "proved" |
"counterexample" | "timeout" | "unsupported", "bounds": …, "counterexample": …,
"solver": "z3 <version>", "seconds": … }] }` — plus the count of functions **declared**
versus **decided**, so a run that silently skipped half the list is visible. A declared
function the tool cannot handle (`unsupported`) is a `fail`, on the tier-1 vacuity
reasoning: a declaration nothing checked must not read as green.

### Why it is not built here

`python3 -c "import z3"` on this machine is `ModuleNotFoundError`, and CrossHair is
absent too. Provisioning them is forbidden by this build's no-install rule, and shipping
a check whose only exercised path is "tool missing ⇒ `noop`" would be shipping an
untested branch as a feature — the check would have no positive-path evidence at all.
Tier 2 therefore ships as this specification plus a follow-up issue, and is built when a
project needs it on a machine where the solver already lives.

### The honest limit

**An SMT proof covers the model you wrote, not the code you shipped** — unless the model
is *extracted from* the code. CrossHair narrows this gap by executing the real Python
symbolically, but the gap never closes: the solver reasons about a mathematical integer
where the program may use a machine word, about a pure function where the deployment has
retries and clocks, and about the version of the source it read. Every discrepancy
between model and artifact is a proof that holds and a system that breaks.

---

## Tier 3 — formal (specified, **not built**)

### What would count

Three artifacts, together — any one alone is worthless:

1. a **statement** file: the theorem, in a proof assistant's language (Lean 4, Dafny,
   Coq), stating what is true of the implementation;
2. a **proof** that a checker accepts **offline**, with no network and no hosted service;
3. a **human review** of the statement, recorded — a named reviewer, a date, and the
   hash of the statement file they read.

### What borromeanRings would gate on

Exactly two facts, both mechanical:

- **the proof checks** — the assistant's checker exits 0 on the artifact, in the version
  the project pins, with no `sorry` / `admit` / `assume` escape hatch left in it
  (a proof with a hole is not a proof, and the checker will happily accept one);
- **the statement is unchanged since review** — the SHA-256 of the statement file matches
  the hash recorded in the review record. A changed statement is an unreviewed statement,
  and the gate fails until a human signs the new one.

borromeanRings would never attempt to judge whether the theorem is the *right* theorem.
It gates the two things a machine can decide, and makes the third — human judgment —
explicit, attributable and re-triggerable.

### The honest limit

**A proof of the wrong theorem is worth nothing**, and it is worth nothing in the most
dangerous way: it comes with a machine-checked certificate. `∀ x, f x = f x` checks
perfectly and says nothing. So the **reviewed artifact is the statement, not the proof.**
The proof is the cheap half to verify (a checker does it); the statement is where all the
risk is, which is why the hash — not the proof — is what the gate pins to a human.

---

## What this ladder cannot do

Plainly: **none of the three tiers tell you the specification is right.**

- Tier 1 tests the property you wrote. If the property is wrong, Hypothesis will
  cheerfully search a million inputs for a counterexample to a false idea of correctness.
- Tier 2 decides the contract you wrote, over the bounds you chose, for the model the
  tool built. Wrong contract, wrong bounds, or wrong model ⇒ a green result and a broken
  system.
- Tier 3 checks the theorem you stated. A checked proof of the wrong theorem is the most
  confident possible way to be wrong.

Each rung raises the **cost of being wrong** in a different direction — tier 1 makes a
wrong implementation cheap to discover, tier 2 makes a wrong implementation hard to hide
inside a bounded domain, tier 3 makes the specification itself an explicit, reviewable,
hash-pinned artifact. None of them raises the cost of *misunderstanding the problem*.
That remains a human job, and the ladder's honest contribution is that it forces the
misunderstanding to be written down somewhere a person can read it.

This is why the ladder is opt-in per tier, why the gate refuses to count anything on it,
and why the verdict vocabulary matters more than the tier: `noop` when nothing was
inspected, `fail` when a claim has no evidence, `pass` only when a runner actually ran
and actually agreed.
