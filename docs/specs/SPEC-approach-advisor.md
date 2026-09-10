# SPEC — Approach advisor: the right approaches and the right questions, before building

**Status:** Accepted (implemented)
**Drives:** ADR-0072
**Refs:** #32 (the contract), ADR-0037 (the advisory-recommender pattern this mirrors),
ADR-0062 / SPEC-archetypes.md (archetypes), ADR-0067 / SPEC-swe-state.md (the lacks),
ADR-0049 / SPEC-self-status.md (honest `noop`, enforcement), ADR-0041 (ratchets and
baselines), ADR-0043 / SPEC-adr-discipline.md, ADR-0028, ADR-0021, ADR-0020 (AI Fluency —
Description)

## 1. Problem

The gate decides whether a change was built *right*. Nothing decides whether the agent is
about to build the *right thing the right way*: which engineering approach fits this change
given what the project is and what its record says, and which questions the human must
answer before the agent proceeds (#32). Today the agent brings its own approach and asks
its own questions — from memory, unshaped by the facts on disk. The facts exist: the
declared archetypes, the SWE-state report's lacks, the last verdict's failing and hollow
checks, the branch and its diff, whether enforcement is on. Nothing turns them into advice.

## 2. Goals

- **G1** From facts already on disk, produce two lists for ONE governed project:
  **questions** the agent should ask the human before proceeding, and **approaches** that
  fit this change. Each line is a deterministic rule keyed on facts and cites the check,
  SPEC or ADR it comes from.
- **G2** Rules are data: a frozen catalog like `enhancements.CATALOG` (ADR-0037), each rule
  a `when` predicate over the facts, its text, and its `source`. Adding a rule is a one-entry
  PR; a catalog-integrity test proves every `source` names something that exists.
- **G3** No model, no score, no ranking. The only order is fixed: questions first, then
  approaches, each in catalog order.
- **G4** Advisory, never a gate: it proposes; the human decides. Always exits 0; reads only.
- **G5** Honest where it cannot tell: an unreadable input is a question, never a guess;
  no facts ⇒ says "no advice", never invents some.

## 3. Non-goals

- Not a check: no receipt, no `CHECKS.md` row, no effect on any verdict.
- Does not re-run the gate; it reads the **last** verdict (`status.sh --run` refreshes).
- Does not detect archetypes (the profiler's job, ADR-0024); undeclared ⇒ it asks.
- Does not grow the prompt-rewrite directive (`prompt_rewrite.py` is untouched; the
  context-budget ratchet measures it). Advice reaches the agent through the
  `borromeanrings-status` skill and `status.sh --advise`, on demand.
- Does not rank, weigh or count rules; "more advice" is not "worse project".

## 4. Contracts

### 4.1 Facts (already on disk)

| Fact | Source | Read by (composition root `advise.sh`) |
|---|---|---|
| required ∪ heavy check ids, declared archetypes | `borromeanrings.toml` | `spine.load_config` |
| last outcome per check | `.meta-harness/last_verdict.json` | `verdict.read_last_verdict` |
| archetype features absent (id, title, why) | working tree | `archetypes.evaluate` + `required_features` |
| ratchet baseline files present | `<project>/<RATCHET_BASELINES[check]>` | the entry point |
| changelog present | `<project>/CHANGELOG.md` | the entry point |
| enforcement mode (`auto` / `partial` / `manual`) | `.claude/settings.json` | `status_assess.classify_enforcement` |
| branch name | `git rev-parse --abbrev-ref HEAD` | the entry point (`""` when not a repo) |
| changed paths | `git diff --name-only <merge-base>` ∪ untracked, base as `13_adr` (`origin/dev` → `dev` → `origin/main` → `main`) | the entry point (`()` when none / no base) |
| stakes, reviewer — **when present** | `[charter].stakes`, `[charter].reviewer` in `borromeanrings.toml` | the entry point (raw TOML; `""` when absent — `[charter]` is not on this base) |
| whether a cited check's own rule is on | `[collaboration].branch_patterns`, `[changelog].enabled` + `require_entry_on_src_change`, `[adr].require_prefixes` | `spine.load_config` |

The pure core `meta_harness.advisor` never touches the filesystem or a process.
`gather_facts(...)` takes these primitives and normalises them into a frozen `Facts`
(the same shape as `swe_state.assess`); the composition root reads them, exactly as
`swe-state.sh` does. Fan-out of `advisor` is **2** — `adopt` (`RATCHET_BASELINES`,
`plan_adoption`) and `verdict` (`is_failing`) — the same two seams `swe_state` uses, so the
advisor classifies "failing", "noop", "ratchet without a baseline" and "recommended not
adopted" identically to the SWE-state report and `adopt.sh`. Everything else crosses the
seam as plain values (`FeatureGap`, strings).

`Facts` fields: `project`, `gated`, `archetypes`, `failing` (`(check, status)` pairs for
required checks whose last status `is_failing`), `noop` (required checks last `noop`),
`ratchets_without_baseline`, `recommended` (RECOMMENDED not required), `features_absent`
(`FeatureGap(id, title, why)`), `required` (required ∪ heavy), `live`, `adr_prefixes`,
`branch`, `changed` (root-relative paths), `changed_src`, `changed_tests`, `changed_adr`,
`changed_changelog`, `enforcement`, `stakes`, `reviewer`, `unreadable`
(`config` / `verdict` / `archetypes`).

Never gated ⇒ `failing` and `noop` are empty (`unknown` is not `lacking` — SPEC-swe-state §4.2).

**`live` — never claim what an unadopted check will do.** `live` is `required` narrowed to
the checks whose own opt-in rule is also on: `08_branch` needs declared
`[collaboration].branch_patterns`, `11_changelog` needs `[changelog].enabled` **and**
`require_entry_on_src_change`; every other check is live once required. A rule whose text
asserts that a check fails closed **must** key on `live` — telling a project that
`13_adr` will fail it when `13_adr` is not adopted is precisely the over-claim the gate
exists to prevent, and the safe direction is to say nothing (SPEC-swe-state §4.4).

### 4.2 Rules

```python
@dataclass(frozen=True)
class Rule:
    id: str            # stable, unique
    kind: str          # "question" | "approach"
    when: Callable[[Facts], bool]
    text: str          # str.format template over the vocabulary below (lists pre-joined)
    source: str        # a check id, a docs/specs/SPEC-*.md file, or ADR-NNNN
```

A firing rule renders as `Line(rule, text, source)` — `rule` is the `Rule.id` that
produced it.

`CATALOG` is a frozen tuple. The catalog (each rule's `source` must exist on this base):

| id | kind | when | source |
|---|---|---|---|
| `q_never_gated` | question | not gated, archetypes declared | SPEC-self-status.md |
| `q_unreadable` | question | any input unreadable | SPEC-swe-state.md |
| `q_enforcement_off` | question | gated, enforcement `manual` / `partial` | SPEC-self-status.md |
| `q_no_archetype` | question | gated, no archetypes | 21_archetype |
| `q_a11y_hollow_web_app` | question | `web-app` declared, `15_a11y` noop | 15_a11y |
| `q_hollow_checks` | question | any noop (other than the rule above's) | ADR-0049 |
| `q_reviewer` | question | stakes present, reviewer empty | ADR-0007 |
| `q_branch` | question | branch is protected/other (not `feat/ fix/ docs/ test/ chore/ refactor/ perf/ ci/ hotfix/`), paths changed, and `08_branch` is live | 08_branch |
| `a_failing_ratchet` | approach | a ratchet check (`32_complexity`, `33_coupling`, `45_docstrings`, `40_test`, `60_mutation`) is failing | ADR-0041 |
| `a_failing_gate` | approach | any other check failing | ADR-0049 |
| `a_ratchet_baseline` | approach | ratchets without a baseline | ADR-0041 |
| `a_spec_and_adr_first` | approach | branch starts with a declared `adr_prefixes` entry, `src/` changed, no `docs/adr/` change, `13_adr` live | 13_adr |
| `a_test_first` | approach | `src/` changed, no `tests/` change, `40_test` live | 40_test |
| `a_changelog_with_change` | approach | `src/` changed, `CHANGELOG.md` unchanged, `11_changelog` live | 11_changelog |
| `a_web_api_health` | approach | `web-api` declared, `health_endpoint_declared` absent | SPEC-archetypes.md |
| `a_archetype_features` | approach | any other archetype feature absent | 21_archetype |
| `a_playbook` | approach | archetypes declared | ADR-0062 |
| `a_recommended` | approach | RECOMMENDED not adopted | ADR-0041 |
| `a_heavy_lane_high_stakes` | approach | stakes present and not `low` | ADR-0033 |

Predicates are pure functions of `Facts` only. Text templates may reference exactly this
vocabulary (a key outside it raises, so it is the contract a new rule is written against):
`{archetypes}`, `{failing_ratchets}`, `{failing_other}`, `{noop_other}`, `{ratchets}`,
`{recommended}`, `{features_other}`, `{branch}`, `{changed_src}`, `{enforcement_upper}`,
`{stakes}`, `{unreadable}` — each the comma-joined list (or the scalar) from `Facts`. The
`_other` keys carry what the narrower rule above them did not take, so no fact is reported
twice.

### 4.3 Advice

`advise(facts) -> Advice(project, questions, approaches, note)`:

- `questions` = every `question` rule whose `when(facts)` holds, **in catalog order**;
- `approaches` = every `approach` rule whose `when(facts)` holds, in catalog order;
- each item is `Line(rule_id, text, source)` with the template formatted;
- **no facts** — not gated, no archetypes, nothing unreadable, no changed paths — ⇒ both
  lists empty and `note = "no advice: never gated, no archetypes"` (the record says
  nothing, so the advisor says nothing rather than something generic);
- otherwise `note = ""`. Unknown archetypes never reach here: `spine.load_config` fails
  closed upstream and the composition root reports `config` unreadable.

### 4.4 Rendering

```
borromeanRings — approach advice for <project name>   (advisory; never a gate)

Questions to ask before proceeding
  1. <text>  [<source>]
  (none)

Approaches that fit this change
  1. <text>  [<source>]
  (none)

Facts: gated=yes · archetypes: web-api · branch: feat/x · enforcement: manual ·
       failing: 21_archetype (fail) · noop: 14_container · changed: 3 path(s) · stakes: (no charter)
Order: fixed — questions, then approaches, each in catalog order; no score, no ranking
```

The "no facts" case prints the header, the note line, and the Facts line. `--json` is
`asdict(Advice)`.

### 4.5 Entry points

- `advise.sh [--json]` — resolves `BORROMEANRINGS_HOME` (its own dir) and the project
  (`BORROMEANRINGS_PROJECT` → `CLAUDE_PROJECT_DIR` → `$PWD`, nearest enclosing
  `borromeanrings.toml`); not governed ⇒ one `NOT GOVERNED` line. Exit 0 always.
- `status.sh --advise` — prints the self-status block, then the advice.
- The `borromeanrings-status` skill tells the agent to run it when starting a task in a
  governed project and to **ask the questions before generating** (Description, ADR-0020).

## 5. Edge cases

| Case | Required behaviour |
|---|---|
| not governed | `NOT GOVERNED — no borromeanrings.toml in …`; exit 0 |
| never gated, no archetypes, clean tree | `no advice: never gated, no archetypes`; both lists empty |
| never gated, archetypes declared | `q_never_gated` + `a_playbook` (+ feature rules if absent) |
| `borromeanrings.toml` unreadable (incl. unknown archetype) | `q_unreadable`; nothing else derived from config fires |
| verdict malformed | `q_unreadable`; `failing`/`noop` empty |
| `[charter]` absent (this base) | `stakes == ""` ⇒ `q_reviewer` and `a_heavy_lane_high_stakes` never fire |
| not a git repo | `branch == ""`, `changed == ()` ⇒ branch/diff rules never fire |
| a cited check not required, or its own rule off | that rule stays silent — no claim about a check that is not in force here |
| heavy check absent from a fast verdict | `unknown`, never failing or noop |

## 6. Verification

- Unit (exact-value, `tests/unit/test_advisor.py`): every rule fires on a fixture built to
  trip it and stays silent on one built not to — including, for each check-citing rule, a
  fixture where the check is *not* live; the fixed order; the no-facts note; `render` and
  `to_json` pinned; 100 % line + branch of `advisor.py`. Catalog shape (ids unique, `kind`
  ∈ {question, approach}, `source` well formed, ≥ 12 rules) is pinned here too.
- Catalog integrity (`tests/integration/test_advise_cli.py`): every `Rule.source` names an
  existing check id (`checks/*/NN_name.sh`), a `docs/specs/SPEC-*.md` file, or an
  `ADR-NNNN` under `docs/adr/` **on this base**. It lives in the integration suite because
  it reads the repository by path and mutmut copies only `src/` and `tests/` into its
  sandbox; a path-reading test in the unit suite fails the clean-test run and evaluates
  zero mutants (observed on the heavy lane).
- Integration (same file, mutmut-ignored): a governed fixture (`archetypes = ["web-api"]`,
  requiring `08_branch`, `11_changelog`, `13_adr`, `14_container`, `21_archetype` with the
  collaboration and changelog rules switched on) gated once through the real `verify.sh`,
  run through `advise.sh` (text + `--json`) and `status.sh --advise`, asserting exact
  lines — and asserting that no claim is made about `40_test`, which the fixture does not
  require.
- borromeanRings's own advice (dogfood) is recorded in ADR-0072.
