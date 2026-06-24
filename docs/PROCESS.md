# borromeanRings — Development Process & Operating Rules

> CS130 framing (Part 3 L10 process choice; Part 5 L16 Scrum/DoD, L19 responsible GenAI). This
> doc answers "how do we build borromeanRings itself, with best practices." It governs the *building*;
> `REQUIREMENTS.md`/`ARCHITECTURE.md`/`TEST-PLAN.md` govern the *thing being built*.

---

## 1. Process: Risk-Driven, incremental

Per Fairbanks' **Risk-Driven Design** (Part 3 L10): the amount of upfront design scales with **risk
= decisions that are hard to change**. borromeanRings's hard-to-change decisions — substrate, the gate
contract, the substrate Adapter seam, the first stack — got upfront design (ADRs + `ARCHITECTURE.md`).
Everything else stays **lean/evolutionary**: design emerges per increment.

- **v0 is the smallest increment that proves the thesis** (one gate, one stack, one substrate). We
  do **not** build deferred components (critic, config spine, orchestration) until v0 is proven —
  building them now would be Lean "extra features" waste (Part 3 L10).
- Each increment: build → pass the gate → demo with evidence → human feedback → next increment.
- Maintain two backlogs (Part 3 L10): a **feature backlog** and a **technical-debt backlog**;
  "failures become checks" feeds the latter.

## 2. The gate is a mechanized Definition of Done

borromeanRings's `verify.sh` **is a Scrum Definition of Done, mechanized** (Part 5 L16). A change is not
"done" until it passes — formatted, lint-clean, type-clean, tests pass, security-clean, coverage not
regressed. The Scrum research is the direct mandate: *"test quality as part of the Definition of Done"*
and *"be proactive about non-functional requirements"* (agile teams ship more **non-functional**
defects — Rahman et al., SAC '24). borromeanRings answers both by encoding **QAS as gate checks**.

## 3. TDD rhythm

Red → Green → Refactor (Part 3 L10 / Part 5 L18). For borromeanRings this is literal: the `TEST-PLAN.md`
red-path matrix is "write the failing test first"; the gate enforces Green; refactor under green.
TDD fits here because the gate's behavior is **well-defined with binary outcomes** — exactly where
TDD works well.

## 4. How borromeanRings is built *by AI agents* — responsible-GenAI rules (Part 5 L19)

borromeanRings's reason to exist is the research finding that **GenAI is an amplifier, not a fixer**: with
automated testing + CI + gates, AI accelerates a team; without them it ships debt faster (>15% of AI
commits introduce ≥1 issue; ~24% survive — arXiv 2603.28592). **borromeanRings is the foundation that flips
AI from debt-generator to accelerator** — so it must hold *itself* to these rules while being built:

- [ ] **Supervisor mentality.** A human approves every merge into borromeanRings itself. This is
      self-**extension** (new capability, human-approved), never self-**rewriting** of the core/gate.
      The AI agent is a fully-supervised junior dev; the supervising human is responsible for all code.
- [ ] **Verifier external to the generator** (QAS-2): the thing that judges a change is never the
      thing that wrote it. The gate runs identically regardless of author; the external critic
      (deferred) extends this.
- [ ] **Security review by default.** The `50_security` check is non-negotiable — AI writes
      less-secure code while *believing* it is secure (Perry et al., CHI 2023); complexity increases
      injected vulnerabilities even when "improve security" is requested.
- [ ] **Explainability rule.** Never land code (AI- or human-written) that the lander can't explain.
- [ ] **Decompose + precise context.** Keep each task small; prompt Role → Task → Context →
      Instructions; supply acceptance criteria as success criteria; give exact context, no more/less.
- [ ] **Right tasks for AI:** scaffolding, tests, refactoring, docs, simple debugging — *tiresome to
      do, easy to verify, low cost of being wrong.* Humans lead requirements, architecture, and
      security-critical work.
- [ ] **Loosely-coupled, modular design** (information hiding): AI's productivity gains are amplified
      in modular systems and absent in tightly-coupled ones (DORA 2025). `ARCHITECTURE.md`'s module
      secrets and the check registry are this principle applied to borromeanRings itself.

## 5. Verification is continuous, evidence-backed

Every acceptance criterion is demonstrated by pasting the actual command + output (PLAN-v0 §9) — the
harness's own evidence rule applied to building the harness. No claim of "done" without the gate's
output as proof.
