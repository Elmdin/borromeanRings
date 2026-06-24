# borromeanRings — Requirements (v0)

> CS130 framing (Part 1): requirements state **what**, never **how**. Functional needs are
> user stories (INVEST) with **Given/When/Then** acceptance criteria; quality attributes are
> **Quality Attribute Scenarios (QAS)** with a measurable response. These ACs/QAS *are* the
> v0 gate's acceptance tests — the requirement and the test are the same artifact (traceability).
>
> Scope: v0 only. Roles: **Author** (a human or an AI coding agent producing a change — they are
> deliberately indistinguishable to borromeanRings), **Maintainer** (a human governing the repo).

---

## Functional requirements (user stories)

### US-1 — One gate, regardless of author
```
As an Author,
I want a single command that decides whether my change meets the declared standards,
so that "done" means "verifiably correct," not "claimed correct."
```
**AC-1.1**
```
Given a change that satisfies every declared check,
When  the gate runs,
Then  it exits 0 and writes one pass receipt per check plus a manifest confirming every
      expected check ran.
```
**AC-1.2**
```
Given a change that violates exactly one declared standard,
When  the gate runs,
Then  it exits non-zero and the failing check is identified by name in its receipt.
```
INVEST note: *Negotiable* — the story names no tool/language; those are design decisions (see ADRs).

### US-2 — Author-agnostic verdict
```
As a Maintainer,
I want the gate to produce the identical verdict whether a human or an AI agent ran it,
so that the verifier is external to the generator and cannot be talked into passing.
```
**AC-2.1**
```
Given the same working tree,
When  the gate is invoked by the Claude Code hook and again by hand,
Then  the pass/fail verdict is identical.
```

### US-3 — Fail closed on missing proof
```
As a Maintainer,
I want absence of evidence to count as failure,
so that a crashed or skipped check can never be mistaken for a passing one.
```
**AC-3.1**
```
Given a check that crashes without emitting a receipt,
When  the gate runs,
Then  the gate exits non-zero (missing receipt ⇒ fail), naming the check that produced no proof.
```

### US-4 — Bounded retry, then human escalation
```
As an Author working inside the agent loop,
I want failures fed back to me to fix, but capped,
so that the loop self-corrects without ever running unbounded.
```
**AC-4.1**
```
Given a failing gate inside a live agent session and an attempt count below the cap,
When  the agent tries to stop,
Then  the stop is blocked and the failing-check summary is fed back for another attempt.
```
**AC-4.2**
```
Given the attempt count has reached the cap,
When  the gate still fails,
Then  control is handed to the Maintainer with an explicit escalation message (no further looping).
```

### US-5 — Dangerous-command guard (defense in depth)
```
As a Maintainer,
I want obviously destructive shell commands blocked before they run,
so that an agent cannot wipe the repo or force-push while working.
```
**AC-5.1**
```
Given a command matching the conservative deny-list (e.g. rm -rf /, force-push to default),
When  the agent attempts it,
Then  it is denied and the reason is surfaced to the agent.
```

### US-6 — Auditable receipts
```
As a Maintainer,
I want every gate run to leave a durable record of what was checked and what each check found,
so that the self-assurance layer can be added later without re-architecting.
```
**AC-6.1**
```
Given any gate run,
When  it completes,
Then  a per-run directory holds one receipt (check name, command, exit code, status, log path)
      per check and a manifest of the expected check set.
```

---

## Quality Attribute Scenarios (the load-bearing walls)

> Each QAS = **Stimulus → measurable Response**. These are the "-ilities" a *meta-harness* lives
> or dies on; per CS130 they get more design attention than features because they are hardest to
> change later. (See `ARCHITECTURE.md` for how the design satisfies each.)

| ID | Quality attribute | Stimulus | Response measure (v0) |
|---|---|---|---|
| QAS-1 | **Integrity / tamper-evidence** | A required check does not produce a pass receipt | Gate exits non-zero; no pass-on-trust path exists |
| QAS-2 | **Determinism / author-agnosticism** | Same tree verified via hook vs. by hand | Identical verdict; no input distinguishes human from agent |
| QAS-3 | **Extensibility — add a check** | A new check is added | 1 new `checks/NN_*.sh` + 1 manifest entry; **0 edits** to `verify.sh` |
| QAS-4 | **Extensibility — add a substrate** (future) | A new harness (e.g. OpenCode) is targeted | New adapter only; **0 edits** to `checks/` or `verify.sh` |
| QAS-5 | **Fail-closed reliability** | Any check tool is missing or a check crashes | Hard failure (non-zero), never a silent skip |
| QAS-6 | **Bounded autonomy** | Gate fails repeatedly in a session | ≤ CAP (default 3) attempts, then escalate and stop |
| QAS-7 | **Test signal quality** | New untested behavior is added | Coverage recorded per run and may not regress (ratchet); **no absolute % target** — gaming a number is not the goal |

---

## Explicit non-requirements (v0)

To keep scope honest (Goals + Non-Goals define scope, Part 1 L4):
- Not the external critic, config/policy engine, orchestration, prompt rewriting, or executor
  abstraction — all deferred (PLAN-v0 §10).
- Not multi-language; Python only (ADR-0004).
- Not data-locality mitigation; documented, not solved (ADR-0002).
- No absolute coverage-% gate (QAS-7, ADR-0006-pending).
