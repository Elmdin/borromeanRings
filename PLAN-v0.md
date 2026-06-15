# Meta-Harness — v0 Plan & Spec

> Status: **DRAFT — awaiting human approval.** No code is written until this plan is approved (§12, principle: plan → approve → implement).
> Scope of this document: v0 only (Build Brief §9 step 1). Everything past the v0 gate is listed under "Explicitly deferred" and is NOT built now.
>
> **Companion docs** (the why/vision, plus the requirements/design/decision artifacts this plan is realized through):
> - [`docs/MANIFESTO.md`](docs/MANIFESTO.md) — **the north star**: why borromeo exists. borromeo is the **meta-harness**; the deep-research and notes tools are separate products built *with* it.
> - [`docs/VISION.md`](docs/VISION.md) — the whole product borromeo (the meta-harness) is meant to become: thesis, the 7 target components, full harness feature set, the self-extension loop, the verification ladder, the red lines.
> - [`docs/ROADMAP.md`](docs/ROADMAP.md) — **every feature, with status** (shipped / in-review / next / deferred). Start here to see the full feature set.
> - [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md) — user stories (INVEST) + Given/When/Then ACs + Quality Attribute Scenarios. These ACs/QAS *are* the v0 gate's acceptance tests.
> - [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — drivers, style, module secrets (information hiding), views, Change Impact Analysis.
> - [`docs/adr/`](docs/adr/README.md) — Architecture Decision Records for the load-bearing decisions (substrate, hosting, hardware, stack, the registry/adapter seam).
> - [`docs/TEST-PLAN.md`](docs/TEST-PLAN.md) — test plan derived from the design: testability (controllability/observability), the red/green matrix (= §9.2), QAS tests, mutation-vs-coverage rationale.
> - [`docs/PROCESS.md`](docs/PROCESS.md) — how borromeo itself is built: risk-driven + incremental, the gate as a mechanized Definition of Done, TDD rhythm, and responsible-GenAI operating rules.
> - [`docs/DELAYED-DECISIONS.md`](docs/DELAYED-DECISIONS.md) — the §11 open questions, tracked with a default + what's needed to resolve each.

---

## 1. Locked setup decisions

| Choice | Decision | Consequence |
|---|---|---|
| Substrate | **Claude Code** | Gate is expressed through native hooks (Stop / PostToolUse / PreToolUse). |
| Model hosting | **Frontier API** | Code leaves the machine on every model call. Data-locality posture is documented, not mitigated, in v0. |
| Hardware | **WSL2 laptop, no GPU** | No local model. The harness is pure local orchestration + deterministic checks; inference is remote. |
| First stack | **Python** | `verify.sh` targets Python: `ruff format` + `ruff check` + `mypy` + `pytest`/coverage + `bandit`. |

**The first project the harness governs is its own repo (`borromeo/`).** It is a Python project. We dogfood from commit one: the harness's own development is gated by the harness's own `verify.sh` via the Stop hook.

---

## 2. v0 mission (and the line we will not cross)

Deliver the smallest thing that proves the core thesis: **a best-practice standard converted from a request into a deterministic gate a change cannot pass until satisfied** (Brief principle 1), running identically whether a human or Claude Code produced the change (principle: the verifier is external to the generator, principle 5).

v0 is **one repo, one stack (Python), one gate, on Claude Code.** It is NOT the critic, NOT the config/policy engine, NOT orchestration, NOT prompt rewriting, NOT the executor abstraction. Those are later steps in §9 and are deferred (see §9 of this doc).

The one capability we deliberately seed early even though the full feature is deferred: **receipts / audit plumbing** (Brief §11 says build the logging/receipt plumbing from v0 so self-assurance can be added later without re-architecting). v0's receipts are minimal but real.

---

## 3. Architecture of v0 (only the components that exist now)

Of the 7 components in Brief §3, v0 instantiates exactly three, as thin seams:

1. **Verifier registry (minimal)** — `verify.sh` plus a `checks/` directory. Each check is one script with a uniform contract (run, exit non-zero on failure, emit a receipt). This is the product; it is built to grow.
2. **Outer gate** — the same `verify.sh` is the single source of truth, invoked by (a) the Claude Code Stop hook and (b) directly by a human / CI. One gate, identical behavior regardless of author.
3. **Spec/context layer (minimal)** — a short `AGENTS.md` (non-obvious rules only) committed to the repo.

The Generator adapter, Executor interface, Orchestrator, and Config/policy spine are **interfaces we are NOT abstracting yet.** In v0 the generator is Claude Code itself, the executor is the local shell, and the orchestrator loop is the Stop hook. We do not build abstraction layers ahead of need (Brief: "no premature building").

---

## 4. Repository layout (v0)

```
borromeo/
├── AGENTS.md                      # non-obvious rules only; agent-neutral
├── PLAN-v0.md                     # this spec
├── README.md                      # what this is, how to run the gate
├── verify.sh                      # THE GATE — orchestrates checks, fails closed
├── pyproject.toml                 # ruff / mypy / pytest / coverage / bandit config + deps
├── .gitignore
├── .python-version                # pinned interpreter (optional)
├── checks/                        # one script per check; uniform contract
│   ├── _lib.sh                    # shared: receipt emitter, run-and-record helper
│   ├── 00_build.sh                # import/installability check
│   ├── 10_format.sh              # ruff format --check
│   ├── 20_lint.sh                # ruff check
│   ├── 30_typecheck.sh           # mypy
│   ├── 40_test.sh                # pytest + coverage floor
│   └── 50_security.sh            # bandit
├── .claude/
│   ├── settings.json              # hook wiring (committed → travels with repo)
│   └── hooks/
│       ├── stop_gate.sh           # runs verify.sh; iteration cap + escalation
│       ├── post_edit_format.sh    # ruff format on Edit|Write|MultiEdit
│       └── pre_bash_guard.sh      # block obviously dangerous bash (defense in depth)
├── src/
│   └── meta_harness/
│       ├── __init__.py
│       └── sample.py              # a small REAL module so the gate has real code to check
├── tests/
│   └── test_sample.py             # real test; proves the test gate fires
└── .meta-harness/                 # audit plumbing (gitignored except .gitkeep)
    └── receipts/                  # one dir per run; one JSON receipt per check
```

`src/meta_harness/sample.py` is intentionally minimal but real (e.g. a tiny pure function with a docstring and type hints) so the gate verifies actual code, not an empty repo. It is replaced by real harness modules as the project grows; it exists in v0 only to make the gate demonstrably exercise every check.

---

## 5. `verify.sh` design (the product core)

**Contract:** `verify.sh` runs every check in `checks/` in filename order, captures each result as a receipt, and exits `0` only if **every declared check produced a receipt with exit code 0**. Any failing check, any missing receipt, or any missing required tool ⇒ non-zero exit. This is **fail-closed** (Brief §11): absence of proof = failure, never pass-on-trust.

**Per-check contract (uniform, so the registry can grow):**
- Each `checks/NN_name.sh` runs one tool, writes its raw stdout+stderr to `.meta-harness/receipts/<run-id>/NN_name.log`, and writes a receipt `NN_name.json`:
  ```json
  {
    "check": "test",
    "command": "pytest --cov=src --cov-fail-under=80",
    "exit_code": 0,
    "log": ".meta-harness/receipts/<run-id>/40_test.log",
    "status": "pass"
  }
  ```
- A check whose tool is **not installed** writes `status:"error"` and exits non-zero (v0 treats a missing required tool as a hard failure — no silent skips, Brief "no silent caps"). A `setup.sh`/documented `pip install` provisions the toolchain.

**The v0 checks (Python), each mapped to a Brief best-practice bucket (a) mechanically-checkable:**

| # | Check | Tool / command | Floor enforced |
|---|---|---|---|
| 00 | Build / installable | `pip install -e . -q` then `python -c "import meta_harness"` (or `compileall`) | Package imports cleanly |
| 10 | Format | `ruff format --check .` | No unformatted files |
| 20 | Lint | `ruff check .` | No lint violations |
| 30 | Typecheck | `mypy src` | No type errors |
| 40 | Test (coverage *reported*) | `pytest` + `--cov=src` (reported, ratchet — not an absolute %) | Tests pass; coverage recorded in receipt + non-regression ratchet. **No absolute % gate** — see note below. Mutation testing (the real signal, §8) deferred to a later step. |
| 50 | Security | `bandit -q -r src` | No findings at/above configured severity |

`run-id` is a counter/sequence (no `Date.now()` dependency required; a monotonic dir name or git-describe is fine). A top-level `manifest.json` lists the expected check set; `verify.sh` cross-checks that every expected check emitted a receipt — a check that never ran (crash, skip) ⇒ overall fail. This is the embryonic version of the §11 config-compliance check ("every declared requirement has an executed-and-passed receipt").

**Output:** human-readable PASS/FAIL summary table to stdout; on failure, a concise list of which checks failed and the path to their logs. Exit code is the contract; the table is for humans.

---

## 6. Claude Code hook wiring (verified against official docs)

All three hooks point at scripts in `.claude/hooks/`, registered in committed `.claude/settings.json` so the gate travels with the repo. Commands use `${CLAUDE_PROJECT_DIR}` and a `timeout` generous enough for the test suite.

### 6.1 Stop hook — the generate→verify→retry gate (the heart of v0)
`stop_gate.sh` receives Stop-event JSON on stdin. Logic:

1. Parse `stop_hook_active`. **If `true`, `exit 0`** (let the agent stop) — this is the documented infinite-loop escape hatch.
2. Maintain a per-session attempt counter at `.meta-harness/stop_attempts/<session_id>`.
3. Run `verify.sh`.
   - **Pass** → reset the counter, `exit 0` (allow stop). The agent only finishes when the code is green. Evidence-based completion (Brief principle 6).
   - **Fail** → increment counter.
     - If counter `< CAP` (default **3**) → block: print the failing-check summary to **stderr** and **`exit 2`**. Per the verified contract, exit 2 + stderr feeds the failures back to the model, which keeps working. This *is* the retry loop, for free.
     - If counter `≥ CAP` → **escalate**: print a clear `ESCALATION: gate failed N times, handing control to human` message and `exit 0` (stop, do not loop forever). Bounded retry + human escalation (Brief §3 component 5: "never an unbounded retry loop"). Claude Code's own 8-block cap is a backstop below our cap of 3.

The cap (3) and the escalation behavior are config constants in the script, surfaced for tuning.

### 6.2 PostToolUse hook — auto-format on edit
`post_edit_format.sh`, matcher `Edit|Write|MultiEdit`. Reads `tool_input.file_path`; if it's a `.py` file, runs `ruff format` on just that file. Exit 0. (Keeps the format check from ever being the reason the Stop gate blocks; cheap, per-edit.)

### 6.3 PreToolUse hook — dangerous-command guard (defense in depth)
`pre_bash_guard.sh`, matcher `Bash`. Reads `tool_input.command`; if it matches a small deny-list (`rm -rf /`, `rm -rf ~`, force-push to default branch, `git reset --hard` on dirty tree, `DROP TABLE`, fork bombs), denies via the verified PreToolUse JSON:
```json
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"..."}}
```
Otherwise exit 0 (normal flow; user/permission prompt still applies). This aligns with the CLAUDE.md `/careful` safety posture. Deny-list is intentionally tiny and conservative in v0 — it is a guard, not the policy engine.

### 6.4 `settings.json` shape (verified)
```jsonc
{
  "hooks": {
    "Stop": [
      { "hooks": [ { "type": "command", "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/stop_gate.sh", "timeout": 600 } ] }
    ],
    "PostToolUse": [
      { "matcher": "Edit|Write|MultiEdit",
        "hooks": [ { "type": "command", "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/post_edit_format.sh", "timeout": 60 } ] }
    ],
    "PreToolUse": [
      { "matcher": "Bash",
        "hooks": [ { "type": "command", "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/pre_bash_guard.sh", "timeout": 30 } ] }
    ]
  }
}
```

---

## 7. `AGENTS.md` (v0 contents — non-obvious rules only)

Kept short and agent-neutral (so it lifts onto OpenCode/Hermes later). It states only what an agent could not infer from the code:
- The gate is `verify.sh`; **you are not done until it exits 0** — show its output as evidence, never claim success without it (Brief principle 6).
- Do not weaken, disable, or bypass any check or hook to make the gate pass. (Integrity; precursor to §11 tamper-evidence.)
- Failures become permanent checks: when a defect escapes, add a regression test/check before fixing (Brief principle 4 + CLAUDE.md "write a failing test first").
- Plan before code for changes touching 3+ files; the human approves specs before implementation (Brief §12).
- Tests must pass and meaningfully assert behavior; coverage is tracked and may not regress — there is **no absolute coverage % target** (gaming a number is not the goal, §8). Functions <50 lines; files <800 lines (enforced where mechanical, requested where not).

---

## 8. Engineering standards this system holds *itself* to (§12 — dogfooding)

The harness is its own first governed project. Concretely, from commit one:
- **Plan → approve → implement.** This document is the first instance. Every meaningful future change gets a spec approved by the human before code (Brief §12, §6.3).
- **The repo passes its own `verify.sh` before anything lands.** Same gate it imposes on others. No exceptions for "it's just the harness."
- **Incremental, reviewable, evidence-backed.** Small steps; each shows the gate output proving it works.
- **The harness's own changes get human approval to merge** (Brief §6.3: no autonomous self-rewriting).
- **Failures→checks** applies to this repo too: any escaped defect becomes a new check in `checks/`.
- **No premature building.** We stop at the v0 gate and prove it before adding the critic, spine, etc.

---

## 9. v0 acceptance criteria (how we prove it works end-to-end)

v0 is "done" only when **all** of the following are demonstrated with evidence (not asserted):

1. **Green path:** On the sample module + passing test, `./verify.sh` exits 0 and writes one receipt per check, all `status:"pass"`, plus a manifest confirming every expected check ran.
2. **Each gate actually bites (red path, one per check):** Introduce, one at a time, (a) a formatting violation, (b) a lint violation, (c) a type error, (d) a failing test, (e) a coverage regression (new untested code lowering the ratchet), (f) a bandit finding — and show `verify.sh` exits non-zero with the correct failing check identified in its receipt. This proves the standards are real gates, not decoration.
3. **Missing-receipt fails closed:** Simulate a check that crashes without emitting a receipt → `verify.sh` still exits non-zero (proves §11 fail-closed plumbing).
4. **Stop-hook loop works:** In a live Claude Code session, deliberately leave a failing test; confirm the Stop hook blocks the stop, feeds the failure back, the agent fixes it, and only then is allowed to stop. Confirm the attempt counter caps at 3 and escalates rather than looping.
5. **PreToolUse guard works:** A blocked dangerous command is actually denied with the reason surfaced.
6. **Author-agnostic:** `./verify.sh` run by hand produces the identical result to the hook-invoked run (same gate, regardless of author — principle 5).

Each criterion is demonstrated by pasting the actual command + output (the harness's own evidence rule applied to building the harness).

---

## 10. Explicitly deferred (NOT in v0 — listed so scope stays honest)

Per Brief §9 build order, the following are out of v0 and built only after the v0 gate is proven, one at a time, each justified by a real need:
- External rubric critic / separate-model verifier (§9.2).
- Config/policy engine — the declarative spine (§9.3). *v0's manifest + receipts are the seed, not the spine.*
- Research + safe prompt-refinement front-of-loop (§9.4).
- Instrumentation + A/B measurement loop (§9.5).
- Orchestration / parallelism / worktrees (§9.6).
- Cloud-sandbox executor, offline prompt optimization, multi-harness substrate (§9.7).
- Full self-assurance layer (§11) — only the receipt/audit *plumbing* is seeded in v0; tool-use instrumentation, config-compliance diffing, tamper-evidence, and adversarial self-testing come later.

---

## 11. Open questions for the human (before scaffolding)

1. **Repo name / packaging:** keep working name `borromeo` and Python package `meta_harness`? Any preferred name?
2. **Coverage approach (revised):** v0 uses coverage *reported + non-regression ratchet*, NOT an absolute % gate; mutation testing (the real signal, §8) is deferred to a later step. This consciously overrides the CLAUDE.md 80% default — confirm you're good with it.
3. **Security tool:** `bandit` only for v0, or also wire `semgrep` if available (heavier install on the WSL2 box)? Recommendation: `bandit` only in v0, add `semgrep` later.
4. **Git:** initialize the repo as part of scaffolding (`git init`, first commit = this plan + scaffold)? The environment currently reports it is not a git repo.

---

## 12.5 Core design principle — self-extension (build → gate → adopt)

borromeo is intended to **compound its own capabilities** over time: it builds a new capability, gates it, and — on human approval — registers it into its own feature set, becoming more capable for the next build. The first planned self-adopted capability is **deep-research / synthesis** (Brief §4 names this explicitly). This is a *core* feature, not a nice-to-have.

**The loop:** borromeo builds capability X → X passes borromeo's own gate (+ external critic + human approval) → X is registered as a plugin in borromeo's registry → borromeo uses X to build the next capability.

**The hard line (Brief §6.3):** this is self-*extension* (new capability, human-approved merge, fully auditable), **never** self-*rewriting* (autonomous modification of its own core/gates). Pragmatic self-improvement, not recursive runaway. The human approves every merge to borromeo itself.

**Stricter gate for self-adopted capabilities:** once a capability becomes part of borromeo's *own* feature set, it is part of the **trust root** — a bug there silently corrupts everything borromeo verifies afterward. So anything borromeo adopts into itself must pass the **same-or-stricter** gate than code it produces for others (full check suite + external critic + explicit human sign-off, every time). Ties into the §11 integrity / tamper-evidence layer.

**v0 implication (small, real):** keep the `checks/`-style registry pattern clean and pluggable so that, later, *tools/capabilities* can be registered the same way *checks* are. We do NOT build the tool registry in v0 — we only avoid an architecture that would make adding it a rewrite. The capability-building (Tools+MCP, Brief §4) and adoption mechanics are a deferred step (see §10).

## 13. What happens after you approve

On approval I scaffold exactly §4's tree and nothing more, then drive the §9 acceptance criteria to green with pasted evidence, then stop and hand back. No modules beyond the gate until v0 is proven and you direct the next step.
