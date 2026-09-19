# Research — `borromeanrings-research` skill token audit (issue #47)

> **Scope:** why one invocation of `.claude/skills/borromeanrings-research/SKILL.md` consumed
> ~70% of a session's usage (issue #47), what is *measured* versus *estimated*, and what was
> changed. Measured with `meta_harness.context_budget` (ratchet `19_context_budget`, ADR-0055)
> on branch base `feat/context-budget`, 2026-09-08. Every number under "Measured" is the
> output of a command that is reproducible from this checkout; everything under "Estimated"
> is labelled as such and is *not* a measurement.

## Bottom line

1. The skill's **static** cost is tiny and cannot explain the incident: 4176 B ≈ 1044 tokens
   before, 3692 B ≈ 923 tokens after — about 1% of a 100K-token session even if reloaded.
2. The cost is **dynamic and structural**: the old protocol had no budget, no cache, no
   "extract, don't ingest" rule, and kept *all* working state (page text, result graph, the
   query/source log, the verification pass) in the conversation. Every later turn re-sends all
   of it, so the cost grows roughly with (tool calls × resident bytes), not linearly.
3. Fix: a declared budget, working state on disk under `docs/research/<slug>/`, passage
   extraction instead of page ingestion, a URL/query cache, verification against the saved
   passage, optional sub-agent delegation, an explicit saturation stop, and trimmed prose. The
   contract (plan + steering, many mutations, multi-engine + dorking + platforms, beyond page
   one, result graph, citation chains, hostile pages, visibility, synthesis over everything,
   fail-closed verification, coverage report, toml config) is unchanged.

## 1. Measured: static context cost

Command (from the repo root, base `feat/context-budget`):

```
PYTHONPATH=src python3 - <<'PY'
from pathlib import Path
from meta_harness.context_budget import format_report, measure_context_budget
from meta_harness.prompt_rewrite import build_directive
from meta_harness.spine import load_config
c = load_config(Path("borromeanrings.toml"))
print(format_report(measure_context_budget(".", build_directive(c.context) if c.prompt_rewriting_enabled else "")))
PY
```

Before (commit `6e349eb`):

```
directive       862 B  ~216 tok  <prompt_rewrite directive>
instructions   1230 B  ~308 tok  AGENTS.md
skill          3508 B  ~877 tok  skills/ai-fluency-delegation/SKILL.md
skill          3169 B  ~793 tok  skills/ai-fluency-diligence/SKILL.md
skill          3450 B  ~863 tok  skills/ai-fluency-discernment/SKILL.md
skill          3802 B  ~951 tok  skills/ai-fluency-prompting/SKILL.md
skill          3917 B  ~980 tok  skills/ai-fluency-stewardship/SKILL.md
skill          1730 B  ~433 tok  skills/borromeanrings/SKILL.md
skill          2447 B  ~612 tok  skills/borromeanrings-contribute/SKILL.md
skill          4176 B  ~1044 tok  .claude/skills/borromeanrings-research/SKILL.md
skill          3395 B  ~849 tok  .claude/skills/borromeanrings-status/SKILL.md
hook            281 B  ~71 tok  .claude/hooks/pre_bash_guard.sh
hook            207 B  ~52 tok  .claude/hooks/stop_gate.sh
TOTAL         32174 B  ~8049 tok  (tokens ≈ bytes/4)
```

After (this change): the research row is `3692 B ~923 tok`; every other row is unchanged;
`TOTAL 31690 B ~7928 tok`. Delta: **−484 B (−11.6% of the skill, −1.5% of the total)**.

Per-section bytes (UTF-8, computed by splitting the file on `## ` headings):

| Section | Before | After | Note |
|---|---:|---:|---|
| frontmatter (name + description — loaded in **every** session, invoked or not) | 692 | 555 | description rewritten; same triggers, adds the budget/disk stance |
| intro | 292 | 310 | states the one rule that matters: state on disk under `docs/research/<slug>/` (committed research state, not scratch; write nowhere else), summaries in chat |
| §0 Budget | — | 271 | **new**: declared, editable knobs |
| §1 Plan | 836 | 521 | same content; prose compressed; plan now written to `plan.md` |
| §2 Search | 725 | 1048 | grew: extract-not-ingest, cache, symbol-level reads, sub-agents, saturation stop |
| §3 Show your work | 189 | 155 | same; "one line each", log on disk |
| §4 Synthesize | 174 | 130 | same; `report.md` |
| §5 Verify | 362 | 367 | same gate; verify against the *saved* passage, re-fetch only if missing; over-cap passages saved whole, only the entailing lines quoted in chat |
| §6 Coverage | 177 | 178 | adds "budget used" |
| Tactics to draw on | 476 | 0 | **cut**: it restated §1 (query mutations, dorking, platforms), §2 (credibility, spam) and the saturation rule now in §2. Nothing unique was lost — see §4 below |
| Config note | 253 | 159 | same; adds "budget defaults" as a declarable preference |
| **total** | **4176** | **3692** | |

Note on the tokens column: `context_budget` uses bytes/4 rounded up — a consistent measure for
a ratchet, not a tokenizer. The real token count for Markdown with backticks and operators is
probably somewhat higher than bytes/4; the *ratio* before/after is what the ratchet tracks.

## 2. Traced: dynamic cost drivers (from reading the skill and its code paths)

What the skill's code path is: the skill has **no Python behind it** in production. ADR-0014
made it a steering layer — the agent runs its own `WebSearch`/`WebFetch`/browse tools;
`src/meta_harness/deep_research.py` is an explicitly deprecated testbed that nothing in the
skill invokes (`architecture_private = ["deep_research"]` in `borromeanrings.toml`). So every
byte of the dynamic cost is *tool results and agent output in the conversation*, driven by
what the prose instructs. Reading the old prose, in the order of likely impact:

| Rank | Driver | Evidence in the old SKILL.md | Why it costs | Cost model (**estimate**) |
|---|---|---|---|---|
| 1 | **All working state in context; nothing written to files** | No file is mentioned anywhere. §2 "Build a result graph: track sources…", §3 "surface each query you send and each source you read", §5 "for each claim… confirm that source's text actually supports" | Every fetched page, the graph, the log and the verification pass are resident for the rest of the session, and re-sent on every subsequent turn. Cost ≈ Σ over turns of resident context — quadratic-ish in the number of tool calls | Estimate: with ~40 tool calls each leaving ~3–8 KB in context, resident state reaches ~150–300 KB (~40–75K tok) and each further turn pays it again. This alone can be ~70% of a session |
| 2 | **Whole-page ingestion, no extraction rule** | §2 "ingest", "read", "reach what a shallow search misses"; nothing says *extract only the relevant passage* | A `WebFetch` of an article returns pages of text; the agent needs a paragraph | Estimate: 5–20 KB per source vs ≤2 KB for an extracted passage — 3–10× per source |
| 3 | **Unbounded fan-out: no rounds, no per-round query or source bound** | §1 "aim for *many*… Don't settle for one or two"; §2 "Run the full set of mutations across the chosen engines/platforms", "don't ingest only the first page", "follow citation chains" | mutations × engines × platforms × pages × chains, with the only stop ("saturation") buried in the tactics footnote | Estimate: 10 mutations × 3 engines = 30 searches ≈ 30–90 KB of search results before a single page is read |
| 4 | **Re-verification re-fetches; no cache/dedupe of URLs or queries** | §5 verifies "for each claim" against "that source's text" — the text is not saved, so a later verification pass re-fetches; no "don't re-fetch" rule (only "don't repeat queries", in the footnote) | Each claim can trigger a second fetch of a page already paid for | Estimate: up to 1× the fetch cost again for a claim-dense answer |
| 5 | **Visibility implemented as echo** | §3 "surface each query you send and each source you read" with no bound on how much | Read as "narrate everything", it duplicates tool output in agent prose | Estimate: +10–30% over the tool results themselves |
| 6 | **No sub-agent isolation** | Not mentioned | Sub-agents get their own context window; the parent only receives the summary. The old skill never suggests it, so all fetch noise lands in the main window | Estimate: delegating fetch+extract moves ~most of driver 1/2 out of the parent; `docs/research/AGENT-TOOLING-SURVEY.md` §2 (PR #148, `feat/prior-art-gate` — this checkout may not have it yet) documents the isolation |
| 7 | **Whole-file reads on code hosts** | §1 lists "code hosts" as a platform; nothing about symbol-level reads | Reading a 1 000-line file to find one function | Estimate: file-size dependent; pyright-lsp / Serena are catalogued in `enhancements.py` once PR #149 merges (not on this base) — referenced, not installed; the skill uses them only if installed and falls back to grep/sed ranges |
| 8 | **Static file** | 4176 B | Loaded once on invocation; the 692 B frontmatter on every session | **Measured**: ~1K tokens; ~1% of the incident. Not a driver |

Ordering rationale: 1–3 compound (3 produces the volume, 2 makes each unit large, 1 makes the
session pay for it repeatedly); 4–7 are multipliers on top; 8 is measured and negligible. No
run was instrumented for this audit (doing so would spend a research session's tokens to
measure a research session's tokens, and issue #47's own numbers — "~70% of a usage budget
in one session" — are the only observation available). The acceptance criterion "≥50% token
reduction on a benchmark query" therefore stays **open**; see §5.

## 3. What was changed, and how each change maps to a driver

| Change (new SKILL.md) | Driver(s) |
|---|---|
| §0 declared budget: defaults 3 rounds, 8 queries/round, 5 sources/round, ≤40 extracted lines/source, shown in the plan and editable by the user; extra rounds only on request after the coverage report | 3, 4 |
| Working state on disk: `docs/research/<slug>/plan.md`, `log.md`, `sources/<n>.md`, `graph.md`, `report.md` — **committed** research state (the repo's surveys live in `docs/research/` too), not scratch; the agent writes nowhere else; conversation gets one line per query/source | 1, 5 |
| "Extract, never ingest": fetch with a prompt for the relevant passages; save passages, not pages | 2 |
| Cache: never re-fetch a URL in `sources/`, never repeat a query in `log.md` | 4 |
| Verify against the **saved passage**; re-fetch only if the passage is missing; a passage longer than the extract cap is saved whole in the slug dir and only its entailing lines are quoted in chat | 4 (keeps the fail-closed gate: entailment against real source text, now on disk) |
| Sub-agent delegation of fetch+extract where available, returning one line per source | 6 |
| Symbol-level reads for code hosts: pyright-lsp / Serena if installed (catalogued once #149 merges), else grep/sed ranges | 7 |
| Saturation stop promoted from the footnote to a rule: a round with no new relevant source ends the search | 3 |
| Cut "Tactics to draw on"; compressed §1/§4/§5 prose; shorter description | 8 |

The budget defaults are **knobs, not gates** (the project rejects arbitrary numeric targets):
they are declared in the plan the user approves, the user may change them, and a project may
set its own in `borromeanrings.toml`. Nothing in the harness enforces them numerically.

## 4. What was cut, and why it is not a loss of contract

- **"Tactics to draw on"** (476 B). Its content: query tactics (synonyms, reformulation,
  decomposition, pseudo-answer, narrow↔broad) — all listed in §1; reach tactics (multiple
  engines, dorking, social/forum/scholarly/structured, region/language, recency) — all in §1;
  quality tactics (prefer primary + credible + diverse, avoid ad/SEO spam) — folded into §2
  "hostile pages"/"primary copies" and the citation-chain rule; efficiency tactics (stop at
  saturation, don't repeat queries, budget to importance) — now §0 and §2 rules with teeth
  rather than advice.
- **Intro sentence** "borromeanRings does not search for you — it makes your search
  dramatically better and keeps the user in control" — the description already says it.
- **§1 parenthetical "(agency first)"** and the standalone line "They have agency here" —
  the ask-to-approve/edit/redirect instruction is kept verbatim.
- **§2 "so coverage is visible and gaps are obvious"** — the graph and the coverage report (§6)
  carry this.
- **§5 "(This is borromeanRings's gate, applied to research.)"** — restated in the intro.

Every numbered section of the old skill is still present with the same obligation; the
frontmatter still names every trigger phrase (exhaustive, mutations, engines, dorking, platform
+ social + specialized, beyond top results, result graph, synthesis, verification fail-closed,
visibility + steering).

## 5. Not done, and why

- **Instrumented before/after on a benchmark query** (issue #47 AC 1–2): needs a real research
  session through the user's agent, which is the very cost under audit; it is also not
  deterministic. Recommended: run one bounded query with `/usage` (or the OTel
  `claude_code.token.usage` counter, `AGENT-TOOLING-SURVEY.md` §2, PR #148) before and after,
  and record it here.
- **`[research]` budget defaults in `borromeanrings.toml`**: the skill honours them if present,
  but `spine.py` does not parse a `[research]` table today; adding one is a separate change.
- **Global installed copy**: `install-global.sh` copies this skill to `~/.claude/skills/`; that
  copy is what actually runs in the user's sessions and is *not* touched by this branch (rule:
  never touch `~/.claude`). Re-run `install-global.sh` after merge.
- **Ratchet on dynamic cost**: `19_context_budget` measures static context only, by design
  (SPEC-context-budget "Out of scope"). A dynamic-cost ratchet would need a token source the
  harness does not have without API keys.
