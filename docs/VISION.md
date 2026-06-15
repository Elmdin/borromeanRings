# borromeo — Vision (the north star)

> This is the whole product borromeo is meant to become. The originating *why* is in
> [`MANIFESTO.md`](MANIFESTO.md); *what is built vs. deferred and in what order* is in
> [`ROADMAP.md`](ROADMAP.md); v0 specifics are in `PLAN-v0.md` and the rest of `docs/`.

## 0. Scope — borromeo is the meta-harness that enhances agents
Per the [Manifesto](MANIFESTO.md), **borromeo is the meta-harness**: it enhances any existing AI
agent so it builds software — and does everything it already does — better. It *enhances* agent
capabilities (code → gates; prompts → rewriting; **deep research → coverage + verification**); it
does not rebuild them.

The one thing borromeo is **not** is an end-user application: the **notes/Kernel** (organize all your
plans/docs/social media into a second brain) is a **separate product built *with* borromeo**, with
its own repo. This document specifies borromeo (the harness), including its deep-research enhancement.

## 1. Thesis (Layer 1)
borromeo is a **model- and harness-agnostic meta-harness**: a governing quality layer that wraps
any AI coding agent + any model and enforces engineering best practices as **deterministic gates**,
not prompt requests. Mental model: an **assembly line with quality gates** — the agent is an
interchangeable worker, the gate/loop is the product. Core move: convert each standard from a
*request* into a *gate a change cannot pass until satisfied*. The differentiator is a config-driven
**spine** that enforces declared invariants on every run, across every harness.

Why it matters: research shows GenAI is an **amplifier, not a fixer** — with automated tests + CI +
gates it accelerates a team; without them it ships debt faster. borromeo is the foundation that
supplies those guardrails, so it flips AI from debt-generator to accelerator. (See `PROCESS.md`.)

## 2. Target architecture — the 7 components
v0 instantiates the first three as thin seams; the rest are deferred (see `ROADMAP.md`).

| # | Component | Role | v0 status |
|---|---|---|---|
| 1 | **Verifier registry** | Pluggable checks under a uniform contract | ✅ shipped |
| 2 | **Outer gate** | Single fail-closed gate; same verdict for any author | ✅ shipped |
| 3 | **Spec/context layer** | Agent-neutral rules (`AGENTS.md`) | ✅ shipped |
| 4 | **Generator adapter** | Abstraction over the AI agent producing changes | ⏳ deferred (v0: Claude Code) |
| 5 | **Executor interface** | Abstraction over where work runs | ⏳ deferred (v0: local shell) |
| 6 | **Orchestrator** | The generate→verify→retry loop, parallelism, worktrees | ◑ partial (v0: Stop hook) |
| 7 | **Config/policy spine** | Declarative invariants per project/harness | ⏳ deferred (v0: manifest + receipts seed) |

## 2a. Full harness feature set (Layer 1 target)
The capabilities borromeo must eventually have — an **extension to any existing harness**, working
with **any LLM + any harness combination**, plug-and-play with existing skills/tools:

- **Best SWE practices as gates** — ✅ shipped (the v0 gate).
- **Config-focused enforcement** — when you declare a specific account, constraint, or requirement,
  it is enforced on **every** run, always (the config/policy spine).
- **Mathematical verification of code *and* claims** — code via the verification ladder
  (mypy → Hypothesis → CrossHair/SMT → mutation → formal); **claims** (factual assertions, e.g. from
  research) verified too — distinct from code correctness.
- **Prompt rewriting + multi-prompting** — improve the **user's in-the-moment prompt** to preserve
  its intent and make it better. The rewriting is **performed by the wrapped agent**, not by
  borromeo; borromeo **enforces that it happens well** — per best agentic-engineering + SE practices,
  the declared context (the spine), and anything that improves results. Plus the ability to drive
  multiple prompts/passes.
- **Deep-research enhancement** — most agents already do deep research; borromeo **improves their
  built-in research**: multi-engine + comprehensive coverage, query mutation, a completeness critic
  ("don't miss anything"), full step-by-step visibility, and **fact-check + deterministic gates** on
  the findings (no unverified claim survives). See `SPEC-deep-research.md`. *(Active workstream.)*
- **Tool access + MCP + plug-and-play** — reach external/internal tools and MCP servers; plug in any
  existing feature, skill, or tool; compose with other harnesses.
- **Ever-growing & research-driven** — can apply existing or new research; **adopts the tools it
  builds** when asked.
- **Multi-prompt / multi-model / multi-harness agnosticism** — never bound to one model or harness.

## 3. The self-extension loop (a core feature, not a nice-to-have)
borromeo **compounds its own capabilities**: it builds capability X → X passes borromeo's own gate
(+ external critic + human approval) → X is registered as a plugin in borromeo's registry → borromeo
uses X to build the next capability. The first planned self-adopted capability is
**deep-research / synthesis**.

**The hard line:** this is self-**extension** (new capability, human-approved merge, fully
auditable), **never** self-**rewriting** (autonomous modification of its own core/gates). The human
approves every merge to borromeo itself (mechanized but never originated by borromeo — see
`adr/0007-gated-explicit-merge.md`). Anything borromeo adopts into itself becomes part of the
**trust root**, so it faces a **same-or-stricter** gate than ordinary code.

## 4. The verification ladder
Practical, escalating rigor — climb only as far as a module's risk warrants:
**mypy → Hypothesis (property tests) → CrossHair (SMT) → mutation testing → formal (Lean/Dafny)**.
Formal verification is **deferred and opt-in** for tagged critical modules only (undecidability +
cost); it is never a general gate. Coverage is a non-regression ratchet, never an absolute % target
(gaming a number is not the goal).

## 5. The self-assurance layer
borromeo must be **trustworthy about its own enforcement**: tool-use instrumentation,
config-compliance diffing ("every declared requirement has an executed-and-passed receipt"),
tamper-evidence (no check may be silently weakened/skipped), and adversarial self-testing. v0 seeds
only the **receipt/audit plumbing** so this can be added later without re-architecting.

## 6. Red lines (what borromeo must never do)
- Never pass on trust — **absence of proof = failure** (fail-closed).
- Never let the generator be its own verifier — the **verifier is external to the generator**.
- Never autonomously rewrite its own core/gates — **human-approved merges only**.
- Never run an **unbounded** retry loop — bounded, then escalate to a human.
- Never weaken/disable a check to make the gate pass.
- **Never suppress the wrapped agent's autonomy.** Many harnesses plan/decide better than borromeo
  would; borromeo enforces *declared invariants on outcomes* (gates + config-compliance), never *how*
  the agent thinks. It governs the *what*, defers the *how* to the agent where the agent is better.
