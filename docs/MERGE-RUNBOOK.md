# Merge runbook — the stacked PR queue, rehearsed

> **Provenance.** Produced by a dry-run replay in a throwaway clone: from `dev`,
> `git merge --squash <headRef>`, then `git commit`, then the gate, one PR at a time in
> the order `HANDOFF.md` §10 gives. Squash-merging reproduces what GitHub does once it
> retargets each child's base to `dev`. **Nothing was pushed and nothing was merged**;
> the main clone was read from only. Every conflict and every red gate recorded below was
> *observed*, not predicted — §6 is explicit about what was not reached.
>
> It is kept in the repo because it is expensive to regenerate: the rehearsal cost five
> hours, and the six recurring causes in §0 are the part that turns roughly thirty-five
> red gates into a few minutes of mechanical work per merge.
>
> Supersedes the blanket "keep both" resolution rule in `HANDOFF.md` §10 for `README.md`
> specifically — see §0.2, where union-merging it is what kept the gate red.


**Status of this document:** written during a dry-run replay in a throwaway clone
(`scratchpad/mergerehearsal`). Nothing was pushed, nothing merged on GitHub, the main clone
was only read from. Every "conflict" and every
"gate went red" below was observed, not predicted.

Method: from `gh/dev`, `git merge --squash <headRef>` then `git commit`, then
`BORROMEANRINGS_CHECK_TIMEOUT=900 ./verify.sh`, one PR at a time, in the order
`docs/HANDOFF.md` §10 gives. Squash-merging reproduces what GitHub will do after it
retargets each child's base to `dev`.

**Headline:** 31 of the 39 stacked PRs were trial-merged, plus #216.

* **4 merged clean** — no conflict, gate green first time: **#123, #129, #147, #149**.
* **27 conflicted.** From #122 onward, *every* PR conflicted.
* **12 left the gate red** on the first run: **#122, #126, #151, #152, #166, #196, #167,
  #185, #180, #198, #162** and **#127** (the last one an artifact of the #126 fix, not
  something you will hit). All twelve were driven back to `RESULT: PASS` in the rehearsal;
  §0 and §4 say how.
* **3 merged, gate not run** (gating cut for time): **#168, #182, #163**.
* **8 never reached**: **#164, #179, #197, #169, #170, #181, #199, #200**.

Read §0 first — six recurring causes account for almost all of the red.

---

## 0. Read this before the first merge — six things that bite on almost every PR

These are not per-PR surprises. They recur, and knowing them turns ~35 red gates into
about five minutes of mechanical work per merge.

### 0.1 `./describe.sh --readme` is part of *every* merge that adds a check

`04_self_description` (from #151) fails the gate whenever the README's stated check/gate
counts drift from the registry. Every check-adding PR moves the registry. So from #151
onward, the merge is not `commit`; it is:

```bash
git merge --squash <branch>
# ...resolve...
./describe.sh --readme          # regenerate the <!-- describe:begin --> block
git add -A && git commit
```

Observed: gate red on `04_self_description` after #151, #152, #166, #196, #198.

### 0.2 README.md must NOT be resolved by "keep both" — §10's blanket rule is wrong here

HANDOFF §10 says to keep both additions for the conflicting files. That is right for
`CHANGELOG.md`, `setup.cfg`, `borromeanrings.toml`, `docs/CHECKS.md`, `adopt.py` — and
**wrong for `README.md`**. Union-merging it duplicates the counts paragraph. After six
such merges the README carried six near-identical paragraphs claiming "nineteen gates",
"twenty gates", "28 checks", "29 checks", "41 check scripts" — and `04_self_description`
reads the *prose*, not just the generated block, so the gate stayed red even after
regenerating.

Every branch that predates #151 still carries the pre-#151 paragraph and re-adds it.

**Resolution for README.md, every time:**

```bash
git checkout --theirs -- README.md      # or hand-pick; never union
# delete any paragraph containing:
#   The required set is declared in `borromeanrings.toml` `[checks].required` (
./describe.sh --readme
```

(The distinguishing feature: the stale variants have `[checks].required (` on **one**
line; #151's rewrite puts the `(` on the next line.)

### 0.3 `#148` widens the Ruff ruleset — three later PRs fail lint because of it

#148 adds `extend-select = ["PIE807", "PERF401", "PERF402", "PERF403", "PLR0402"]` to
`pyproject.toml`. Each PR was green on its own base, which did not have that rule. Landed
together, three of them fail `20_lint` on **PERF401**:

| PR | File:line | Fix |
|---|---|---|
| #151 | `src/meta_harness/describe.py:112` | `found.extend(_describe_script(script, lane) for script in lane_dir.glob("[0-9]*.sh"))` |
| #180 | `src/meta_harness/charter.py:226` | `problems.extend(Violation(key, "unknown key") for key in charter.extras if key not in allowed)` |
| #162 | `src/meta_harness/context_budget.py:115` | `rows.extend(_source("skill", file.relative_to(root).as_posix(), file.stat().st_size) for file in _skill_files(root))` |

Do the #151 fix **after #171 lands**, not before: #171 carries the unfixed `describe.py`
and will conflict on exactly that line otherwise (it did in the rehearsal).

### 0.4 Merges silently duplicate Python definitions and import names

Two shapes, both caught by the gate, neither flagged as a conflict:

* **Duplicated top-level definitions.** `src/meta_harness/verdict.py` came out of the
  #167, #180, #183, #184, #198, #162 merges with `NON_FAILING_STATUSES` and `is_failing`
  defined **twice** — no conflict marker, git just auto-merged an add/add. Symptom:
  `20_lint` F811 + `30_typecheck` `[no-redef]`.
* **Duplicated names in a union-merged import block.** `tests/unit/test_self_status.py`
  came out with `classify_enforcement` and `hollow_checks` listed twice. Symptom:
  `20_lint` I001 then F811.

**After every merge, before committing:**

```bash
python3 -m ruff check --fix --select I001,F811 src tests
python3 -m ruff format src tests
```

then re-read `src/meta_harness/verdict.py` and delete any block that appears twice
(`ruff --fix` will not remove a duplicated *definition*, only a duplicated import).

`adopt.sh` is the one file this does not cover: it embeds a Python import block inside a
heredoc, so ruff never sees it. #162's merge duplicated `RATCHET_BASELINES` there. Dedupe
it by hand.

### 0.5 Union resolution of a `.py` file needs `ruff format` afterwards

Keeping both sides leaves one blank line where PEP 8 wants two. `10_format` fails.
`ruff format <file>` is the whole fix. First seen on #122 (`tests/unit/test_status.py`).

### 0.6 "Keep both" on a test file can emit Python that does not parse

The strongest caveat to §10's rule. At step 31 (#163) the union of two test files produced
**syntactically invalid** source:

* `tests/unit/test_self_status.py` — two `from ... import (` blocks interleaved, leaving
  an unclosed paren: `Expected ')', found newline` at line 18.
* `tests/integration/test_harness_version_stamp.py` — a `def test_...():` left with no
  body, immediately followed by `@pytest.fixture`: `Expected an indented block after
  function definition` at line 34.

`ruff` refuses to even parse them, so the §0.4 auto-fix silently does nothing and the
breakage reaches the commit. `00_build` / `20_lint` / `40_test` all catch it, but the
resolution is manual: open both files and interleave the two sides by hand.

**Rule of thumb that held for every conflict in this rehearsal:** union is safe when one
side of the hunk is empty (a pure addition). When both sides have content, look at it.
Three sub-cases covered everything seen:

1. one side is a strict superset of the other (an import list, an `__all__` block) → take
   the superset;
2. both sides add genuinely different things (two new config fields) → union;
3. both sides are different wordings of the same thing (a rewritten paragraph, a loop vs
   the comprehension that replaced it) → a human picks one.

---

## 1. The order

Unchanged from HANDOFF §10 except for one insertion at the front. Merge base-first,
`--squash`, never `--admin`.

```
 0.  #216  fix/pin-the-toolchain            <-- NEW, merge FIRST (see §2)
 1.  #123  docs/reconcile-backlog
 2.  #129  docs/community-health
 3.  #147  docs/handoff
 4.  #195  docs/self-assessment             (child of #147)
 5.  #149  fix/enhancement-catalog-audit
 6.  #161  chore/issue-pr-templates         (needs #147 + #129 for its citations)
 7.  #165  chore/rename-tail
 8.  #122  feat/versioning-and-checks-catalog   <-- the trunk
 9.  #124  feat/shellcheck-gate
10.  #125  fix/merge-honors-project-scope
11.  #126  fix/identity-guard-overrides
12.  #127  test/entrypoint-coverage
13.  #148  feat/prior-art-gate
14.  #150  test/adopt-governance
15.  #151  feat/self-description
16.  #171  docs/readme-quickstart
17.  #152  feat/precompact-hook
18.  #166  feat/claude-plugin
19.  #196  docs/multi-harness-spec
20.  #167  feat/rewrite-contract
21.  #185  feat/self-report-receipt
22.  #180  feat/charter-gate
23.  #183  docs/stewardship-cadence
24.  #184  docs/4d-dry-runs
25.  #153  feat/governance-matrices
26.  #160  feat/api-contracts
27.  #198  feat/multi-language
28.  #162  feat/context-budget
29.  #168  fix/research-skill-tokens        } merge together (#168's fix is in #182)
30.  #182  feat/quote-fidelity              }
31.  #163  feat/verdict-evidence
32.  #164  fix/a11y-noop                    <-- must precede #179; see §5
33.  #179  feat/archetype-profiles
34.  #197  feat/swe-state-report
35.  #169  feat/trunk-policy
36.  #170  feat/supply-chain
37.  #181  feat/predicate-lint
38.  #199  test/mutation-guard
39.  #200  feat/provenance-gate
```

The parent→child tree reconstructed from `gh pr list` matches §10 exactly; no PR's base
contradicts the written order.

**Does #216 change any ordering already settled?** No. #216 is based on `dev` and is
independent of every branch in the tree, so it slots in ahead of everything without
moving anything else. It only adds work *inside* three later steps (#124, #148, #170) —
see §2.

---

## 2. #216 `fix/pin-the-toolchain` — merge first

Verified against the branch tip (`9c77a7c`), which is three commits, not the one
originally described:

```
9c77a7c fix: pin only what decides a verdict, not the whole closure
f166c04 chore: pre-pin html5lib ahead of #211 to avoid a merge collision
360317b fix: pin the check toolchain so CI and local cannot disagree
```

**`constraints-dev.txt` does not exist at the tip** — the full-closure approach was
reverted because it froze `click`/`idna`/`msgpack`/`urllib3` at CVE-bearing versions and
`70_pip_audit` correctly went red. The branch now pins only the deciders, in
`pyproject.toml`'s `dev` list, plus `coverage` and `libcst` (transitive but verdict-
deciding). It also edits `setup.cfg`, which §10 already lists as an additive-conflict
file.

Merged first onto `dev` it is **clean** (it is based on `dev`). The conflicts are with the
later PRs. Rehearsed by merging it onto a `dev` already carrying #124/#148/#198:

| File | Conflict | Resolution |
|---|---|---|
| `pyproject.toml` | the whole `dev = [...]` list: ours has the 8 floors + `shellcheck-py>=0.10` (#124); theirs has 10 exact pins | **Take the exact pins, and add `"shellcheck-py==0.11.0.1"` back.** Taking theirs wholesale silently drops #124's shellcheck wheel and CI loses `16_shellcheck`. |
| `setup.cfg` | prose comment rewritten + `--ignore=` list | take theirs for the prose, union the `--ignore` lines, **dedupe** (the list already carried `test_source_coherence_gate.py` and `test_rewrite_contract_hook.py` twice from earlier merges) |
| `CHANGELOG.md`, `docs/adr/README.md` | additive | union |

> The briefing says #216 "conflicts only in the `pyproject.toml` dev block". Reproduced,
> that is not quite the whole list: `setup.cfg`, `CHANGELOG.md` and `docs/adr/README.md`
> conflict too. They are all additive and take two minutes, but budget for four files, not
> one. (`constraints-dev.txt` is correctly absent — no conflict is recorded against it.)

**#170's upper bounds vs #216's exact pins** — the coordinator's rule holds and I
confirmed the mechanics: `==0.15.8` satisfies #170's `78_pins` check (it *is* bounded
above), and an upper bound at the next major does not constrain the minor releases that
actually broke CI. At step 36, resolve `pyproject.toml`'s `dev` block by keeping the exact
pins and discarding the `>=x,<y` forms.

**The thing that is not in the briefing, and will bite.**
`tests/integration/test_toolchain_pins.py::test_the_tools_table_mirrors_what_the_checks_actually_invoke`
scans `checks/**/*.sh` for every tool the checks invoke and asserts that set equals
`TOOLS` in `src/meta_harness/toolchain.py`. And
`test_every_gate_tool_is_pinned_exactly_in_both_places` asserts every entry in the `dev`
list is `==`-pinned. So #216's own tests are a *registry mirror*, exactly like
`04_self_description` and the README:

* **#124** adds `checks/shared/16_shellcheck.sh` → `shellcheck` enters the scanned set →
  `TOOLS` must gain it and `shellcheck-py` must be `==`-pinned, **in the #124 merge**.
* **#198** adds `checks/typescript/*` and `checks/go/*` → every tool those scripts reach
  for enters the set → `TOOLS` and the pins must grow again, **in the #198 merge**.
* **#170** replaces the pins with floors+bounds → `unpinned(declared)` is non-empty →
  fails unless resolved as above.

Treat "extend `TOOLS` + pin the new tool" as a standing obligation of any PR that adds a
check invoking a new binary, the same way an ADR + CHANGELOG entry already is.

**Also:** #207 and #208 are red on toolchain drift, not on their own content. They should
go green once their base carries #216. Do not open fix rounds on them.

---

## 3. Step-by-step: what each merge actually did

Legend: **clean** = no conflict, gate green first time.
Files listed are the conflicted ones; unless noted, the resolution was "keep both"
(union) exactly as §10 says.

| # | PR | Conflicts | Gate | Notes |
|---|---|---|---|---|
| 1 | #123 | — | PASS | clean |
| 2 | #129 | — | PASS | clean |
| 3 | #147 | — | PASS | clean |
| 4 | #195 | `docs/HANDOFF.md` | PASS | union; two hunks, both pure additions |
| 5 | #149 | — | PASS | clean |
| 6 | #161 | `CHANGELOG.md` | PASS | union |
| 7 | #165 | `CHANGELOG.md` | PASS | union |
| 8 | #122 | `CHANGELOG.md`, `tests/unit/test_status.py` | PASS* | *after `ruff format tests/unit/test_status.py` — union left one blank line where two are needed (`10_format`) |
| 9 | #124 | `CHANGELOG.md`, `README.md`, `docs/CHECKS.md`, `setup.cfg`, `tests/unit/test_spine.py`, `tests/unit/test_status.py` | PASS | union (README per §0.2) |
| 10 | #125 | + `merge.sh`, `src/meta_harness/spine.py` | PASS | **not additive.** `merge.sh`: take THEIRS for the `ROOT=` → `BORROMEANRINGS_HOME`/`PROJECT_ROOT` hunk — #125 supersedes it and already contains #124's cd-fail-loudly guard. `spine.py`: whitespace-only hunk, take either + `ruff format` |
| 11 | #126 | + `src/meta_harness/spine.py` | **FAIL** | see §4.1 — a genuine post-merge test failure |
| 12 | #127 | + `tests/integration/test_merge_project_scope.py` | PASS | union; the `test_identity_guard_overrides.py` conflict seen in the rehearsal is an artifact of the §4.1 patch, not something you will hit |
| 13 | #148 | + `borromeanrings.toml`, `src/meta_harness/adopt.py` | PASS | union |
| 14 | #150 | as above | PASS | union |
| 15 | #151 | as above | **FAIL** | `04_self_description` (README drift 28/19 stated vs 31/22 real) **and** `20_lint` PERF401. See §0.2, §0.3 |
| 16 | #171 | + `src/meta_harness/describe.py` | PASS | keep OUR `found.extend(...)` line (the §0.3 fix) |
| 17 | #152 | + `docs/specs/SPEC-self-status.md`, `src/meta_harness/status_assess.py` | **FAIL** | `status_assess.py` conflict is three pure additions → union. Gate red on `04_self_description` until the stale README paragraph is deleted (§0.2) |
| 18 | #166 | + `tests/unit/test_self_status.py` | **FAIL** | `04_self_description`, same cause, same fix |
| 19 | #196 | + `docs/HOOK-EVENTS.md` | **FAIL** | `04_self_description`, same cause, same fix |
| 20 | #167 | + `.claude/skills/borromeanrings-status/SKILL.md`, `src/meta_harness/status.py`, `src/meta_harness/status_assess.py`, `tests/unit/test_verdict.py` | **FAIL** | `status_assess.py`: the two two-sided hunks are supersets → take THEIRS. Then `verdict.py` duplicated `NON_FAILING_STATUSES`+`is_failing` **with no conflict marker** (§0.4) → F811 + no-redef. Then the union'd import block in `test_self_status.py` → I001 (§0.4) |
| 21 | #185 | + `.claude/hooks/stop_gate.sh`, `src/meta_harness/rewrite_contract.py`, `src/meta_harness/verdict.py`, `tests/unit/test_rewrite_contract.py` | **FAIL** | all four two-sided files are supersets from the #167 lineage → take THEIRS. Then the §0.4 import dedupe |
| 22 | #180 | + `src/meta_harness/spine.py` | **FAIL** | `status_assess.py` → take **OURS** (ours is the superset here; #180 branches off #152, not #185). `spine.py` → genuine union, both sides add distinct config fields. Then §0.4 (verdict.py again) and §0.3 (PERF401 in `charter.py`) |
| 23 | #183 | + `docs/AI-FLUENCY.md`, `docs/adr/0063-*.md`, `src/meta_harness/charter.py` | PASS | `charter.py` → take OURS (the PERF401 form); `status_assess.py` → take OURS |
| 24 | #184 | + `docs/specs/SPEC-ai-fluency.md` | PASS | same two files, same resolution |
| 25 | #153 | + `docs/ENFORCEMENT-COVERAGE.md` | PASS | union |
| 26 | #160 | (same set) | PASS | union |
| 27 | #198 | + `docs/adr/README.md`, `src/meta_harness/source_coherence.py`, `src/meta_harness/spine.py` | **FAIL** | see §4.2 |
| 28 | #162 | + `adopt.sh`, `tests/unit/test_adopt.py` | **FAIL** | see §4.3 |
| 29 | #168 | + `.borromeanrings-context-baseline`, `src/meta_harness/context_budget.py`, `docs/specs/SPEC-context-budget.md`, `tests/unit/test_context_budget.py` | not run | baseline: two different numbers (ours 40379, theirs 31690) → keep ours, then **re-measure and re-seed after the merge** — #168 trims the research skill, so the honest value *drops*. `context_budget.py` → take OURS (the §0.3 PERF401 form) |
| 30 | #182 | + `.claude/skills/borromeanrings-research/SKILL.md`, `tests/integration/test_context_budget_gate.py` | not run | **#168 and #182 both re-word the same research SKILL.md** — four divergent prose hunks, union duplicates them. #182 descends from #168, so take THEIRS for the whole file. This is why §9 says merge the two together |
| 31 | #163 | + `verify.sh`, `tests/integration/test_harness_version_stamp.py` | not run | `verify.sh`: the embedded `from meta_harness.verdict import ...` — theirs adds `risk_band`, take THEIRS and delete the narrow one-line form. **Then the §0.6 breakage**: `test_self_status.py` and `test_harness_version_stamp.py` union into unparseable Python — hand-merge both |
| 32–39 | #164 #179 #197 #169 #170 #181 #199 #200 | **not reached** | — | see §6 |

Rough shape of the conflict set: after #122 lands, **every** subsequent PR conflicts.
The recurring cast is `CHANGELOG.md`, `README.md`, `setup.cfg`, `borromeanrings.toml`,
`docs/CHECKS.md`, `src/meta_harness/adopt.py`, `docs/specs/SPEC-self-status.md`,
`.claude/skills/borromeanrings-status/SKILL.md`, `tests/unit/test_status.py`,
`tests/unit/test_self_status.py`, `tests/unit/test_verdict.py`,
`src/meta_harness/status.py`, `src/meta_harness/status_assess.py` — 10 to 20 files per
merge from #167 onward. All but the `src/` ones are pure additions.

---

## 4. The gates that went red, and why

### 4.1 #126 — `test_a_normal_commit_is_still_allowed` fails on any protected branch

`tests/integration/test_identity_guard_overrides.py::test_a_normal_commit_is_still_allowed`
drives the PreToolUse guard with `CLAUDE_PROJECT_DIR` pointed at the repo itself and
asserts `'"deny"' not in` the output. The guard also enforces the Gitflow-lite
protected-branch rule, so **on `dev` or `main` it denies every commit** and the negative
control fails.

It passed CI on the PR because `pull_request` checkouts are detached HEAD (branch =
`HEAD`, not protected). Verified: the test passes on a `feat/` branch and on detached
HEAD, fails on `dev`. The `push: branches: [main, dev]` job will go red the moment this
lands, and so will the maintainer's local `./verify.sh`.

**Fix (apply in the #126 merge commit):**

```python
def test_a_normal_commit_is_still_allowed() -> None:
    out = _run_guard("git commit -m 'a normal commit'")
    assert "identity" not in out.lower(), out
```

That keeps the negative control's meaning — the *identity* rule did not fire — without
asserting on a rule that legitimately denies on `dev`. The fuller fix is to point
`CLAUDE_PROJECT_DIR` at a fixture repo on a work branch; either is fine, the assertion
change is one line and was enough to turn the gate green.

### 4.2 #198 — `test_unreadable_config_fails_closed_not_noop` loses its receipt

#198 replaces `verify.sh`'s `|| echo python` fallback with a hard `exit 1` when
`load_config` raises. #148's
`tests/integration/test_prior_art_gate.py::test_unreadable_config_fails_closed_not_noop`
writes a deliberately broken spine and asserts `statuses["17_prior_art"] == "fail"` —
but now the run aborts before any check emits a receipt, so the status is `None`.

Still fail-closed (`exit != 0`); only the test's contract broke. **Fix:**

```python
    assert code != 0
    assert statuses.get("17_prior_art") != "noop"
```

or give the test a spine that *loads* but breaks the check's own read.

Also at this step: #198's README carries a third stale-count variant ("**41 check
scripts**", "nineteen gates") — §0.2 applies.

### 4.3 #162 — the context-budget ratchet trips on the merged tree

`19_context_budget` seeded its baseline at **32174** bytes on #162's own branch. On the
merged `dev` the injected context is **40379** bytes, because the PRs merged alongside it
add to exactly what it measures:

* #166 packages the skills as a Claude Code plugin, so
  `skills/borromeanrings-research/SKILL.md` **and**
  `.claude/skills/borromeanrings-research/SKILL.md` are both counted (same for
  `borromeanrings-status`) — the plugin copy double-counts ~2 KB;
* #180/#183/#184 add five `skills/ai-fluency-*/SKILL.md` (~4.4 KB);
* #167 adds the prompt-rewrite directive (862 B).

The check says it plainly: *"trim what borromeanRings injects, or accept the new baseline
deliberately."* This is a decision, not a bug. The rehearsal accepted it:

```bash
echo 40379 > .borromeanrings-context-baseline
```

Worth a look first at whether the plugin's duplicated skill tree should be excluded from
the measurement — otherwise every skill counts twice forever.

Plus PERF401 in `context_budget.py` (§0.3) and the `adopt.sh` embedded-import dedupe
(§0.4).

---

## 5. Follow-ups unblocked once the stack lands

| Item | What becomes possible | Where |
|---|---|---|
| **#186 fail-closed enumeration** | HANDOFF §11 lists twelve sites that read a crashed tool as a clean pass. Nine are on `dev` and were deliberately deferred because #186 "refactors an idiom every check PR copies". After the stack lands, all nine are in one tree and can be fixed in one pass: `32_complexity`, `33_coupling`, `45_docstrings`, `12_secrets`, `06_git_identity`, `74_secret_history`, `34_api_diff`, `14_container`, and `15_a11y` (already fixed on #164). The three on open PRs (#198 `typescript/50_security`, #181 `23_predicates`, #170 `76_lockfile`) land with their PRs. #186 also adds the reader-side guard for the receipt-dir rule ("never write a non-receipt `*.json` into `$RECEIPT_DIR`"). |
| **README describe-block regeneration** | Already unavoidable per §0.1 — but after the last check-adding PR (#200) run `./describe.sh --readme` once more and delete every remaining stale counts paragraph, so the README states one set of numbers. |
| **`docs/matrices` rows S6/S8 (ADR-0061)** | ADR-0061 §"Consequences" says the matrix file lives on #138's branch and must be updated there. Both land in this stack (#170 is the ADR, #153 is the matrix file), so after both: in `docs/matrices/02-security-compliance.md`, row **S6** (SBOM matches the declared closure) `gap → #58` → *built (unsigned inventory)*; row **S8** (pinned deps + a lockfile whose integrity the gate checks) `gap → #58` → *built*. **S7** (build provenance) and **S9** (dependency-update tool) stay maintainer decisions. |
| **`describe.py` `_LANES` one-liner (#198's SPEC)** | `docs/specs/SPEC-multi-language.md` line 122 names it: `_LANES` in `src/meta_harness/describe.py:23` is `("shared", "python", "ci")` and must become `("shared", "python", "typescript", "go", "ci")`, then `./describe.sh --readme`. It could not be done on #198's branch (based on `feat/api-contracts`, which predates #151's `describe.py`). Do it right after #198 merges — otherwise the TS and Go lanes exist but the harness cannot describe them, and the counts `04_self_description` enforces exclude them. |
| **`[supply_chain].lockfile` (new)** | #170 declares `lockfile = ""` because the repo has none, so `76_lockfile` is an honest `noop`. #216's original plan would have supplied `constraints-dev.txt` as the value — **but that file no longer exists at #216's tip**, so there is still nothing to point the key at. Either leave `76_lockfile` a `noop` (honest, and visible in every heavy run's `inspected NOTHING` line) or generate a real lockfile as its own change. Do not set the key to a file that is not there. |
| **`15_a11y` × #164/#179** | Not an overlap to resolve — an ordering dependency, and §10 already has it right. #179 gives the `web-app` archetype `must_be_non_noop = ("15_a11y", "40_test")`, and the ADR-0062 spec names `15_a11y` inspecting no HTML in a declared web app as the vacuity case the clause exists for. #164 is what makes `15_a11y` report `noop` instead of `pass` when it finds no HTML. **#164 must precede #179** (it does, steps 32→33); merged the other way the clause would be vacuous — the check would report `pass` on nothing and never trip. #179 does not touch `checks/shared/15_a11y.sh`; it builds on it. After both land, sanity-check by declaring `archetypes = ["web-app"]` in a scratch project with no HTML and confirming the gate fails on the non-noop clause. |
| **#207 / #208** | Red on toolchain drift, not their own content. Once their base carries #216 they should go green with no fix round. |
| **New PRs outside §10** | `gh pr list` now shows #203, #206, #207, #208, #211, #212 (and #216) that HANDOFF §10 predates. They are not in this runbook's order and need their own sequencing pass once the 39 land. |
| **`TOOLS` as a standing obligation** | §2: any PR adding a check that invokes a new binary must extend `TOOLS` and pin it, or #216's mirror test fails. Worth adding to the PR template next to the ADR/CHANGELOG lines. |

---

## 6. Confidence, and what was not reached

### Reproduced (I ran the merge and saw it)

Steps 1–31 (#123 → #163) and #216. Every conflicting file list in §3 is `git diff
--name-only --diff-filter=U` output, not inference. Every resolution in §3 and §4 was
applied and, for steps 1–28, confirmed by a green `./verify.sh` afterwards.

### Reproduced merge, gate not run

Steps 29–31 (**#168, #182, #163**). The merges and conflicts are real and the
resolutions are written down; the gate was not run on them (gating was cut for time).
#163's tree is known to be broken as merged — see §0.6 — so treat step 31's resolution as
"identified, not validated".

### Not reached at all

Steps 32–39: **#164, #179, #197, #169, #170, #181, #199, #200.** Nobody should assume
these were checked. What is known about them comes from reading the branches, not from
merging them:

* **#164 → #179 → #197** — ordering dependency verified by reading both branches (§5).
  #179 does not touch `checks/shared/15_a11y.sh`.
* **#170** — its `pyproject.toml` `dev`-block conflict with #216 is **inferred from the
  three file versions**, not reproduced: I read #170's diff (`>=x,<y` bounds on the same
  eight lines #216 replaces with `==` pins) and merged #216 against a tree that already
  had #124's `shellcheck-py` line, which conflicted exactly as predicted. The #170 half
  is by construction, not observation.
* **#181, #199, #200** — each adds a check, so §0.1 (`describe.sh --readme`) and §2
  (`TOOLS`) apply to all three; #181 additionally carries the `23_predicates` fail-closed
  fix from HANDOFF §11.

Given that every PR from #122 onward conflicted, expect all eight to conflict on the
recurring additive set, and expect `04_self_description` red on each until the README
block is regenerated.

### Not investigated, deliberately

**#207 and #208.** Per the coordinator these are already diagnosed — red on toolchain
version drift, not on their diffs, and expected green once their base carries #216. I did
not open them, did not build merge worktrees for them, and have nothing of my own to add.
(Worktrees named `pr207merge` / `pr208merge` exist in the shared scratchpad; they are not
mine. All of my work is confined to `scratchpad/mergerehearsal`.)

### Scope notes

* Nothing was pushed. Nothing was merged on GitHub. `gh pr merge` was never called,
  `--admin` was never used, nothing was installed. The `gh` remote was fetch-only.
* The main clone was read from only — `gh pr list`, `git show`, `git worktree list`, and
  reading files under the `wtpin` worktree.
* Two small **rehearsal patches** were applied to keep the replay measurable and are
  flagged as such in the tree: the #126 assertion change (§4.1) and the #198 prior-art
  assertion change (§4.2). Both are proposed fixes, not merge artifacts.
