# borromeanRings — Test Plan (v0)

> CS130 framing (Part 3 L12–13 + Part 5 L18, L20): the test plan is **derived from the design** —
> every test traces back to a requirement (`REQUIREMENTS.md` AC/QAS) and a design decision
> (`ARCHITECTURE.md`). **Testability = Controllability + Observability**, designed in, not bolted on.
> Tests prove the *presence* of bugs, never their absence — so every escaped defect becomes a new
> check ("failures become permanent checks").

---

## 1. Testability of borromeanRings itself

| Property | How v0 achieves it |
|---|---|
| **Controllability** | The input is the working tree — a test drives the gate into a chosen failure state by **injecting exactly one defect** (a format error, a type error, …). `CAP` and tool config are constants, injectable for the loop tests. The substrate (Claude Code) is a **Depended-On Component**: because `verify.sh` is substrate-neutral (ADR-0005), gate tests invoke it **directly**, needing no harness — that *is* the seam. |
| **Observability** | **Receipts are the observability mechanism**: each check's verdict, command, exit code, and log path are recorded; the gate's exit code is the top-level observable; the manifest cross-check makes "a check never ran" observable. (Logs of critical events — Part 5 observability checklist.) |

**DOCs & test doubles (Part 5 L18):** the model-provider API and the Claude Code hooks are DOCs.
Gate-level tests touch neither (verify.sh is substrate-neutral) → no doubles needed. The Stop-hook
loop test (US-4) deliberately exercises the *real* agent loop as a system test.

---

## 2. Test levels (derived from the Module/Component views)

| Level | Target | Representative cases |
|---|---|---|
| **Unit** | receipt emitter (`checks/_lib.sh`) | Given a command + exit code → emits a well-formed receipt. **Boundary:** tool missing → `status:"error"`, non-zero (no silent skip). |
| **Component** | each `checks/NN_*.sh` in isolation | **Green:** clean input → pass receipt, exit 0. **Red:** one injected violation → fail receipt, exit non-zero. |
| **Integration** | `verify.sh` aggregation | all-pass → exit 0 + manifest complete; one check fails → exit non-zero, failing check named; **missing receipt → fail-closed**; manifest mismatch → fail. |
| **System** | live Claude Code session | Stop-hook loop (US-4); PreToolUse guard denies a dangerous command (US-5); author-agnostic verdict (US-2). |

---

## 3. The v0 red/green matrix (this IS "write the failing test first" — TDD Red, Part 3)

Black-box, derived from the spec — one representative defect per check (equivalence + BVA). Maps
directly to PLAN-v0 §9.2. Each row: inject the defect, assert the **named** check fails.

| Check | Green path (→ pass, exit 0) | Red path (inject → that check fails, exit ≠ 0) | Trace |
|---|---|---|---|
| 00 build | package imports cleanly | introduce an import error | AC-1.1 / AC-1.2 |
| 10 format | already `ruff format`-clean | add an unformatted line | AC-1.2 |
| 20 lint | no violations | add an unused import / lint violation | AC-1.2 |
| 30 type | `mypy` clean | add a type error | AC-1.2 |
| 40 test | tests pass | break a test's expected behavior | AC-1.2 |
| 40 cov (ratchet) | coverage ≥ recorded baseline | add untested code that lowers it | QAS-7 |
| 50 security | no `bandit` findings | add a flagged insecure call | AC-1.2 |

Plus the two structural tests that prove the *gate*, not a tool:
- **Missing-receipt fail-closed** (AC-3.1 / QAS-1): a check crashes without a receipt → `verify.sh`
  still exits non-zero, naming the check that produced no proof.
- **Author-agnostic** (AC-2.1 / QAS-2): hook-invoked verdict == hand-invoked verdict on the same tree.

---

## 4. Quality-attribute tests (Scenario → Measure, Part 5 L18)

| QAS | Control (inject) | Observe (assert) |
|---|---|---|
| QAS-1 integrity | delete/corrupt a pass receipt | gate exits non-zero |
| QAS-5 fail-closed | required tool absent | hard failure, never a silent skip |
| QAS-6 bounded autonomy | force repeated gate failure in a session | ≤ CAP attempts, then escalation message + stop |
| QAS-2 determinism | two invokers, same tree | identical verdict |

---

## 5. Oracle strength — why coverage is a ratchet, not a target (Part 3 L12)

Coverage measures whether lines/branches **executed**, not whether assertions **catch bugs** —
100% coverage with weak assertions still passes broken code. The real signal is **mutation testing**
(inject a mutant; does any test kill it?), which measures oracle strength (Jain et al., ISSRE 2023).
v0 therefore **records coverage + ratchets it** (may not regress) and defers mutation testing as the
next real signal — it does **not** set an absolute % (that would be a Goodhart proxy). This is the
test-design justification for QAS-7 / DD-1.

---

## 6. Process integration

- **TDD rhythm:** the §3 red cases are the failing-tests-first; the gate enforces Green; refactor
  under green (Part 3 / Part 5 L18 Red→Green→Refactor).
- **Regression / CI:** every check runs on every gate invocation — the gate *is* the regression suite.
- **Failures→checks (Knight Capital lesson, Part 3 L12):** the $440M dead-code-flag failure is the
  cautionary tale for "no silent skips" and fail-closed. Any defect that escapes the gate becomes a
  new red-path row here + a new check.
- Real usage will still surface unanticipated scenarios (the black-box bar parable) — the gate is a
  floor, not a ceiling.
