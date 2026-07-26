# SPEC — T2 external rubric critic (seam)

> Status: spec for the **seam** (the reusable mechanism), per the enforcement coverage map's
> T2 tier (`docs/ENFORCEMENT-COVERAGE.md`). Model-wiring and a concrete gate check are a later,
> opt-in step (see §7). Plan → approve → implement; delivered via PR. ADR-0023.

## 1. Purpose
Every gate check borromeanRings has today is **mechanical** — it checks *form* (builds, types, lints,
tests, layout). None checks *intent*: whether a change does the **right** thing, is well-named, is
well-designed, or matches its stated requirements. That is the **T2** tier of the coverage map, and
it is currently empty. This spec defines the **critic seam**: a reusable mechanism that judges an
artifact against a declared **rubric** using a **separate-model judge**, fail-closed.

It extends borromeanRings's founding principle — *the verifier is external to the generator* — from
mechanical checks to semantic judgment. It is the same shape as the deep-research verifier
(`meta_harness.deep_research`): a deterministic harness around an **injected** semantic judge, so
the mechanism is fully testable without a model, and the model is a substrate detail.

## 2. Requirements

### User stories
- **US-C1 (intent, not just form):** As a maintainer, I want changes judged against criteria a
  linter cannot express ("does this do what the task asked?", "are names clear?"), so quality means
  more than "it compiles and passes tests".
- **US-C2 (external verifier):** As a maintainer, I want the judgment made by a verifier *separate
  from* whatever generated the code, so it is a real second opinion — not the author grading itself.
- **US-C3 (substrate-agnostic):** As a maintainer, I want the mechanism to work with any model (or
  a panel), or none in tests, so borromeanRings stays model- and harness-agnostic (ADR-0002/0003).
- **US-C4 (fail-closed + auditable):** As a maintainer, I want an unclear/errored judgment to
  **fail** the criterion (never silently pass), and every verdict recorded with a rationale.

### Quality-attribute scenarios (meaningful signals, not arbitrary numbers)
| QAS | Stimulus | Response measure |
|---|---|---|
| C-1 Fail-closed | a criterion the judge cannot affirm (unsure / error / non-answer) | criterion is **failed**, not passed |
| C-2 Externality | the critic evaluates a change | judgment comes from an injected judge distinct from the generator (structural) |
| C-3 Required vs advisory | a rubric with required and advisory criteria | overall passes iff **all required** criteria pass; advisory criteria are reported, never blocking |
| C-4 Testable-without-model | the test suite | full mechanism exercised with stub judges — no network, deterministic |
| C-5 Auditable | any run | every criterion → (passed, rationale) is emitted for a receipt |

## 3. Contract (the seam)
`meta_harness.critic`:

- `Criterion(id, question, required=True)` — one yes/no rubric question. `required` criteria gate;
  advisory ones (`required=False`) are reported only.
- `CriterionVerdict(criterion_id, passed, rationale)` — one judgment.
- `CriticReport(passed, verdicts)` — `passed` iff every **required** criterion passed (fail-closed);
  `.failures` lists the required criteria that failed.
- `CriticJudge = Callable[[question, artifact], tuple[bool, str]]` — the injected semantic step.
- `evaluate_rubric(artifact, rubric, judge) -> CriticReport` — runs each criterion through the
  judge. A judge that **raises** is caught and recorded as a failed criterion (fail-closed) — a
  flaky model call must never pass a gate.
- `make_rubric_judge(ask) -> CriticJudge` — builds a **fail-closed** judge from an `ask(prompt) ->
  str` LLM/agent: only an explicit affirmative ("yes …") passes; anything else (incl. "unsure")
  fails. Mirrors `deep_research.make_entailment_judge`.
- `render_report(report) -> str` — human-readable pass/fail with rationales.

## 4. Design rationale
- **Injected judge (Adapter/Strategy).** The one decision most likely to change — *which model, how
  many, prompt phrasing* — is a module secret behind `CriticJudge`. borromeanRings structures the rubric
  and enforces fail-closed aggregation; the model performs the judgment. (CS130: information hiding,
  low coupling; VISION §6 red line — enforce outcomes, don't dictate the agent.)
- **Fail-closed aggregation** lives in tested deterministic code; only the per-criterion judgment is
  probabilistic. This keeps the *policy* auditable even though the *judge* is not.
- **Rubric = data.** Criteria are declared values, so different check-kinds (intent, naming,
  requirements-traceability, doc-drift) are different rubrics over the *same* mechanism (Single
  Choice / DRY), not new code.

## 5. Non-goals (this increment)
- No specific model integration and no blocking gate check yet (§7).
- No adversarial panel here (a diverse-judge `evaluate_rubric_adversarial`, mirroring
  `deep_research.verify_claim_adversarial`, is the natural next strengthening).

## 6. Verification
Unit tests exercise the full mechanism with stub judges (C-4): fail-closed on unsure/error,
required-vs-advisory aggregation, the `make_rubric_judge` parser, and rendering. 100% coverage of
`critic.py` (coverage ratchet). No network.

## 7. Later (opt-in, own PRs)
- **Model-wired check.** A `checks/` entry that builds a real judge and runs a concrete rubric.
  First **advisory / non-blocking** (reported in the receipt, does not fail the gate) because it is
  non-deterministic; promoted to a **blocking heavy-lane check** (ADR-0022 lane) once it earns trust.
- **Adversarial panel** (independent, diverse judges; min-agree) for higher-stakes rubrics.
- **Concrete rubrics**: intent-correctness, naming, requirements-traceability, doc-drift (coverage
  map rows J/E/F/G).
