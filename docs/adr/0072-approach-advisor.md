# ADR-0072 — Approach advisor: rules as data, questions before approaches, never a gate

**Status:** Accepted
**Spec:** `docs/specs/SPEC-approach-advisor.md`
**Refs:** #32, ADR-0037 (advisory recommender), ADR-0062 (archetypes), ADR-0067 (SWE
state), ADR-0049 (honest `noop`), ADR-0041 (ratchets and baselines), ADR-0043 (ADR
discipline), ADR-0028 (changelog), ADR-0021 (branching), ADR-0020 (AI Fluency), ADR-0038
(coupling), ADR-0011 (prompt rewriting)

## Context

Every gate in borromeanRings judges a change after it is built. #32 asks for the
front-of-loop counterpart: induce the wrapped agent to build the *right* thing the *right*
way — surface the approaches that fit this project and ask the human the right questions
*before* generating, scoped to relevance ("not everything needs everything"). The facts
that decide relevance are already on disk: the declared archetypes, the last verdict's
failing and hollow checks, the SWE-state report's lacks, the branch and its diff, whether
enforcement is on. Nothing turned them into advice; the agent brought its own approach and
its own questions, from memory.

## Decision

1. **A pure module, `meta_harness.advisor`, mirroring ADR-0037.** The rules are **data**: a
   frozen `CATALOG` of `Rule(id, kind, when, text, source)`, each `when` a predicate over
   a frozen `Facts`, each `source` a check id, a `SPEC-*.md` or an `ADR-NNNN` that exists
   on this base (a catalog-integrity test proves it). `gather_facts` normalises already-read
   primitives; `advise` applies the catalog; `render` / `to_json` print. No model, no
   filesystem, no process. `advise.sh` is the composition root, the same shape as
   `swe-state.sh`; `status.sh --advise` appends the advice to the self-status.

2. **Advisory, never a gate.** It proposes; the human decides. Always exits 0, writes
   nothing, produces no receipt and no `CHECKS.md` row. It does not grow the prompt-rewrite
   directive (ADR-0011; the context-budget ratchet measures that): advice reaches the agent
   on demand through the `borromeanrings-status` skill, which now says to run it when
   starting a task in a governed project and to ask the questions first.

3. **Questions precede approaches.** The output is two lists in one fixed order — every
   firing `question` rule, then every firing `approach` rule, each in catalog order — and
   nothing else orders them. Questions come first because an approach chosen before the
   question is answered is exactly the scope drift Discernment later has to catch
   (ADR-0020): "who reviews?", "is there really no HTML?", "should this be on a feat/
   branch?" change *what* to build; "add the health route first", "fix the design, never
   the baseline" only change *how*. No score, no weight, no count: more advice is not a
   worse project.

4. **Never crash where the record is malformed.** `[charter]` is read raw (the spine does
   not model it on this base), so every shape that is not "absent, or a table of strings" —
   a top-level `charter = "high"` scalar, a list-valued `stakes` — degrades to `charter` in
   `unreadable`, which surfaces as the `q_unreadable` question. The first cut caught only
   `OSError`/`ValueError`, so a scalar raised `AttributeError`: a traceback on stderr, empty
   stdout, exit 0, and `--json` emitting nothing parseable — strictly worse than the
   documented "no advice" path, and a violation of the advisory contract this ADR asserts
   (found by the PR #207 review). Total reads, or the contract is a claim the code does not
   keep.

5. **Honest where the record is silent.** Never gated, no archetypes, nothing unreadable,
   nothing changed and no declared stakes ⇒ `no advice: never gated, no archetypes`, not generic guidance.
   An unreadable input (including an unknown archetype, which `spine.load_config` rejects
   fail-closed upstream) is itself a question. `[charter]` stakes are consumed *when
   present* — the section is not on this base — so the reviewer and heavy-lane rules
   simply never fire without it.

6. **A rule may only cite a mechanism that is in force here.** `Facts.live` is the
   project's required ∪ heavy set narrowed to the checks whose own opt-in rule is also on
   (`08_branch` needs declared branch patterns; `11_changelog` needs the
   entry-on-source-change rule), and the four diff-keyed rules key on it. Telling a project
   that `13_adr` will fail it when `13_adr` is not adopted would be the same over-claim as
   a hollow green — so where the mechanism is off, the advisor says nothing rather than
   something unfounded. The ADR-trigger prefixes come from `[adr].require_prefixes`, not a
   hardcoded `feat/`. (An independent review of this change found the first cut asserting
   all four unconditionally; it is fixed here and pinned by not-adopted tests.)

   A second review (PR #207) found the same defect surviving in two more rules —
   `a_web_api_health` and `a_archetype_features` claimed `21_archetype fails closed` while
   keying only on the declared archetypes, so a project with `archetypes = ["web-api"]` and
   `21_archetype` unadopted was told in one breath that the gate would catch a missing
   health route *and* that `21_archetype` is not required here. Both now key on `live`. A
   sweep of all 19 rules for the same class then found two further cases, fixed here:
   `q_no_archetype` claimed that declaring an archetype "turns hollow greens into failures"
   (true only where `21_archetype` runs — reworded to what the declaration *is read by*),
   and `a_heavy_lane_high_stakes` enumerated the four heavy checks as though `--heavy` would
   run them anywhere (it now names `[checks].heavy` and stays silent when that is empty).
   §4.2 of the SPEC records the four-part test each rule must now pass, and
   `test_no_rule_claims_a_check_fails_closed_unless_that_check_is_live` enforces it.

   The lesson is recorded rather than hidden: fixing four instances of a defect class is not
   the same as eliminating the class, and only the written-down test plus an executable
   invariant caught the rest.

7. **Fan-out held at the coupling baseline (2).** `advisor` imports `adopt` and `verdict`
   — the same two seams `swe_state` uses — so "failing", "noop", "ratchet without a
   baseline" and "RECOMMENDED not adopted" are classified identically by the advisor, the
   SWE-state report and `adopt.sh`. Archetype gaps, enforcement mode, branch and diff cross
   the seam as plain values from the entry point.

## Alternatives considered

- **Inject the advice into the prompt-rewrite directive on every prompt.** Rejected: the
  directive is a fixed cost on every turn and is under a context-budget ratchet; advice is
  per-task, not per-prompt, and belongs in the skill the agent runs when it starts a task.
- **Let a model pick or phrase the advice.** Rejected — it would reintroduce the
  from-memory answer the record exists to replace, cost tokens, and be untestable as a
  contract. Every rule here is a deterministic predicate with exact-value tests.
- **Rank or score rules by importance.** Rejected (HANDOFF §3 "Threshold-free"; #139): a
  weight over rules of unequal kind is a meaningless number. One fixed order suffices.
- **Fire the diff rules regardless of adoption, since the advice is good anyway** ("write
  the failing test first" is right even without `40_test`). Rejected: the rule's value is
  that it cites the mechanism that will hold the line, and a citation of something switched
  off here is unfounded. Under-claiming is the safe direction (ADR-0067 §3).
- **Make any rule a gate** ("no ADR on a feat/ branch ⇒ fail"). Rejected — where a rule
  *can* be a gate it already is one (`13_adr`, `11_changelog`, `21_archetype`); the
  advisor cites those and adds the ones that cannot be gates (which question to ask).
- **Detect archetypes instead of asking.** Rejected — the profiler's advisory detection
  (ADR-0024) is a guess; an undeclared archetype earns the question "what kind of app is
  this?", which is the one that matters.

## Consequences

- A session can start from the record: run `status.sh --advise`, ask the questions, then
  build with the approaches the facts call for — each traceable to a check, SPEC or ADR.
- Dogfooded on this repository (one run, 2026-09-10, on branch `feat/approach-advisor`
  after a fast-lane gate; a dated observation, not a contract): no questions; one approach
  — `archetype(s) cli, library declared ⇒ read the catalog playbook for each
  (meta_harness.archetypes.CATALOG[name].playbook) before designing the change [ADR-0062]`;
  facts `gated=yes · archetypes: cli, library · enforcement: auto · failing: none · noop:
  none · stakes: (no charter)`. The ADR, test and changelog rules stayed silent because
  this branch already carries all three — which is the intended reading: silence means the
  record has nothing to say, not that the advisor had nothing to check.
- Adding a rule is one catalog entry plus its firing/silent tests; the integrity test
  refuses a `source` that names nothing.
- (−) The catalog is curated and will lag the check registry; a new check earns advice only
  when someone writes the rule. (−) The diff-based rules see the branch against its
  integration base, so on a long-lived branch "src changed" stays true until merge.
