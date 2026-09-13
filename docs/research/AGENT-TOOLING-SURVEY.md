# Research — Agent tooling survey: token cost, agentic workflow, prior-art detection

> **Scope:** open-source tools that (a) cut token/compute cost when using Claude Code and AI coding
> agents, and (b) improve agentic coding workflows — assessed specifically for **borromeanRings**.
> Researched September 2026. All star counts and commit dates below were pulled from the GitHub API
> (`gh api repos/OWNER/NAME`) on **2026-09-02** and are therefore verifiable, not quoted from READMEs.

> **Method note.** GitHub's search `updatedAt` field is **not** the last-commit date — it moves on
> stars, issues, and metadata edits. Every recency claim here uses `pushed_at`. Several repos that
> look alive in search results are stale by this measure (`claude-code-otel` is the starkest: search
> says 2026-09-01, real last push is **2025-06-17**). Recency claims sourced from search listings
> alone should be distrusted.

## Bottom line

Three findings dominate, and two of them are negative:

1. **Claude Code now does natively most of what the third-party "cost" ecosystem sells** — automatic
   layered prompt caching with a settable TTL, `/compact` + auto-compaction, `/context` and `/usage`
   (including cache hit rate), first-party OpenTelemetry metrics, Haiku subagent delegation, ~30 hook
   events, and GA plugins. Whole categories of popular repos are therefore duplicative.
2. **Most of the existing `enhancements.py` catalog does not apply to Claude Code** — LiteLLM,
   Helicone, GPTCache and RouteLLM all act on API-key traffic you own, which subscription Claude Code
   does not expose. Two of those entries are also unmaintained (RouteLLM: no commits since
   **2024-08-10**).
3. **The genuinely open ground is prior-art detection**, and it splits — but not cleanly. In-repo
   duplication is solved by **jscpd**, which fits both hard constraints exactly *but only detects
   literal copy-paste in Python* (verified by experiment, §7a). "Is there already a library for
   this?" is **unbuilt by anyone**, and for Python it has **no sound deterministic implementation
   today**: every key-free registry API lacks free-text search (verified, §7b). That half belongs in
   the advisory lane, not in a gate.

Meanwhile the entire spec-driven/agentic-workflow field — 280k stars at the top — is **prompt-level
persuasion with nothing that fails closed**. That is borromeanRings's differentiation, now stated as
a verified observation rather than a claim.

## 0. The two hard constraints that decide almost everything

borromeanRings has two constraints that disqualify most of this ecosystem before quality is even
considered:

1. **No independent API keys / no extra token burn.** Any AI step must run through the user's own
   `claude` CLI.
2. **No arbitrary numeric thresholds.** Signals must be threshold-free or non-regression ratchets.

Constraint (1) is more destructive than it first appears. Nearly every "LLM cost" tool in the
ecosystem — gateways, semantic caches, routers, observability proxies — assumes **you own the API
traffic**. Claude Code on a subscription does not expose that traffic to a proxy you control without
re-pointing `ANTHROPIC_BASE_URL`, which changes the auth path entirely. This is the single most
important finding of this survey and it is a **negative** one:

> **Most of the existing `enhancements.py` catalog does not apply to Claude Code subscription usage.**
> LiteLLM, Helicone, GPTCache, and RouteLLM are all API-key-traffic tools. They remain valid entries
> for a *governed project that itself calls an LLM API*, but they are not levers on the cost of
> running Claude Code. The catalog should say so explicitly, per entry.

Constraint (2) is the reason the duplication-detection tooling below matters: the good ones ship a
**baseline** file, which is a ratchet, not a threshold.

## 1. Health audit of the *existing* catalog (do this first)

Before adding anything, three existing entries fail a basic maintenance check:

| Entry | Stars | Last push | Verdict |
|---|---:|---|---|
| **RouteLLM** (`lm-sys/RouteLLM`) | 5,444 | **2024-08-10** | **Abandonware.** ~2 years without a commit. Also API-key-traffic only. **Remove or mark dead.** |
| **GPTCache** (`zilliztech/GPTCache`) | 8,173 | **2025-07-11** | ~14 months stale. API-key-traffic only. **Mark unmaintained.** |
| **OmniRoute** | — | — | Already flagged `verified=False`; the catalog URL is a GitHub *search query*, not a repo. Either resolve it to a real URL or drop it. |
| LiteLLM (`BerriAI/litellm`) | 57,855 | 2026-09-02 | Healthy, but API-key-traffic only — scope note needed. |
| Helicone (`Helicone/helicone`) | 6,126 | 2026-08-31 | Healthy (Apache-2.0), API-key-traffic only — scope note needed. |
| Langfuse (`langfuse/langfuse`) | 34,111 | 2026-09-02 | Healthy. API-key-traffic only. |
| Promptfoo (`promptfoo/promptfoo`) | 24,767 | 2026-09-02 | Healthy (MIT). The one catalog entry that is genuinely usable as-is. |
| MCP reference servers | 90,034 | 2026-09-02 | Healthy. |

**Recommendation:** add a `maintained_as_of` date and an `applies_to` field
(`api-traffic` vs `claude-code`) to `EnhancementTool`. A catalog that recommends a
two-year-dead router is worse than no catalog — it is exactly the "asserting more certainty than it
has" failure the module's own docstring warns against.

## 2. What Claude Code already does natively (so we don't recommend duplicates)

Verified against official docs at `code.claude.com/docs`. This section exists to **kill**
recommendations, and it kills a lot of them.

- **Prompt caching is automatic**, layered (system prompt → project context → conversation), with a
  user-controllable TTL (`CLAUDE_CODE_PROMPT_CACHE_TTL=5m|1h`; 1h is the subscription default).
  Cache reads bill at ~10% of input rate. Cache-busting events are documented: model switch, MCP
  server connect/disconnect, `/compact`, deny-rule changes, Claude Code upgrade.
  → **Nothing third-party is needed here.** Any tool selling "prompt caching for Claude Code" is
  selling something you already have.
- **Context management is built in**: `/clear`, `/compact [focus]`, `/recap`, `/rewind`, plus
  auto-compaction (`autoCompactEnabled`, `autoCompactWindow`).
- **Context and cost inspection is built in**: `/context` and `/usage`. As of v2.1.251+, `/usage`
  reports cache hit rate, misses, and expected rebuilds directly.
- **Telemetry is built in and production-grade**: `CLAUDE_CODE_ENABLE_TELEMETRY=1` plus standard
  `OTEL_*` exporters emit `claude_code.token.usage`, `claude_code.cost.usage`,
  `claude_code.session.count`, `claude_code.lines_of_code.count`, `claude_code.active_time.total`,
  and events including `api_request`, `tool_decision`, `mcp_server_connection`.
- **Cheap-model delegation is built in**: `model: haiku` in subagent frontmatter, or
  `CLAUDE_CODE_SUBAGENT_MODEL=haiku`; `opusplan` plans on Opus and executes on Sonnet.
- **Subagents get isolated context windows** — verbose work stays out of the parent conversation.
  Caveat from the docs: agent *teams* cost ~7x because each teammate carries a full window.
- **~30 hook events exist**, far more than the four borromeanRings currently uses. Notably
  `PreCompact`, `PostCompact`, `SessionStart`, `SubagentStop`, `PermissionRequest`,
  `PostToolUseFailure`, `ConfigChange`, `InstructionsLoaded`. Hook types include
  `command`, `http`, `mcp_tool`, `prompt` (single-turn, Haiku by default) and `agent` (multi-turn).
- **Official cost guidance explicitly recommends two things borromeanRings can act on**:
  "install code intelligence plugins (e.g. TypeScript LSP) — reduces file reads via symbol
  navigation", and "offload to hooks and skills: preprocess data before Claude sees it."

**Consequence:** the entire category of "Claude Code cost tracker" third-party tools (there are
dozens — `Claude-Code-Usage-Monitor` 8,671★, `ccseva` 805★, `claude-lens` 245★, a long tail of macOS
menu-bar apps) is **duplicative of `/usage` + OTel** for a single-developer project. They are
dashboards, not levers. None of them reduce a token.

## 3. Worth adopting now

| Tool | URL | Stars | Last push | Licence | Own API key? | What borromeanRings does with it |
|---|---|---:|---|---|---|---|
| **Ruff `reimplemented-*` rules** (`astral-sh/ruff`) | `github.com/astral-sh/ruff` | 49,450 | 2026-09-02 | MIT | No | **Enable `PIE`, `PERF`, `PL` in `pyproject.toml`.** The only shipping "you reimplemented this" rules anywhere; `20_lint.sh` already runs `ruff check .`, so this is a one-line config change with no new dependency. See §7c. |
| **Official LSP plugins** (`pyright-lsp`) | `github.com/anthropics/claude-plugins-official` | 35,836 | 2026-09-02 | Apache-2.0 | No | **Install for this repo.** First-party, Anthropic-maintained. Gives symbol-level navigation so the agent stops reading whole Python files. Officially named in Anthropic's own cost-reduction guidance. Zero governance risk. |
| **jscpd** | `github.com/kucherenko/jscpd` | 6,129 | 2026-09-02 | MIT | No | **New check: in-repo copy-paste gate.** Rust engine, 220+ languages, JSON + SARIF, and a stateless `--baseline-from-ref` + `--fail-on-new-clones` mode — a non-regression predicate with no baseline file and no number to pick. **Type-1 only in Python** (verified, §7a): it catches copy-paste, not renamed reinvention, and the check must say so. |
| **Serena** | `github.com/oraios/serena` | 28,750 | 2026-09-02 | MIT | **No** (LSP backend is the default and free) | **Catalog entry, `context`/`mcp-server`.** MCP toolkit giving symbol-level retrieval and editing across 40+ languages, LSP-backed. The multi-language answer where the official LSP plugins only cover one language at a time. |
| **ast-grep** | `github.com/ast-grep/ast-grep` | 15,732 | 2026-09-02 | MIT | No | **Check primitive.** Structural (AST) search/lint/rewrite in Rust. Deterministic, offline, machine-readable — the right tool for writing precise structural invariants in `checks/` without regex fragility. |
| **Anthropic plugin distribution** | `github.com/anthropics/claude-plugins-official` | 35,836 | 2026-09-02 | Apache-2.0 | No | **Distribution channel, not a dependency.** Plugins are GA and can bundle hooks + skills + agents + MCP servers + settings in one installable unit. borromeanRings's whole adoption story (`adopt.sh`) is a hand-rolled version of this. Shipping as a plugin makes "governs by reference, per-project opt-in" a one-line install. |
| **Repomix** | `github.com/yamadashy/repomix` | 28,168 | 2026-09-02 | MIT | No | **Catalog entry, `context`.** Packs a repo into one AI-friendly file with per-file token counts and a `--compress` mode that uses tree-sitter to keep signatures and drop bodies. Useful for the maintainer-run "give another model the whole repo" workflow and for measuring context weight. |

### Notes on the six

**Official LSP plugins** are the highest value-per-effort item in this entire survey and cost
essentially nothing: `npm install -g pyright`, then install the plugin. Anthropic maintains 15+ of
them (`pyright-lsp`, `typescript-lsp`, `rust-analyzer-lsp`, `gopls-lsp`, `clangd-lsp`, `ruby-lsp`,
`jdtls-lsp`, `swift-lsp`, `kotlin-lsp`, `php-lsp`, `lua-lsp`, `csharp-lsp`, …).

**jscpd** deserves emphasis because it is the rare tool that fits *both* hard constraints. It needs
no key, it emits JSON, and its baseline mechanism is a non-regression ratchet by construction: the
gate is "duplication count must not exceed the committed baseline", never "duplication must be under
5%". It also now ships an MCP server and a token-efficient reporter, which is a sign of active
maintenance rather than a stale linter.

**Serena vs the official LSP plugins** is not either/or, but for a Python repo the official plugin
is strictly lower-risk. Serena earns its place in the *catalog* (advisory, for governed projects in
other languages) rather than as a borromeanRings dependency. Its evaluation section is written as
testimonials from AI agents, which is a marketing device — discount the prose, keep the tool.

## 4. Interesting, not yet

| Tool | URL | Stars | Last push | Licence | Why not yet |
|---|---|---:|---|---|---|
| **Context Mode** | `github.com/mksglu/context-mode` | 20,314 | 2026-09-02 | **Elastic Licence 2.0 — source-available, NOT OSI open source** | Technically the most interesting cost tool found: sandboxes MCP/tool output into SQLite+FTS5 instead of the context window, and pushes a "think in code" pattern (write a script that prints one number rather than reading 47 files). Real, active, no API key. **Two blockers:** (a) ELv2 is not open source, and blog posts calling it "an open source MCP plugin" are wrong; (b) it registers `PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `PreCompact`, `SessionStart`, and `Stop` — **the same hooks borromeanRings uses**. Adopting it without an ordering/conflict story risks silently breaking the gate. Worth a spike specifically to test hook coexistence. |
| **codanna** | `github.com/bartolli/codanna` | 733 | 2026-08-29 | Apache-2.0 | Local code-intelligence MCP + CLI, no API key. A leaner Serena. Small user base; revisit if Serena proves heavy. |
| **probe** | `github.com/probelabs/probe` | 695 | 2026-09-02 | Apache-2.0 | ripgrep + tree-sitter code search for agents, no API key, no index to maintain. Genuinely fits the constraints; simply overlapped by Serena/LSP for now. |
| **OpenSpec** | `github.com/Fission-AI/OpenSpec` | 67,060 | 2026-09-02 | MIT | Spec-driven development for AI assistants. borromeanRings already has `docs/specs/SPEC-*.md` and an ADR discipline check. Value would be *convergence on a format others already use*, not new capability. Read it for format ideas before extending our own. |
| **github/spec-kit** | `github.com/github/spec-kit` | 133,098 | 2026-09-02 | MIT | The category king by stars. Same reasoning as OpenSpec — it is a *workflow scaffold* (`/specify`, `/plan`, `/tasks`), not a gate. It produces artifacts; borromeanRings enforces them. Complementary, and a plausible thing to *detect and check* rather than adopt: "if `.specify/` exists, assert specs are current." |
| **Semgrep** | `github.com/semgrep/semgrep` | 16,482 | 2026-09-01 | LGPL-2.1 | Mature, active, offline-capable rule engine. Heavier than ast-grep and its best rules live behind a registry account. Consider only if ast-grep proves insufficient. |
| **LLMLingua** | `github.com/microsoft/LLMLingua` | 6,623 | 2026-04-08 | MIT | Research-grade prompt compression (EMNLP'23/ACL'24). Requires a local compressor model and operates on prompts you construct — there is no seam to insert it into Claude Code. ~5 months stale. Academically interesting, practically inapplicable here. |
| **Caveman** (skill only) | `github.com/JuliusBrussee/caveman` | 102,616 | 2026-09-02 | **Split: MIT skill / BSL-1.1 engine+proxy** | See §5 — partially real, partially disqualified. |

## 5. Looks relevant, actually isn't

**`ColeMurray/claude-code-otel`** (494★, MIT) — presents as "comprehensive observability for Claude
Code". Last real commit **2025-06-17**, ~15 months ago, and it wraps the native OTel exporter that
Claude Code now documents first-party. **Abandonware wrapping a built-in.** Do not adopt.

**`zilliztech/claude-context`** (12,464★, MIT, pushed 2026-07-14) — "Code search MCP for Claude Code,
make the entire codebase the context". Looks like a perfect fit until you read the install: it
requires `OPENAI_API_KEY` *and* a Zilliz Cloud `MILVUS_TOKEN`. **Two third-party keys, one of them a
competing model provider.** Disqualified outright by constraint (1). This is the clearest example of
why the catalog needs an explicit "needs own API key" field.

**`sturdy-dev/semantic-code-search`** (403★, AGPL-3.0) — last push **2023-05-14**. Over three years
dead. Ranks high on "semantic code search" queries. **Abandonware.**

**`JuliusBrussee/caveman`** (102,616★) — the highest-starred token tool found, Product-Hunt and
Trendshift badged. It deserves a careful verdict rather than a dismissal, because it is *more honest
than its marketing*: its own README states that the skill "only shortens **output**", that its rules
cost "about 1–1.5k input tokens every turn", that "on workloads that were already terse you can lose
money", and it ships a `docs/HONEST-NUMBERS.md` documenting its losses. That is genuinely good
practice. **But:** the headline 65% figure is output-token-only across 10 hand-picked prompts, and
the part that actually reduces *input* tokens — the Engine, Proxy, Cache Engine, rewriter, and MCP
server — is **BSL-1.1, not OSI open source**, converting to Apache-2.0 only in 2030. Only the skill
is MIT. Additionally, its mechanism is instructing the model to write tersely, which directly
conflicts with borromeanRings's interest in legible, reviewable agent output, and Context Mode cites
evidence that aggressive brevity prompts degrade coding benchmarks. **Do not adopt; do not catalogue
as open source.**

**The Claude Code cost-dashboard category** — `ccusage` (18,299★, MIT despite GitHub reporting
`NOASSERTION`; the LICENSE file is plain MIT), `Maciek-roboblog/Claude-Code-Usage-Monitor`
(8,671★, MIT, pushed 2026-07-05), `claude-hud` (27,793★, MIT), plus a dozen menu-bar clones. These
parse `~/.claude/projects/**/*.jsonl` and render spend. They are well-built and popular, and they
are **measurement, not reduction**. `/usage` now shows cache hit rate natively. For a single
maintainer, `ccusage` is a fine personal utility — it is not a borromeanRings dependency, a check,
or a catalog entry, because the catalog is for tools that *improve the wrapped agent*.

**`disler/claude-code-hooks-multi-agent-observability`** (1,529★) — **no licence file at all** and
last pushed 2026-02-08. Unlicensed code is not adoptable regardless of quality.

**`Ido-Levi/claude-code-tamagotchi`** (436★, MIT) — despite the name, it is described as "real-time
behavioural enforcement for Claude Code: monitors AI actions, detects violations, intervenes",
i.e. the nearest prior art to borromeanRings's hook layer. Last push **2025-10-20**, ~10 months
stale. Worth reading once for its interception patterns; not worth depending on.

**`parcadei/Continuous-Claude-v3`** (3,933★, MIT) — hook-based context management via ledgers and
handoffs, conceptually close to our `HANDOFF.md` practice. Last push **2026-01-26**, ~7 months.
Read, don't adopt.


## 6. Agentic coding workflow — the "gate for agents" landscape

This is the category closest to borromeanRings's own thesis, so the important question is not
"what should we adopt" but "**who is already doing this, and are they enforcing or merely
suggesting?**" The answer is consistent and favourable:

| Tool | URL | Stars | Last push | Licence | Enforcing or suggesting? |
|---|---|---:|---|---|---|
| **Superpowers** | `github.com/obra/superpowers` | 280,825 | 2026-08-31 | MIT | **Suggesting.** Skills that auto-trigger a spec → plan → red/green TDD → subagent-driven-execution methodology. Explicitly a *methodology*, delivered as prompts. Nothing fails closed. |
| **github/spec-kit** | `github.com/github/spec-kit` | 133,098 | 2026-09-02 | MIT | **Suggesting.** Scaffolds `/specify`, `/plan`, `/tasks` artefacts. Produces documents; verifies nothing. |
| **OpenSpec** | `github.com/Fission-AI/OpenSpec` | 67,060 | 2026-09-02 | MIT | **Suggesting.** Spec format + workflow for AI assistants. |
| **get-shit-done** | `github.com/gsd-build/get-shit-done` | 64,605 | 2026-05-31 | MIT | **Suggesting.** Meta-prompting/context-engineering system. Note: ~3 months stale and the author has started a successor (`gsd-build/gsd-2`, 7,771★, active) — adopting v1 means adopting a version being replaced. |
| **planning-with-files** | `github.com/OthmanAdi/planning-with-files` | 26,588 | 2026-09-02 | MIT | **Suggesting.** Crash-proof file-based plans for long-running agents. |
| **Agent OS** | `github.com/buildermethods/agent-os` | 5,364 | 2026-08-29 | MIT | **Suggesting.** Injects codebase standards into spec-driven workflows. |
| **spec-workflow-mcp** | `github.com/Pimzino/spec-workflow-mcp` | 4,293 | 2026-07-03 | **GPL-3.0** | **Suggesting.** MCP server exposing spec workflow tools. GPL-3.0 is a notable licence constraint for anything linking it. |
| **claude-code-tamagotchi** | `github.com/Ido-Levi/claude-code-tamagotchi` | 436 | **2025-10-20** | MIT | The only one that claims **enforcement** ("detects violations, intervenes"). ~10 months stale. |

**The finding:** at every scale, from 280k stars down, this category is **prompt-level persuasion**.
Not one maintained project makes agent workflow compliance *fail closed*. `spec-kit` will happily let
you generate a spec and then ignore it; Superpowers will let the agent skip TDD if the model decides
to. The single project that framed itself as enforcement has been stale for ~10 months.

That is borromeanRings's differentiation, stated in verifiable terms rather than as a claim, and it
suggests a concrete design move: **do not compete with these frameworks — govern them.** A check that
detects `.specify/`, `openspec/`, or a Superpowers plan directory and then *verifies the artefacts are
current against the diff* turns the most popular scaffolds in the ecosystem into inputs for a
fail-closed gate. That is strictly more valuable than borromeanRings inventing a ninth spec format,
and it directly serves the "adapt behaviour to project archetype" goal.

**Adopt now:** none of them as dependencies. **Read for format convergence:** OpenSpec and spec-kit,
before extending `docs/specs/SPEC-*.md`. **Build against:** detection + freshness checks for whichever
of these a governed project already uses.

## 7. Prior-art / duplication detection — one gate to build, one to refuse to build

borromeanRings wants a check that answers *"does this already exist before you build it?"* The
question splits into three, with sharply different maturity — and the honest answer to the most
interesting one is "not buildable as a gate, for this language, today." Claims in this section were
tested by running the tools against purpose-built fixtures, not read off READMEs.

### 7a. In-repo duplication — adoptable today, but it catches *copy-paste*, not *reinvention*

| Tool | URL | Stars | Last push | Licence | Key? | JSON out? |
|---|---|---:|---|---|---|---|
| **jscpd** | `github.com/kucherenko/jscpd` | 6,129 | 2026-09-02 | MIT | No | Yes — JSON, SARIF, **baseline** |
| ast-grep | `github.com/ast-grep/ast-grep` | 15,732 | 2026-09-02 | MIT | No | Yes |
| Semgrep | `github.com/semgrep/semgrep` | 16,482 | 2026-09-01 | LGPL-2.1 | No (registry rules optional) | Yes (SARIF) |
| comby | `github.com/comby-tools/comby` | 2,672 | 2026-06-08 | Apache-2.0 | No | Partial |

**jscpd is the right choice** and the fit is better than "adequate" — it is close to purpose-built
for this constraint set:

- `src/meta_harness/ratchet.py`'s own docstring already lists **"duplication"** among the metrics the
  ratchet primitive is meant to serve — the slot is designed and empty. This is not a new mechanism,
  it is filling a declared one.
- jscpd ships a **fingerprint baseline**, and — the important part — a *stateless* variant:
  `jscpd --baseline-from-ref origin/main --fail-on-new-clones .` It checks out the base ref, scans it
  with identical configuration, and compares content-hash fingerprints in memory. That is a pure
  non-regression gate with **no committed baseline file to drift and no number to choose**. The
  documented default of `--fail-on-new-clones` is N=0, i.e. "no new clones", which is a
  *predicate*, not a threshold.
- New-clone data is machine-readable and explicitly named: the `json` reporter emits per-clone
  `isNew` plus `newClones` and `newDuplicatedLines` statistics; SARIF marks new clones `error` and
  carries `partialFingerprints["jscpdCloneHash/v1"]`.
- **Note this means the check may not need `decide_ratchet` at all.** The committed-baseline form
  (`--baseline .jscpd-baseline.json`) is available if borromeanRings prefers a visible, reviewable
  baseline artefact consistent with `.borromeanrings-*-baseline`; the ref-based form is simpler and
  has less state. Worth a deliberate choice rather than defaulting to the ratchet out of habit.
- It is an external binary, so it follows the existing optional-tool pattern: `emit_noop` when jscpd
  is absent, and register in `[checks].heavy` (CI tier) first, mirroring `60_mutation` /
  `70_pip_audit`. `--baseline-from-ref` needs full git history in CI (`fetch-depth: 0`).
- It also exposes `--mcp`, serving `check_duplication` / `get_statistics` over stdio — so the same
  binary can later back an advisory MCP tool for the agent, not just a gate.

**Operational gotchas, verified by running it:**

- `--threshold 0 --exitCode 1` exits **2**, not 1. Do not write `[ "$?" -eq 1 ]`.
- The CLI prints **unsolicited vendor marketing** to stdout/stderr (a "Gangsta Agents" pitch, an
  OpenCollective appeal, an "Auto-refactor with AI" skill ad). Run with `--silent` and parse the
  JSON report file; never parse the console.
- The ratchet counter is `statistics.total.clones` (integer); `newClones` / `newDuplicatedLines` /
  per-clone `isNew` appear when a baseline is in play.
- Ships first-party `.pre-commit-hooks.yaml` and `action.yml`.

#### The limitation that must go in the check's own description

Three fixture pairs were built and run against every offline candidate:

| Fixture | jscpd v5 | PMD CPD 7.27.0 | similarity-py 0.5.0 |
|---|---|---|---|
| Identical body, only the **function name** differs | 1 clone | 1 clone | 0 |
| Same structure, **all variables renamed**, one line inserted | **0** | **0** (even with `--ignore-identifiers`) | **0** |
| Two identical functions in **one** file | n/a | n/a | 1 pair @ 100% |
| Two identical functions in **two** files | 1 clone | 1 clone | **0 — broken** |

**Every offline clone detector worth adopting is Type-1 only in Python.** They match identical token
runs. An AI agent that writes a near-duplicate with its own variable names — the overwhelmingly
likely case — **evades all of them**. PMD CPD's `--ignore-identifiers` is a **silent no-op for
Python** (it is Java/C++ only; the run produced zero findings and no warning), which is the single
most likely thing to mislead a future maintainer into thinking the gate is stronger than it is.

So the check must describe itself as **"detects copy-pasted code"**, never "detects reinvention".
Overclaiming here is precisely the dishonest-green failure that `01_source_coherence` and the
honest-noop work exist to prevent: a passing clone gate on a renamed duplicate proves nothing, and
the check should be capable of saying so in its own receipt.

**PMD CPD** (`pmd/pmd`, 5,482★, pushed 2026-09-02, custom BSD-style licence reported as
`NOASSERTION`) is the cross-check option: exit **4** = duplicates found, **0** = clean, XML only (no
JSON), 133 MB distribution. Strictly worse than jscpd for a Python-only repo — same detection power,
heavier, harder to parse. Worth revisiting only if borromeanRings governs Java or C++, where
`--ignore-identifiers` genuinely works and buys real Type-2 detection.

Modelled on `checks/python/33_coupling.sh` (~40 lines of shell over a ~45-line module), this is a
**half-day** check including tests and a `docs/CHECKS.md` entry.

### 7b. "Is there already a library for this?" — unbuilt, and for Python **not buildable as a gate**

This half does not exist as a tool. That much was easy to establish. The harder and more useful
finding is *why it also cannot be built deterministically here* — every key-free package API was
probed directly and **none supports free-text search**:

| Source | Auth | Free-text search? | Verified result |
|---|---|---|---|
| **deps.dev** (`google/deps.dev`, 443★) | None (anonymous 200) | **No** | v3alpha exposes `GetPackage`, `GetVersion`, `GetDependencies`, `GetFindings`, `Query` (by *hash*), `GetSimilarlyNamedPackages` (by *name*). Answers "tell me about this package", never "find a package that does X". |
| **ecosyste.ms** (`ecosyste-ms/packages`, 109★, AGPL-3.0) | None | **No** | OpenAPI spec declares only `/packages/lookup` (exact name/purl/repo URL) and `/keywords/{name}`. A probe of `?query=` returned a package literally *named* `search` — the path segment is read as a package name. |
| **PyPI** | None | **No** | XML-RPC `search` was disabled years ago. Only the HTML page and per-package `/pypi/<name>/json`. |
| **libraries.io** | **Key required** | Yes | Returns `401 {"error":"An API key is required."}`. Disqualified by constraint (1). |
| **npm registry** | None (anonymous 200) | **Yes** | `registry.npmjs.org/-/v1/search?text=…&size=N` returns JSON with descriptions, keywords, downloads. The only key-free full-text option — **JS/TS only**. |
| **GitHub code search** (`gh search code`) | Already authenticated here | Yes | Works, but rate-limited to **10 requests/minute**. Enough for one targeted query per new module; not for a repo sweep. |

**Correction worth stating plainly:** deps.dev is the tool this idea intuitively reaches for, and it
is the wrong one. It is a dependency-graph and advisory API, not a discovery API.

**Consequence.** Python — borromeanRings's own language and that of most governed projects — is the
**worst-served ecosystem** for this question. There is no deterministic, key-free way to ask "does a
library already do this" for a Python module. Therefore:

> The "does a library already exist" half must live in the **advisory lane** — alongside the
> agent-enhancement recommender and steered research, driven by the user's own `claude` CLI — and
> must **not** be a gate. A gate that cannot answer its question deterministically is exactly the
> dishonest-green failure the `01_source_coherence` / honest-noop work exists to prevent.

The one gate-shaped thing that *is* available is narrower and is described in §7d.

### 7c. The only shipping "you reinvented it" rules — and they are one config line away

Ruff (`astral-sh/ruff`, 49,450★, MIT, pushed 2026-09-02, no API key, `--output-format json`) is the
only maintained linter anywhere that ships rules literally named for reimplementation. Enumerated
against the **ruff 0.15.8 already on this machine** (`ruff rule --all --output-format json`):

| Code | Rule | Linter | In this repo's `select`? | Preview-gated? |
|---|---|---|---|---|
| `SIM110` | `reimplemented-builtin` | flake8-simplify | **Yes** (`SIM` selected) | No |
| `PIE807` | `reimplemented-container-builtin` | flake8-pie | **No** | No |
| `PERF401` | `manual-list-comprehension` | Perflint | **No** | No |
| `PERF402` | `manual-list-copy` | Perflint | **No** | No |
| `PERF403` | `manual-dict-comprehension` | Perflint | **No** | No |
| `PLR0402` | `manual-from-import` | Pylint | **No** | No |
| `FURB118` | `reimplemented-operator` | refurb | **No** | **Yes** — needs `preview = true` |
| `FURB140` | `reimplemented-starmap` | refurb | **No** | **Yes** — needs `preview = true` |

`pyproject.toml` currently has `select = ["E", "F", "I", "B", "UP", "SIM"]`, and `checks/python/20_lint.sh`
already runs `ruff check .` as a required check. So **adding `"PIE", "PERF", "PL"` to `select` turns on
five more reimplementation rules through machinery that already exists** — no new check, no new
dependency, no new baseline. FURB118/140 additionally require opting into Ruff preview mode, which is
a separate stability decision and should not be bundled with the free part.

**Honest scope note:** these rules are a **hand-curated, stdlib-only list**. They catch "you wrote a
loop instead of `any()`". They do not read your dependency graph and do not generalize. The same is
true of every tool in this camp (`dosisod/refurb` 2,532★ — now largely redundant since Ruff
reimplemented its rules natively; `eslint-plugin-unicorn`'s `prefer-*` family; staticcheck's S1xxx).

### 7d. Looks relevant, actually isn't

- **`zilliztech/claude-context`** (12,464★) — reads as the obvious "search your codebase before you
  write" answer; requires `OPENAI_API_KEY` plus a Zilliz Cloud token. Disqualified.
- **`sturdy-dev/semantic-code-search`** (403★, AGPL-3.0) — last push **2023-05-14**. Abandonware.
- **`upstash/context7`** (61,532★, MIT) — ranks first for "up-to-date library docs for LLMs" and is
  frequently recommended as the prior-art/doc-freshness tool. The MIT repo is a **client for a hosted
  Upstash service**; the index is not self-hostable and an API key is recommended for usable rate
  limits. It is a SaaS dependency wearing an OSS licence. The honest alternative is
  **`arabold/docs-mcp-server`** (1,706★, MIT, pushed 2026-08-29), which self-hosts and makes
  embeddings optional (Ollama works, so no third-party key) — a better fit if the `55_doc_drift`
  check ever wants library-doc grounding.
- **`mizchi/similarity` / `similarity-py`** (823★, MIT, pushed 2026-04-16) — markets itself as exactly
  this use case: AST-based (APTED tree edit distance), "detects duplicate functions across your
  codebase", ships `--fail-on-duplicates`. **It was installed and tested, and cross-file detection
  does not work.** Two files each holding a 100%-identical function: *"No duplicate functions
  found!"* — at threshold 0.5, with `--no-fast`, with `-e py`, and with both files passed explicitly.
  Concatenate the same two functions into one file and it reports 100%. Intra-file works; cross-file
  is broken, and this is **not** in the project's `KNOWN_ISSUES.md`. Their own maturity table already
  labels `similarity-py` **Beta / "not production-tested yet"** — believe it. It also has **no JSON
  output**, so it could not drive a ratchet even if it worked.
- **`danielstjules/jsinspect`** (3,581★) — **abandonware**; last push 2024-03-20, last release
  **2017-08-15**. The star count is a trap.
- **`depcheck`** (4,926★) and **`codeclimate-duplication`** (118★) — both **archived**. Dead despite
  the stars.
- **`skyhover/Deckard`** (224★, `NOASSERTION`, last push 2024-03-05) — research artifact, not a CI tool.
- **Simian** — **not open source**; a commercial RedHill Consulting product, not on GitHub.
- **`mibk/dupl`** (368★, MIT) — genuinely structural (AST suffix tree), and therefore the kind of
  thing that *would* close the Type-2 gap. **Go only.** Already vendored in golangci-lint.
- **knip** (12,166★), **dependency-cruiser** (7,129★), **vulture** (4,790★) — all healthy, all
  solving *unused* code/deps, which is the **inverse** problem. They detect nothing about
  reimplementation and should not drift into this design by association.
- **Package-registry MCP servers** — `Artmann/package-registry-mcp` (39★) and
  `loonghao/pypi-query-mcp-server` (18★) are **thin wrappers** over registry HTTP APIs at near-zero
  adoption. They add an MCP dependency and a nondeterministic agent hop to something that should be
  a `curl`. Skip; call the registry directly.
- **SeaGOAT** (`kantord/SeaGOAT`, 1,303★, MIT, pushed 2026-08-28) — local-first semantic code search,
  no API key, genuinely answers "do we already have a function that does X". **Blocker:** it is a
  long-running *server* (`seagoat-server start`), not a one-shot CLI — a poor fit for a stateless
  gate. Revisit if it gains a batch mode.
- **Dolos** (`dodona-edu/dolos`, 347★, MIT, pushed 2026-09-01) — a *plagiarism* detector, therefore
  explicitly designed to survive renaming, i.e. the exact Type-3 gap the §7a tools have. Education-
  oriented and web-app-first (tuned for comparing many submissions of one exercise rather than
  scanning a repo), CSV output. **Highest-upside experiment** if the Type-1 limitation ever becomes
  the binding constraint.
## 8. Standing recommendations for the enhancement catalog

Concrete changes to `src/meta_harness/enhancements.py`:

1. Add fields: `maintained_as_of: str` (ISO date the maintainer last verified the repo was alive),
   `needs_api_key: bool`, and `applies_to: Literal["api-traffic", "claude-code", "both"]`.
2. Mark RouteLLM dead (2024-08-10) and GPTCache unmaintained (2025-07-11). Resolve or drop OmniRoute.
3. Annotate LiteLLM / Helicone / Langfuse / GPTCache as `applies_to="api-traffic"` so the recommender
   stops implying they cut Claude Code cost.
4. Add: Serena (`context`), Repomix (`context`), ast-grep (`context`), probe (`context`, second
   choice), codanna (`context`, second choice).
5. Add a `source-available` flag or exclude Context Mode and Caveman by policy — a catalog that says
   "open-source tools" must not list ELv2 and BSL-1.1 projects without saying so.
6. Consider a `render_recommendation` line that prints "verified alive YYYY-MM-DD" per entry. The
   module's docstring already promises never to assert more certainty than it has; a dead link with
   no date breaks that promise.

## 9. Top 5 ranked recommendations

Ranked by (value to borromeanRings) ÷ (effort), with effort grounded in the existing check pattern
(`checks/python/33_coupling.sh` is ~40 lines of shell over a ~45-line module).

| # | Recommendation | Effort | Why it ranks here |
|---|---|---|---|
| 1 | **Add `"PIE", "PERF", "PL"` to `[tool.ruff.lint].select`** in `pyproject.toml` | **~15 min** | Turns on `PIE807`, `PERF401/402/403`, `PLR0402` — five of the only shipping "you reimplemented this" rules in existence — through `checks/python/20_lint.sh`, which already runs `ruff check .` as a required check. No new tool, no new dependency, no baseline, no threshold. Verified against the ruff 0.15.8 already installed here. Highest value-per-minute in the survey. |
| 2 | **Install the official `pyright-lsp` plugin** on this repo | **~15 min** | Anthropic-maintained, zero governance risk, and named in Anthropic's own cost guidance as the way to cut file reads. |
| 3 | **Health-audit `enhancements.py`** — add `maintained_as_of` / `needs_api_key` / `applies_to`; mark RouteLLM dead and GPTCache unmaintained | **~2–3 h** | The catalog currently recommends a router with no commits since **2024-08-10** and four tools that cannot affect Claude Code cost at all. Correctness-first is the module's stated contract; right now it breaks it. |
| 4 | **Build the duplication check on jscpd** (`[checks].heavy`, `--baseline-from-ref` + `--fail-on-new-clones`, `--silent`, parse JSON) | **~half a day** | Deterministic, key-free, thresholdless. **Ship it described as "detects copy-pasted code"** — the fixtures in §7a prove it is Type-1 only in Python, and the check's receipt should say so rather than implying it caught reinvention. |
| 5 | **Widen hook coverage beyond the current four** — at minimum `PreCompact`, `SessionStart`, `SubagentStop` | **~1 day** | ~30 hook events exist; borromeanRings uses four. `PreCompact` is the moment governance state is most likely silently lost — the same failure mode the in-flight honest-noop work is chasing. |

**Runners-up, deliberately not in the top 5:** ship borromeanRings as a Claude Code plugin (~2–3 days
— the right long-term answer for per-project opt-in, since `adopt.sh` hand-rolls a now-first-party
mechanism, but it is distribution work, not capability); Serena and Repomix as *catalog entries*
(~1 h of data entry each, no code); a spike on **Context Mode** hook coexistence (~half a day, gated
on accepting an Elastic-Licence dependency — probably a "no", though its "think in code" pattern is
worth adopting as documented practice regardless); an **ADR on bounded dependency-reimplementation
detection** (§7b/§7c show nobody has built this; a version that extracts public callables from
declared dependencies and matches new function names/signatures against them, **advisory only**,
would be genuinely novel and needs no LLM — but it is research, not a scheduled check).

**Explicitly recommended against:** any third-party Claude Code cost dashboard (duplicative of
`/usage` + OTel — measurement, not reduction); `caveman` (its input-reducing half is BSL-1.1, and
terse-output prompting fights legibility); `claude-code-otel` (abandonware wrapping a built-in);
`zilliztech/claude-context` (two third-party API keys); `similarity-py` (cross-file detection is
broken, verified); `jsinspect` / `depcheck` / `codeclimate-duplication` (abandoned or archived);
**deps.dev as a discovery API** (it has no free-text search — the intuitive choice is the wrong one).
