# Changelog

All notable changes to borromeanRings are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to
follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Discipline is enforced by check `11_changelog`: this file must exist and carry an
`## [Unreleased]` section (a home for pending changes). The stricter
"every source change updates the changelog" rule is available via
`[changelog].require_entry_on_src_change` and will be enabled once the current PR
queue is merged.

## [Unreleased]

### Fixed
- `15_a11y` reported `pass` for a project with no HTML at all — a hollow green (#154).
  Under ADR-0049 a check that inspected nothing must say so: it now exits 3 ⇒ `noop`,
  the log names what was searched (git-tracked `*.html/*.htm/*.xhtml`, minus
  `[a11y].exclude`) and where, and the gate output counts it under `inspected NOTHING`.
  Clean HTML ⇒ `pass`, violations ⇒ `fail`, unchanged. The HTML walk now mirrors
  `01_source_coherence`: a `git ls-files` failure inside a repo **fails closed** (never a
  `noop`), and a non-git project falls back to a filesystem walk (honouring `exclude`) and
  evaluates what it finds. Locked down by an integration suite
  (`tests/integration/test_a11y_gate.py`) driving `verify.sh` on every fixture.

### Added
- Session charter gate (ADR-0063, #173): a committed `CHARTER.toml` (goal, stakes `low`|`high` — two opt-in tiers, never a dial — done_when/stop_when/may_not, owner; `high` also requires rollback/reviewer/blast_radius) validated fail-closed by `22_charter` via the pure `meta_harness.charter` (every violation as `field — reason`, hedged `done_when` items rejected, unknown keys/stakes rejected, never `noop`); `[charter]` spine block; a sub-120-byte UserPromptSubmit reminder when enabled and the file is missing; this repo declares its own high-stakes charter. Mechanism re-authored from a CC BY-NC-SA source — no text or code copied.
- Application archetypes (ADR-0062, #79 phase 1): a project declares what KIND of app it
  is — `[project].archetypes = ["cli", "library"]` (vocabulary: `library`, `cli`,
  `web-api`, `web-app`, `ml`, `embedded`, `data-pipeline`; unknown ⇒ fail closed at config
  time) — and `21_archetype` gates the **required features of that kind**: a health route
  declared, structured logging configured, an input-validation layer, an auth mechanism,
  a rate limiter, config from the environment (web-api); an i18n catalog, a viewport meta,
  a bundle budget, an error page (web-app); a model card, datasheet, schema, fixed seeds,
  lockfile, evaluation script, baseline, NaN guard, rollback command (ml); watchdog,
  static analysis, HAL, linker script, host tests, pinned toolchain (embedded); and so on.
  Every feature is a binary file-presence or content-regex fact with an evidence path in
  the log (as `[<file>:<line>]`) — no model, no network, no build; what cannot be decided
  that way lives in the archetype's advisory **playbook** instead. The catalog is versioned
  immutable data (`meta_harness.archetypes.CATALOG`). Second half: an archetype can require
  a check to be **non-`noop`** — the verdict now turns the run FAIL when e.g. a declared
  `web-app`'s `15_a11y` inspected no HTML (*"required to inspect something by archetype
  web-app"*), the #130 vacuity case; `15_a11y` accordingly reports `noop` (not `pass`) on
  no tracked HTML. `verify.sh` refuses a config the spine rejects instead of falling back to
  `python`. This repo declares `cli` + `library` (six features, all evidenced, nothing
  faked). Unit (catalog integrity, evaluate on fixtures, exact render) + integration (off /
  pass / fail / unknown / hollow-green-turned-red / negative control). Adopt-recommended.
  Closes matrix rows O5+, O6, O7, O11, M1, M5, M6, M9, M11, M12, M16, U10s, U12d, U14s, U17.
### Changed
- `borromeanrings-research` skill token audit (ADR-0060, issue #47): the skill's static
  cost is measured at 4176 B → 3692 B (`docs/research/RESEARCH-SKILL-TOKEN-AUDIT.md`,
  per-file and per-section), and the dynamic drivers are traced and ranked — working state
  kept in context, whole-page ingestion, unbounded fan-out, re-fetch on verification. The
  protocol now declares an editable budget (rounds, queries/round, sources/round, extracted
  lines/source — knobs the user approves, never gates), writes plan/log/sources/graph/report
  to `docs/research/<slug>/`, extracts passages instead of ingesting pages, caches URLs and
  queries, verifies against the saved passage, delegates fetch+extract to a sub-agent where
  available, reads symbols not files on code hosts, and stops at saturation. Same contract;
  the redundant "Tactics" section is folded into the numbered steps.
  `.borromeanrings-context-baseline` re-seeded downward to 31690 (the ratchet tightens on
  purpose) and a test pins the skill at ≤ 3692 B (in `tests/integration/`, which
  mutmut skips: it reads `.claude/`, which mutmut's `mutants/` copy lacks).

### Added
- **Static a11y rules for labels, link text and heading structure** (ADR-0075, #159) —
  matrix rows U4–U6 of `docs/matrices/06-product-ux.md`, added to `15_a11y` (not a second
  check) and **opt-in** via `[a11y].require`, so a project adopts one at a time:
  `control_label` (every `<select>`/`<textarea>`/`<input>` except
  `hidden|submit|button|reset|image` has an accessible name — a wrapping or
  `for=`-associated `<label>`, a non-empty `aria-label`, or an `aria-labelledby` naming an
  id that **exists**; WCAG 2.2 SC 3.3.2, 4.1.2), `link_text` (every `<a href>` has
  non-empty text, an ARIA name, or an `<img alt="...">` inside it; SC 2.4.4), and
  `heading_structure` (a full document has exactly one `<h1>`; no heading skips a level;
  `<template>` and comment content excluded; SC 1.3.1). Findings now carry a source line
  and are reported as `file:line — [rule] — what is wrong` (an absence, such as a missing
  `<title>` or `<h1>`, prints without a line rather than inventing one). Defaults are
  unchanged — `[a11y].require` still defaults to the three ADR-0045 rules, and `adopt`'s
  `RECOMMENDED` set is untouched.
  Deliberately **not** built and specified instead (#210): contrast, keyboard
  reachability/visible focus, target size and the axe-core violation ratchet (rows
  U7–U9, U18) are properties of the *rendered* page, not the source. No banned-phrase
  ("click here") list either: link purpose *in context* is a judgement, not a fact.

### Fixed
- `15_a11y` treated `<script src="a.js"/>` as an element that never ends, so everything
  after it was dropped and an `<a href>` past it was reported as an unnamed link where a
  browser has no link at all. A regression introduced by the self-closing fix below and
  caught by verification: `html.parser` skips its raw-text switch on the `/>` form, so
  the run of text is now started explicitly. A void `<br/>` is still closed once, and a
  foreign `<rect/>` still self-closes.
- `15_a11y` reported an empty `<title>` for `<title><b></b></title>`, where a browser
  shows the literal string `<b></b>` and the title is not empty. Tag-shaped text inside a
  text-only element is now kept as text (start tags via `get_starttag_text()`, end tags
  and comments reconstructed), instead of being dropped as markup that was never there.
- `15_a11y` checked `<math><a href>` for link text. The SVG-anchor departure is a
  judgement about links a user clicks; MathML has no anchor element, so there is nothing
  there to click and nothing to judge.
- `15_a11y` judged some rules against the accessibility tree and others against the DOM.
  **Every rule that judges rendered content now skips `hidden`/`aria-hidden` subtrees**,
  the heading outline included. The outline was exempted at first on the argument that
  dropping an element out of a *sequence* could invent a finding; verification showed the
  argument inverted. `<h1><h2><div hidden><h3></div><h4>` and `<h1><h2><h4>` are the same
  document to a screen reader and were given opposite verdicts — counting the hidden
  heading **masked** a real skipped level rather than preventing an invented one. It also
  ran the other way: `<div hidden><h1>Dup</h1></div><h1>Real</h1>` reported "a further
  `<h1>`" on a page where nothing can perceive two. `page_title` and `html_lang` are
  unaffected, and for a different reason than the one first given: a `<title>` and the
  `<html>` element are *document metadata*, which `hidden` cannot remove. Each case is
  pinned by a test, including one that fails if the rule ever spreads to `page_title`.
- `15_a11y` **failed correct markup** in four ways, each found by an adversarial review of
  PR #211 and each now pinned against html5lib:
  - **A text-only element's content was read as markup.** The HTML tokenizer reads
    `<textarea>`, `<title>`, `<iframe>`, `<xmp>`, `<noembed>`, `<noframes>` and
    `<plaintext>` as raw text or RCDATA; `html.parser` knows this for `script`/`style`
    only. So `<textarea><img src="cat.png"></textarea>` — a "paste your markup here" box
    that every browser renders correctly — raised `img_alt`, a **default-gated** rule,
    where html5lib finds no image at all.
  - **HTML integration points were tested as the union of both namespaces.**
    `<foreignObject>`/`<desc>`/`<title>` are SVG's and `<mtext>`/`<mi>`/`<mo>`/`<mn>`/
    `<ms>`/`<annotation-xml>` are MathML's, so `<svg><mtext><input>` was a form control
    and `<math><desc><title>Icon</title></desc></math>` silenced `page_title` — the same
    defect the previous commit set out to retire, in both directions. The namespace is
    also **inherited** now rather than read off the nearest `<svg>`/`<math>` tag name
    (html5lib confirms the `<svg>` in `<math><svg>` is a MathML element), and
    `<annotation-xml encoding>` is matched whole and untrimmed.
  - **A `<script>`/`<style>` inside an `<svg>` swallowed the document.** A browser parses
    the content of a foreign one as markup; `html.parser` switched to CDATA regardless,
    and with no `</script>` to return at it lost the rest of the page — *inventing*
    "document has no `<h1>`". Disclosed as an unfixable departure in the previous commit;
    it was neither unfixable nor purely a missed violation. `_Collector` now overrides
    `set_cdata_mode` so a foreign `<script>`/`<style>` stays in markup mode.
  - **A self-closing HTML element closed itself.** The parsing spec acknowledges the flag
    only in foreign content, so `<a href="/x" />Read the docs</a>` is a link *with* that
    text; `html.parser` closed it and the check reported an empty link.
- `15_a11y` flagged three more shapes that axe-core passes: a link named only by a `title`
  attribute (HTML-AAM's last-resort source, now accepted for `link_text` — though still
  **not** for `control_label`, where a tooltip is a poor label); anything marked `hidden`
  or `aria-hidden="true"`, which is out of the accessibility tree entirely and is now
  skipped by `control_label` and `link_text`; and placeholder links and controls inside a
  `<template>`. **`<template>` content is now inert for every rule**, resolving an
  asymmetry (inert for the outline and the title, live for the element rules) that had no
  defence: a template is a stamp whose text, `href` and `alt` arrive at clone time, and
  the source cannot tell an unfinished stamp from a finished element. Each of these
  trades a missed violation for not failing conformant markup, and each is stated in
  SPEC-accessibility.md under "What these rules do not catch".
- `15_a11y`'s remaining recited constants are now **derived from html5lib** like the
  breakout list. The review showed that adding `iframe` to `_VOID_TAGS` passed all 211
  tests — nothing guarded it — and that `_RAW_TEXT_TAGS` was the recited list that was
  actually wrong. The void list gained `basefont`, `bgsound` and `keygen` from the
  derivation; `<col>` is asserted separately because a browser drops it outside a
  `<colgroup>`, where no probe can reach it.
- `15_a11y` suppressed headings inside `<svg>`/`<math>`, which is the **opposite** of what
  a browser does (PR #211 follow-up review). `h1`–`h6` are in the HTML parsing spec's
  foreign-content *breakout* list: a browser hoists `<svg><h1>` out into a genuine
  heading and closes the `<svg>` doing it. The old behaviour both invented a "no `<h1>`"
  finding for a page whose heading sat in an `<svg>` and hid a duplicate `<h1>`. The
  **whole** breakout list is now implemented (`b, big, blockquote, body, br, center,
  code, dd, div, dl, dt, em, embed, h1`–`h6`, `head, hr, i, img, li, listing, menu, meta,
  nobr, ol, p, pre, ruby, s, small, span, strike, strong, sub, sup, table, tt, u, ul,
  var`, plus `font` with `color`/`face`/`size`), along with `<annotation-xml>`'s
  `encoding` condition — and it is **derived from html5lib by a new conformance suite**
  rather than recited, since reciting it is what got it wrong twice. `html5lib` joins the
  `dev` extra as a test oracle only — **pinned** (`==1.1`), because an oracle whose
  version drifts can disagree with itself between a laptop and CI (ADR-0077); the
  harness itself still runs on the stdlib alone.
- `15_a11y` treated an accessible *name* as present when only the **mechanism** was
  present (PR #211 review). `<label><input></label>`, `<label for="q"></label>` and an
  `aria-labelledby` pointing at an empty element all passed while announcing nothing;
  and `<a href="/tw"><svg role="img" aria-label="Twitter"></svg></a>` — the commonest
  icon-link idiom there is — was **flagged**, because only `<img alt>` was credited from
  inside a link. Names are now resolved from content: every element accumulates its
  subtree text plus the `alt`/`aria-label` of any descendant, and `aria-labelledby` is
  resolved (one level) after the parse.
- `15_a11y` let an `<svg><title>` satisfy the **default-on** `page_title` rule, so a page
  with no `<head><title>` at all passed if it contained one titled icon (pre-existing,
  undisclosed). Inside an `<svg>`/`<math>` subtree a familiar tag name is no longer taken
  for an HTML element — `<title>`, `h1`–`h6` and form controls are all namespace-aware,
  and HTML resumes at an integration point such as `<foreignObject>`.
- `15_a11y` read the HTML tree in three ways a browser does not (found in review of
  #159, and applying to the rules shipped in ADR-0045 as well): **duplicate attributes**
  resolved last-wins where the HTML parsing spec keeps the *first*
  (`<html lang="" lang="en">` was read as valid); **`<script>`/`<style>` source** was
  treated as rendered text, so a link containing only code looked named; and
  **`<template>` content** — inert until cloned — could supply a document's `<title>` or
  an enclosing link's name. Each is now resolved the way the DOM would, with tests in
  both directions.
- Citation-resolution gate `26_citations` (ADR-0073) — the deterministic half of the
  largest defect class this repo's review cycle found: **doc overclaim**, 13 findings
  across 11 PRs. Most instances were not judgements but path-resolution facts (a doc
  citing `docs/HANDOFF.md` (lands with #147) on a base that lacks it; `ADR-0057` (lands with #166)
  cited bare where the records stop at 0047; `docs/CHECKS.md` described as being "on this
  base" when it is not). On a branch that changed Markdown under
  `[citations].paths`, every repo-relative path, heading anchor, `ADR-NNNN` reference and
  check id it cites must resolve against **git-tracked** paths on this branch, reported as
  `file:line — citation — does not exist on this branch`. The decision core
  (`src/meta_harness/citations.py`) is pure with an **injected** resolver — no filesystem,
  no network, 100% line+branch coverage, with every real review instance as a fixture.
  Deliberately and permanently out of scope, stated in the SPEC and the check header
  rather than implied away: **external URLs** (needs a network; this runs on every gate)
  and **issue/PR numbers** (GitHub state, off-machine and mutable) — a real `#53`-for-`#82`
  defect stays a review concern, as does whether prose *describes* the code correctly
  (`55_doc_drift`, ADR-0030). A deliberate forward reference is written in one narrow
  recognised form immediately after the citation: `docs/PLUGIN.md` (lands with #166), or
  `docs/PLUGIN.md` (on `feat/claude-plugin`) — `(on line 5)` is not a marker, because a hatch ordinary prose could
  open by accident is a hole. Off unless `[citations].enabled`; `noop` when a branch
  changed no documentation; fails closed on an unreadable config, an unreadable document,
  or a git error inside a repository. Turned on for this repo, which surfaced **24**
  unresolved citations in the existing tree — moved test paths after the `unit/` +
  `integration/` regrouping, two broken relative links in one spec, a planned check id
  whose number was already taken, and several historical paths written in citation shape.
  Every one was fixed in the document; none suppressed. Not added to `adopt.py`'s
  `RECOMMENDED` set: going red on accumulated dead references should be a maintainer's
  choice, not a surprise from `adopt.sh`. Anchor slugs reproduce GitHub's **duplicate
  disambiguation** (two "Setup" sections answer to `#setup` and `#setup-1`), and
  **indented code blocks** are skipped alongside fenced ones — list-aware, because four
  spaces inside a list is continuation, not code. See `docs/specs/SPEC-citations.md`.
- Executor and generator interfaces, spec-first (#143, ADR-0071): `docs/specs/SPEC-executor.md` names the contract for "run this check against this snapshot and return a receipt" — snapshot identity (head + dirty-tree OID + branch), receipt/log/sidecar outputs, eight guarantees (isolation, determinism as equivalence, boundedness, fail-closed `error`/125 receipt on executor failure, no rewriting in transit, same harness, same branch) — and three executors: `local` (today, the reference), `worktree` (a git worktree per run, basis for #144), `sandbox` (contract only, #145 builds). `docs/specs/SPEC-generator.md` names what the gate needs from whatever produces the next change (deliver verdict, request retry with failing ids, bounded retry then a human, identity as self-declared provenance in `intent.generator`) and two generators: `claude-code` (the Stop hook as it is) and `headless` (a scripted, model-free generator for tests and #144). Conformance tests are the definition of done; `local` and the hooked agent stay the only implementations until #201 / #202 land. Substrate (ADR-0069), executor and generator are stated as three separate axes. Docs only — nothing built.
- Multi-harness substrate research and spec (#142, ADR-0069): `docs/research/HARNESS-SUBSTRATES.md` surveys Codex CLI, Gemini CLI, OpenCode, Hermes, Aider, Cline and Roo Code from their public docs (dated, URL per cell, "not documented" never guessed); `docs/specs/SPEC-substrate-adapter.md` writes down the stdin/stdout/exit contract the six hooks already implement, the `adapters/<name>/` wiring-only shape, the capability matrix, degraded modes and the conformance test. Decision: one gate and one hook set with per-substrate wiring adapters; phase-1 target Codex CLI filed as #194. Docs only — nothing built.
- Claude Code plugin distribution: `.claude-plugin/plugin.json`, a self-hosted single-plugin marketplace, `hooks/hooks.json` wiring the six hooks through `${CLAUDE_PLUGIN_ROOT}` (scripts unchanged), project skills exposed by symlink; one-line install from a checkout or the GitHub URL, per-project opt-in untouched. `docs/PLUGIN.md` (ADR-0057, #136).
- PreCompact snapshot + SessionStart(compact|resume) re-injection of the governance brief (last verdict, open obligations, enforcement, identity policy) so gate state survives context compaction; hook-event inventory in `docs/HOOK-EVENTS.md` (ADR-0053, #137).

- `docs/4D-DRY-RUNS.md` (#178): re-authored account of 4D's two dry runs — a research capture that published a false count with every AI-side obligation failing silently, and a shipped PR where they held — with a fifteen-row finding→mechanism table (22_charter, the rewrite-contract receipt, the compaction brief, #174–#177, and six honest "no mechanism; open" rows) and the deliberate exclusions: the 100 wpm transcript-density threshold (a metric target; ratchet alternative described and still declined) and the three-level severity ladder (a dial; replaced by the charter's binary tiers). Linked from `docs/AI-FLUENCY.md` and the SPEC-ai-fluency artifact table. Docs only.
- Session charter gate (ADR-0063, #173): a committed `CHARTER.toml` (goal, stakes `low`|`high` — two opt-in tiers, never a dial — done_when/stop_when/may_not, owner; `high` also requires rollback/reviewer/blast_radius) validated fail-closed by `22_charter` via the pure `meta_harness.charter` (every violation as `field — reason`, hedged `done_when` items rejected, unknown keys/stakes rejected, never `noop`); `[charter]` spine block; a sub-120-byte UserPromptSubmit reminder when enabled and the file is missing; this repo declares its own high-stakes charter. Mechanism re-authored from a CC BY-NC-SA source — no text or code copied.
- PreCompact snapshot + SessionStart(compact|resume) re-injection of the governance brief (last verdict, open obligations, enforcement, identity policy) so gate state survives context compaction; hook-event inventory in `docs/HOOK-EVENTS.md` (ADR-0053, #137).

- Session charter gate (ADR-0063, #173): a committed `CHARTER.toml` (goal, stakes `low`|`high` — two opt-in tiers, never a dial — done_when/stop_when/may_not, owner; `high` also requires rollback/reviewer/blast_radius) validated fail-closed by `22_charter` via the pure `meta_harness.charter` (every violation as `field — reason`, hedged `done_when` items rejected, unknown keys/stakes rejected, never `noop`); `[charter]` spine block; a sub-120-byte UserPromptSubmit reminder when enabled and the file is missing; this repo declares its own high-stakes charter. Mechanism re-authored from a CC BY-NC-SA source — no text or code copied.
- PreCompact snapshot + SessionStart(compact|resume) re-injection of the governance brief (last verdict, open obligations, enforcement, identity policy) so gate state survives context compaction; hook-event inventory in `docs/HOOK-EVENTS.md` (ADR-0053, #137).

- Quote fidelity (ADR-0065, issue #175, sub-issue of #172): `24_quotes` +
  `meta_harness.quotes` verify that every quotation a Markdown document marks with a source
  (`> …` then `— source: docs/research/<slug>/<file>#L<a>-L<b>`, or the
  `<!-- quote: … -->` comment form) is **verbatim** against that saved span — the mechanism
  behind the research skill's fail-closed citation promise. Both sides are normalised the
  same way (curly → straight quotes, whitespace collapsed, one wrapping `"` pair and trailing
  sentence punctuation dropped) and nothing else; outcomes are verbatim / drifted (with a
  unified diff) / missing / out-of-range / orphan marker, each listed as `file:line`. Opt-in
  via `[quotes].enabled` + `paths`; no marked quotation ⇒ `noop`; an unreadable document or
  source fails closed; no network. Registered in `[checks].required` here (currently `noop`:
  no research document has a saved source yet), catalogued in `docs/CHECKS.md`;
  `docs/specs/SPEC-quotes.md`. Unit- (100% line+branch) and integration-tested. The research
  skill's §5 now requires the convention for verbatim quotes in `report.md` (still ≤ 3692 B).
  PR #182 review: matching is line-for-line at word boundaries (a one-line quote inside one
  source line, a multi-line quote over a contiguous run of source lines) — joining the span
  hid a word dropped at a line boundary; and the check resolves symlinks, refusing (never
  reading or printing) any source or walked file whose real path leaves the project.

### Changed
- The research skill's ≤ 3692 B pin test moved from `tests/unit/test_context_budget.py` to
  `tests/integration/test_context_budget_gate.py`: it reads the repo's `.claude/` tree, which
  mutmut's `mutants/` copy lacks, so on the heavy lane it failed the clean-test run and
  `60_mutation` evaluated 0 mutants (failing closed). Same assertion, still on every gate.
- `borromeanrings-research` skill token audit (ADR-0060, issue #47): the skill's static
  cost is measured at 4176 B → 3692 B (`docs/research/RESEARCH-SKILL-TOKEN-AUDIT.md`,
  per-file and per-section), and the dynamic drivers are traced and ranked — working state
  kept in context, whole-page ingestion, unbounded fan-out, re-fetch on verification. The
  protocol now declares an editable budget (rounds, queries/round, sources/round, extracted
  lines/source — knobs the user approves, never gates), writes plan/log/sources/graph/report
  to `docs/research/<slug>/`, extracts passages instead of ingesting pages, caches URLs and
  queries, verifies against the saved passage, delegates fetch+extract to a sub-agent where
  available, reads symbols not files on code hosts, and stops at saturation. Same contract;
  the redundant "Tactics" section is folded into the numbered steps.
  `.borromeanrings-context-baseline` re-seeded downward to 31690 (the ratchet tightens on
  purpose) and a unit test pins the skill at ≤ 3692 B.
- Supply-chain hardening (ADR-0061, #58): two heavy-lane checks and an SBOM entry point,
  all native (stdlib only, no network, no new dependency) and threshold-free.
  **`76_lockfile`** fails when a dependency manifest (`pyproject.toml`, `package.json`)
  changed since the merge-base without the declared `[supply_chain].lockfile` changing —
  working-tree and untracked changes count; no lockfile declared ⇒ `noop`, declared-but-
  missing / non-git / git error ⇒ fail closed. **`78_pins`** requires every
  `[project].dependencies` requirement (optional groups too with `pin_optional = true`)
  to carry an upper bound or exact pin (`==`, `~=`, `<`; a direct URL needs a commit hash
  or `sha256=`), naming each offending line verbatim; no requirements ⇒ `noop`; `dynamic`
  dependencies or malformed TOML ⇒ fail. **`sbom.sh`** emits a deterministic CycloneDX 1.5
  JSON of the declared closure via `tomllib` + `importlib.metadata` (name/version/purl +
  dependency graph; unresolved requirements listed, never dropped) — an inventory that
  states it is *not* signed or attested. Applied here: `lockfile = ""` (this repo has none
  and nothing regenerates one — honest `noop`), `pin_optional = true`, and every dev
  requirement bounded above at its next major. Dependabot, SLSA provenance/signing and
  SHA-pinned Actions need CI or a remote service and are recorded in the ADR as maintainer
  decisions with the exact config. Unit (100 % line + branch on both modules) + integration
  (real `verify.sh --heavy` on fixture repos: stale lock ⇒ red; both changed ⇒ green;
  undeclared ⇒ `noop`; missing lock and broken git index ⇒ fail closed).
- Context-budget ratchet (ADR-0055, issue #135): `19_context_budget` +
  `meta_harness.context_budget` measure what borromeanRings **itself** puts into the
  agent's context — the prompt-rewrite directive, `CLAUDE.md`/`AGENTS.md`, every installed
  `SKILL.md`, and the message templates in `.claude/hooks/*.sh` — as bytes and approximate
  tokens (bytes/4, no tokenizer dependency), and **ratchet the total** against
  `.borromeanrings-context-baseline`: above the baseline fails naming both numbers, at or
  below passes with the per-source rows in the log, nothing measurable ⇒ `noop`, an
  unreadable baseline fails closed. Non-regression only, no absolute cap. Registered in
  `[checks].required`, in `adopt.py` `RECOMMENDED`/`RATCHET_BASELINES` (seeded even when
  the project declares no package), catalogued in `docs/CHECKS.md`; borromeanRings's own
  baseline seeded at 32174 B (~8K tokens). Unit- (100% line+branch) and integration-tested
  (pass / regression / noop / unseeded / unreadable).
### Fixed
- `15_a11y` reported `pass` for a project with no HTML at all — a hollow green (#154).
  Under ADR-0049 a check that inspected nothing must say so: it now exits 3 ⇒ `noop`,
  the log names what was searched (git-tracked `*.html/*.htm/*.xhtml`, minus
  `[a11y].exclude`) and where, and the gate output counts it under `inspected NOTHING`.
  Clean HTML ⇒ `pass`, violations ⇒ `fail`, unchanged. The HTML walk now mirrors
  `01_source_coherence`: a `git ls-files` failure inside a repo **fails closed** (never a
  `noop`), and a non-git project falls back to a filesystem walk (honouring `exclude`) and
  evaluates what it finds. Locked down by an integration suite
  (`tests/integration/test_a11y_gate.py`) driving `verify.sh` on every fixture.

### Added
- Context-budget ratchet (ADR-0055, issue #135): `19_context_budget` +
  `meta_harness.context_budget` measure what borromeanRings **itself** puts into the
  agent's context — the prompt-rewrite directive, `CLAUDE.md`/`AGENTS.md`, every installed
  `SKILL.md`, and the message templates in `.claude/hooks/*.sh` — as bytes and approximate
  tokens (bytes/4, no tokenizer dependency), and **ratchet the total** against
  `.borromeanrings-context-baseline`: above the baseline fails naming both numbers, at or
  below passes with the per-source rows in the log, nothing measurable ⇒ `noop`, an
  unreadable baseline fails closed. Non-regression only, no absolute cap. Registered in
  `[checks].required`, in `adopt.py` `RECOMMENDED`/`RATCHET_BASELINES` (seeded even when
  the project declares no package), catalogued in `docs/CHECKS.md`; borromeanRings's own
  baseline seeded at 32174 B (~8K tokens). Unit- (100% line+branch) and integration-tested
  (pass / regression / noop / unseeded / unreadable).
- `18_api_contracts` + `[api_contracts]`: a project's own API-usage rules (banned / forbidden_in / must_check / required_arg / paired / requires_before) enforced as deterministic AST checks, `noop` when they match nothing, with a PostToolUse preventive layer and a cited `python-asyncio` rule pack (ADR-0054, #130).

### Added
- `70_pip_audit` and `72_licenses` judge the project's own dependency closure instead of whatever is installed on the machine (#228). Both read the *installed environment*, which equals the project's dependencies only on a clean CI runner; on a developer machine the heavy lane reported 43 CVE'd and 14 GPL distributions — `torch`, `notebook`, `semgrep`, `pynput` — none of them dependencies of anything being gated. That contradicted the claim `verify.yml` makes in its own header (the same `verify.sh`, author- and environment-agnostic), and the remedy each check printed was actionable and **wrong**: following it would write a permanent exception into the project's config for a package it does not depend on. New `meta_harness.closure` resolves the declared set — including `[build-system].requires` — plus its transitive reach from installed metadata (pure stdlib). Every ambiguity resolves toward *including*: platform markers are not evaluated, an extra the project itself asked for is followed (`pip-audit[doc]` means `pdoc` is in scope), and a marker satisfiable without its extra is followed too; only a requirement guarded solely by an extra nobody requested is skipped, because following all of them turns the graph into the index (624 distributions against 79 for the real closure); both checks now report the scope size and **fail closed** if the closure cannot be determined, rather than silently widening back to everything.
- `12_secrets` detects the AWS **secret** access key, (#230). Found by running the harness end-to-end against a fresh external project: a planted credential passed, because the pattern set covered only the `AKIA` key *ID* — the public half of the pair. The new pattern matches by **name plus shape** — an identifier saying `aws…secret…` assigned a 40-character base64 value — so the no-entropy-heuristics rule is untouched: a bare 40-char string is still not a finding. Quotes around the value are optional, because the commonest home for this credential — `~/.aws/credentials` — is INI and has none, as do `.env` files, Dockerfile `ENV` and `export`; a terminator is required instead, so a longer base64 run never matches its first 40 characters. `SPEC-secrets.md`'s table is now the exhaustive covered set, enforced by a test that fails if a pattern ships without a planted example. The same end-to-end run showed `init.sh` does not put `12_secrets` in a new project's required set either; that is #236, because the check fails closed without a git repository and `init.sh` must start green — a genuine design conflict rather than a patch.
- Adoption now gives a governed project the `.gitignore` entries borromeanRings always assumed it had (#219). Without them the gate's own output is untracked-but-not-ignored, so `git add -A` puts the receipt logs into the index that `12_secrets` reads — and a check log quoting a secret-shaped line makes the secret gate fail **on generated files, still failing after the offending source is deleted**, telling the user to rotate a secret that no longer exists. `init.sh` and `adopt.sh` now ensure `.meta-harness/` and `.coverage` are ignored: created when there is no `.gitignore`, appended (and announced on stdout) when there is, and left alone when already present in any spelling git honours. `--no-gitignore` opts out, because "deliberately absent" cannot be inferred from an absence.
- The Stop hook no longer stands down because the governed project said so (#222). Its no-op-skip record moved out of the tree to `${XDG_STATE_HOME:-$HOME/.local/state}/borromeanrings/<digest>/last_green_state`, beside the retry count — an unkeyed hash whose function ships in this repository is not evidence when the agent it bounds can write it. An in-tree record from an older version is never read and is deleted on the next green. A claim marker dated in the future is no longer treated as a fresh claim: `now - mtime` went negative and compared as fresh forever, so one `touch -d tomorrow` silently stopped the gate running at all. Location arithmetic extracted to `meta_harness.state_home`. Each of the three routes has a test that first proves the forgery is live and then proves the gate ran anyway (ADR-0082).
### Changed
- What borromeanRings injects into an agent's context is 771 bytes lighter: the prompt-rewrite directive tightened from 862 to 690 bytes with every obligation intact (asserted by a new test that pins the duties rather than the prose), and the Stop hook's three verdict messages trimmed from 435 to 336. Measured against the `19_context_budget` baseline (32,174 bytes): the tree now measures 32,123, i.e. under it (#135).

### Added
- README states the trust boundary in plain words: borromeanRings resists accident, mistake and naive forgery, and does **not** resist an agent that deliberately forges its verdict, because the gate runs the governed project's own test code as your user. The distinction is confinement, not good intentions; a real bound needs isolated execution (#144/#145). The work-in-progress notice now names the specific issues holding it in place (#230, #228, #229) instead of gesturing at "known gaps".
- Rewrite contract (ADR-0059, #81): the prompt-rewrite directive is now *verified*, not just injected. `meta_harness.rewrite_contract` reads the tail of the session transcript the Stop hook receives (`transcript_path`), finds the reply to the last human prompt and decides deterministically — no model call — whether it opened with `Reading this as:` (trivial yes/no/continue prompts exempt). `stop_gate.sh` appends the verdict with its evidence to `.meta-harness/rewrite_contract.jsonl` (append-only; `unknown` when the transcript is missing/malformed; never blocks), and `status.sh` shows the tally (`Rewrite: contract honoured N of M in this project`). Record, don't nag: a ratchet check is the documented next step. Unit + stdin-protocol integration tested.
- Claude Code plugin distribution: `.claude-plugin/plugin.json`, a self-hosted single-plugin marketplace, `hooks/hooks.json` wiring the six hooks through `${CLAUDE_PLUGIN_ROOT}` (scripts unchanged), project skills exposed by symlink; one-line install from a checkout or the GitHub URL, per-project opt-in untouched. `docs/PLUGIN.md` (ADR-0057, #136).
- PreCompact snapshot + SessionStart(compact|resume) re-injection of the governance brief (last verdict, open obligations, enforcement, identity policy) so gate state survives context compaction; hook-event inventory in `docs/HOOK-EVENTS.md` (ADR-0053, #137).

- PreCompact snapshot + SessionStart(compact|resume) re-injection of the governance brief (last verdict, open obligations, enforcement, identity policy) so gate state survives context compaction; hook-event inventory in `docs/HOOK-EVENTS.md` (ADR-0053, #137).

- Fast (interactive) lane: `verify.sh --fast` (closes #226). The Stop hook ran the full
  required set on every turn — 445 s, of which `40_test` was 404 s (91%) — so an agent
  waited over seven minutes to report finished, and three retries made the worst case ~22
  minutes per session. `--fast` exports `BORROMEANRINGS_LANE=fast` and runs the same check
  set; only `40_test` narrows, to the paths a project declares in the new `[test].fast_paths`
  (`Config.test_fast_paths`), without coverage. This repo declares `["tests/unit"]`: the Stop
  gate is now ~12 s. Declaring nothing means no fast lane and no behaviour change; `--heavy`
  always wins over `--fast`; CI still runs everything. A fast-lane pass is labelled as partial
  in the verdict line, the check row, the receipt (`lane`, `fast_paths`, no coverage number)
  and `last_verdict.json`, so it can never be read as a full pass. See ADR-0081.

### Fixed
- Git-identity guard hardened against per-command overrides and exotic invocations
  (closes #54). Two independent holes, both preventive-layer only (check `06_git_identity`
  remained the backstop). **(1) Overrides were invisible.** The guard compared the repo's
  *configured* identity, but git accepts an identity per invocation — `--author=`,
  `-c user.email=`, and the `GIT_AUTHOR_*`/`GIT_COMMITTER_*` environment variables — none
  of which config-comparison can see, so a correct repo could still produce a
  wrong-authored commit. **(2) Detection was a substring match.** Keying on the literal
  `"git commit"` misses every spelling that puts something between the two words
  (`git -c … commit`, `git -C dir commit`, `VAR=value git commit`) — so those invocations
  skipped the identity *and* protected-branch guards entirely. New `git_subcommand()`
  parses the real subcommand, stepping over leading environment assignments and git's
  global options; `command_override_violation()` compares any declared override against
  the required identity, allows one that states the correct identity (being explicit is
  not evasion), and refuses an override it cannot parse rather than failing open. Both
  guards now key off the parsed subcommand. Scoped so it only ever fires on a real
  `git commit`/`push`: a script or heredoc that merely mentions git is not a commit.
  Verified end to end against all four evasion paths through the hook's own stdin
  protocol, with negative controls.
  Those hook tests now run against a throwaway governed project (configured identity =
  declared identity, HEAD on a work branch) instead of the harness checkout: CI's checkout
  has no `user.name`/`user.email`, so the configured-identity rule denied every commit
  there — failing the negative control and letting the override test pass for the wrong
  reason. The override test now also asserts the denial came from the override rule.
- `merge.sh` now merges the **governed project**, not borromeanRings itself (closes #121).
  It unconditionally `cd`-ed into `BORROMEANRINGS_HOME`, so invoking it from a governed
  project checked *borromeanRings's* working tree for dirtiness and would have merged
  *borromeanRings's* branches — the wrong repository. Found in the field: an untracked file
  in the harness blocked a clean merge in another repo. `verify.sh` has always honoured
  `BORROMEANRINGS_PROJECT`/`CLAUDE_PROJECT_DIR`; `merge.sh` now resolves the same two roots
  (ADR-0013) and runs every git/`gh` call, the gate, the policy check and the audit receipt
  against `PROJECT_ROOT`, while loading harness code from `BORROMEANRINGS_HOME`. It also
  refuses outright when the target has no `borromeanrings.toml`. Regression-tested against
  a real fixture repo with a local bare origin; both tests fail against the pre-fix script
  with the exact symptom from the report.
### Security
- Gate no longer self-certifies via a planted stdlib name (ADR-0080, #222). `verify.sh`
  ran its trusted Python (verdict aggregation, language detect) and `checks/_lib.sh` ran
  `emit_receipt` / `borromeanrings_project_cfg` from `PROJECT_ROOT` — putting the
  governed project first on `sys.path`, so a `json.py` committed at the repo root could
  shadow stdlib and make `bash verify.sh` (what CI runs) print `RESULT: PASS` and exit 0
  on a failing tree, forging the required `gate` check. New `checks/_py.sh` defines
  `borromeanrings_py` (runs Python from `/` with `PYTHONPATH` at borromeanRings' own
  `src`, plus `PYTHONNOUSERSITE=1` so a user-site `usercustomize.py` cannot forge the
  verdict either — #224 review; mirrors #221's hook helper); the four named calls plus
  every verdict-deciding analysis heredoc (`05`–`15`, `32`–`35`, `45`, `55`, `56`, `74`)
  and `00_build`'s stdlib `compileall` step now route through it. Deliberately not
  `python3 -P`/`-I` (3.11-only / drops `PYTHONPATH`). Tool runs that execute project code
  by design (`pytest`, `mypy`, `mutmut`, `pip-audit`, `pip-licenses`, and `00_build`'s
  `import <package>` half) are left as-is — already untrusted per #218, blocked on M7.
  This closes the project-directory shadow completely and the user-site vector; it is not
  full interpreter isolation. The Stop-hook half of #222 (forged `last_green_state`, hook
  markers) also remains, on M7.
### Fixed
- The Stop hook's retry count could be reset by deleting a file (#218, ADR-0079). It lived
  in `.meta-harness/stop_attempts/`, inside the project, and a missing file read as `0`. It
  now lives under `${XDG_STATE_HOME:-$HOME/.local/state}/borromeanrings/<project-digest>/`,
  keyed by the project's resolved path, via the new `meta_harness.retry_state` (pure, 100%
  unit-tested). This resists accident and a naive reset: tidying `.meta-harness/`, deleting
  the counter or writing `0` into it no longer buys attempts. It is **not** a bound against
  intent: the gate runs the project's own tests as the user, so a `conftest.py` can still
  delete the count, as can any same-user process; only an isolated test run closes that.
  Keyless. Fails closed: a broken or unusable state directory, one that resolves inside the
  project, or a symlink on the old in-tree path now escalates to the human instead of
  silently counting from zero. The old in-tree count is carried over with `max()`, walked
  without following symlinks, then removed. The headless driver from #217 must adopt the
  same module when it lands.
- Hooks no longer import modules from the governed project. They run from the project
  directory, where `python3 -c` put a planted `json.py` ahead of the standard library; the
  Stop hook's payload parse imported one and got a fresh session id on every Stop. Every
  hook now starts Python through `borromeanrings_py` (`.claude/hooks/_lib.sh`), which runs
  it from `/`. Not `-P`, which needs Python 3.11 against `requires-python = ">=3.10"`.
### Deprecated
- The pre-rename config file name `borromeo.toml` (issue #62). It still loads —
  `meta_harness.spine.resolve_config_path` falls back to it when `borromeanrings.toml`
  is absent and prints a `FutureWarning` to stderr (once per process per legacy file;
  shown by Python's default filters, which a `DeprecationWarning` is not). Visible from
  `verify.sh` (its own notice on every run), `status.sh`, `ledger.sh`, the Stop and
  UserPromptSubmit hooks; the PreToolUse branch guard swallows stderr by design and stays
  silent but still governs — so no already-governed project falls out of governance. Migrate with `git mv borromeo.toml borromeanrings.toml`.
  The `meta_harness` package and the `.meta-harness/` evidence directory are deliberately
  NOT renamed (receipts, baselines, mutmut config and import paths depend on them).

### Added
- Prior-art gate (ADR-0051, closes #131): `17_prior_art` — on a feature branch, a change
  that **adds public surface** must also add or modify a survey record under
  `docs/surveys/` saying what already existed (in the repo, a dependency, the ecosystem)
  and why building was still right. The `13_adr` pattern applied to reuse; the practice the
  maintainer most often re-stated to agents by hand, now enforced. New surface is computed
  by diffing `api_diff.public_api` at the merge-base vs HEAD; no new surface ⇒ `noop`.
  Ships with its own survey (`docs/surveys/0001-prior-art-gate.md`) and a `TEMPLATE.md`.
  Two honest limits from the research (`docs/research/AGENT-TOOLING-SURVEY.md`): the
  ecosystem "is there a library?" half is **advisory only** — no key-free package API
  supports free-text search, so a gate could not answer its own question; and clone
  detectors catch copy-paste, not reinvention (renamed clones evade them), so jscpd is
  deferred and will be described as copy-paste detection. Reimplementation-of-a-builtin
  IS deterministic: Ruff's `PIE807`/`PERF401-403`/`PLR0402` are now enabled — selected
  **individually**, because the `PIE`/`PERF`/`PL` groups measured 50 findings on this
  tree, 37 magic-value nits and 3 `too-many-arguments` (a numeric threshold, the exact
  thing this project rejects). Their one finding was fixed, not suppressed.
- `describe.sh` (`--json`, `--readme`) + `04_self_description`: the capability report is generated from the check registry, the README block is regenerated in place, and a README that states a check/gate count must match the registry (ADR-0052, #132).
- **Verification ladder, tier 1 — property-based tests (ADR-0074, #140).** The gate can now
  run a project's *universal* statements, not just its examples. `27_properties` runs the
  suite declared at `[verification].properties` (pytest + Hypothesis) under a **binary,
  threshold-free** rule: nothing declared ⇒ `noop` (rule off) · **declared but empty ⇒
  `fail`** · runner not importable ⇒ `noop` **naming it** (borromeanRings never installs a
  project's toolchain) · a falsified property ⇒ `fail`. It **never counts properties, never
  ratchets on how many exist, and never targets a number of examples** — ADR-0022 chose a
  mutation ratchet over a coverage percentage for exactly this reason, and "number of
  properties" is the same trap one rung up; the file probe is `find … -print -quit`, so the
  check is structurally unable to see a count. Declared-but-empty fails because
  `[verification]` has **no defaults**: writing the key is an affirmative claim, and a claim
  with no evidence behind it is the vacuity ADR-0049 exists to catch (`pass` would be that
  defect verbatim; `noop` would make the declaration free). An **unknown key under
  `[verification]` fails config loading closed** (`spine.VERIFICATION_KEYS`), so a typo
  (`propertys = …`) can't silently switch a verification claim off. Order of evaluation is
  part of the contract: everything decidable *without* a runner is decided first, so a
  missing tool can never mask a broken claim. Unit-tested on the spine (including the
  fail-closed typo) + eight integration cases driving the real `verify.sh`, each shown to
  fail under a deliberate sabotage of the branch it covers. **Tiers 2 (SMT) and 3 (formal
  proof) ship as specification only** — `docs/specs/SPEC-verification-ladder.md` covers all
  three with their honest limits (an SMT proof covers the model you wrote, not the code you
  shipped; a proof of the wrong theorem is worth nothing, so the *statement* is the reviewed
  artifact) — with acceptance criteria filed as #204 and #205. z3 and CrossHair are not on
  this machine and nothing was installed to change that. borromeanRings declares the check
  and **no** property directory, so its own gate honestly reports `noop — rule off`; no
  suite was invented to make the check look busy. `adopt.py`'s `RECOMMENDED` set is
  unchanged: adopting a verification tier is a project's decision, not a migration's.
- Mutation-guard proof + evaluated count on the gate row (issue #187). `60_mutation` has
  failed closed on zero evaluated mutants since ADR-0022; it is now pinned by
  `tests/integration/test_mutation_guard.py`, which plants a unit test that reads a path
  outside `src/`/`tests/` (the #160/#168 shape — absent from mutmut's copied sandbox) and
  asserts `60_mutation` is `fail` with "MUTATION CHECK DID NOT RUN", then removes it and
  asserts `pass` with a real count. Checks may now write a one-line `summary` field into
  their receipt (`meta_harness.mutation.summary_line` for 60_mutation); the gate prints it
  beside the status (`meta_harness.verdict.status_label`, validated + bounded) so the row
  reads `PASS (evaluated N, score S)` / `FAIL (evaluated 0)` — a score alone is unreadable.
- `60_mutation` clears the stale `mutants/` copy before each run. mutmut 3.6's
  `copy_src_dir` skips any target that already exists and never deletes, so a test removed
  from `tests/` lingered in the sandbox and kept the lane red — the root cause of the
  "`rm -rf mutants/` before a heavy run" rule. Bounded to `$PROJECT_ROOT/mutants`; refuses
  a path that resolves outside the project. The integration test's second run now passes
  without cleaning up itself, which is the regression proof.
- Provenance gate `25_provenance` (ADR-0070, `docs/specs/SPEC-provenance.md`, closes #189):
  re-authored text must not reproduce its declared source. The ADR-0020 rule for the 4D
  merge (#172) was enforced by review alone, and review found copied or clause-for-clause
  passages in two of five ports after the builder had reported them clean; the reviewer's
  shingle sweep lived only in a scratchpad. Now a check: every file changed since the
  merge-base under `[provenance].paths` is split into **6-word shingles** (lowercased,
  Unicode punctuation stripped, whitespace collapsed, code fences skipped) and compared
  with every file under `[provenance].sources` (config, then the colon-separated
  `BORROMEANRINGS_PROVENANCE_SOURCES` env var — so a machine-local sibling path never
  lands in the config). **Binary, no score**: any overlap not covered by
  `[provenance].allow` fails, printed as `changed:line ↔ source:line — "<shingle>"`;
  the gate never guesses which overlaps are "generic" — the human allowlists them with a
  reason, in a reviewable diff. No `[provenance]` ⇒ off (`noop`); no sources or nothing
  changed under `paths` ⇒ `noop`; absent/unreadable/empty source, git error inside a
  repo, or an allow entry that normalizes to nothing ⇒ **fail closed**. Self-quotes
  (overlap among this repo's own files, or a source inside the project) are never
  findings. Pure core `meta_harness.provenance` (100% line+branch, exact-value tests);
  end-to-end tests on a fixture repo + fixture source cover off / noop / pass / fail with
  locations / allowlisted / unreadable source / env-var. This repo declares
  `sources = []` (honest `noop` until the maintainer sets the env var) and registers the
  check in `[checks].required`; `adopt.sh`'s RECOMMENDED set is unchanged (opt-in).
- Predicate lint (`23_predicates`, `meta_harness.predicates`, ADR-0064, #174): the
  checkable statements this repo's documents make — SPEC `Contract`/`Guarantees`/
  `Acceptance` bullets, ADR `Consequences` bullets phrased must/never/shall, issue-form
  task items — are now read by a gate. Any **hedge word** ("appropriately", "as needed",
  "reasonable"; a fixed list organised by ISO/IEC/IEEE 29148 §5.2.7's ambiguity categories,
  extended per project via `[predicates].hedges`) fails the gate as
  `file:line — predicate — hedge`, and any SPEC that names **no** shipped check id, existing
  test file or issue is reported as an **orphan**. Only resolvable references count, so the
  orphan rule cannot be vacuous — a mutation-driven test replaces the detector with one that
  finds nothing and asserts the suite notices (the defect 4D's validator shipped). Opt-in via
  `[predicates].enabled`; `noop` when off or when nothing was found; fails closed on an
  unreadable file. Dogfooded: five hedged predicates in this repo's SPECs/ADRs were rewritten
  as yes/no statements and five orphan SPECs now name their unit-test file.
- Governance matrices #2–#6 documented (#138) — `docs/matrices/` holds one row-by-row
  document each for **security & compliance**, **delivery / DORA**, **operational / SRE**,
  **data / ML** and **product / UX**, plus an index of the shared conventions. Every row is a
  binary check or a threshold-free ratchet (never a percentage target), names the check that
  enforces it today — verified against the script, e.g. `14_container` rule `healthcheck`,
  `15_a11y` rule `html_lang`, `74_secret_history` — or the gap issue that would close it, is
  tagged deterministic-now / telemetry-gated / archetype-blocked (the last wired to #79), and
  cites a checkable source (OWASP ASVS 4.0.3, NIST SSDF, SLSA, OpenSSF Scorecard, DORA /
  *Accelerate*, Google SRE Book and Workbook, CIS Docker Benchmark, ML Test Score, WCAG 2.2,
  Nielsen heuristics). `docs/ENFORCEMENT-COVERAGE.md` §6 now links each matrix and reports it
  as `documented` (the `archetype` status word is retired: archetype-blocked is a row
  property, not a matrix status).
- Tests for the portability entry points (closes #53). `init.sh`, `install-global.sh` and
  `merge.sh` are the code that reaches *outside* this repository — into a governed
  project's config, into a user's global Claude settings, into another repo's git history
  — and none of it was tested. `init.sh` also now substitutes the `__BORROMEANRINGS_HOME__` placeholder in copied
  skills, which `install-global.sh` always did and it did not — a skill still carrying
  it tells the agent to run a path that does not exist. `init.sh`: the written config
  loads through the spine, all
  four hooks are wired at this borromeanRings, an existing config is not clobbered, skills
  are installed, and **the gate then runs green in the freshly-initialised project** (a
  starter config that cannot pass its own gate would make every adoption start red).
  `install-global.sh`: hooks are installed, unrelated settings survive, a *foreign* hook on
  the same event is kept, re-running does not duplicate entries, and the
  `__BORROMEANRINGS_HOME__` placeholder is substituted. Every one of those redirects the
  script with `CLAUDE_CONFIG_DIR` — a test that wrote to the real `~/.claude` would
  silently re-enable global governance on the developer's machine. `merge.sh`: refuses a
  dirty tree, refuses when already on the base branch, and refuses when the gate fails,
  asserting in each case that nothing was merged.

### Fixed
- Git-identity guard hardened against per-command overrides and exotic invocations
  (closes #54). Two independent holes, both preventive-layer only (check `06_git_identity`
  remained the backstop). **(1) Overrides were invisible.** The guard compared the repo's
  *configured* identity, but git accepts an identity per invocation — `--author=`,
  `-c user.email=`, and the `GIT_AUTHOR_*`/`GIT_COMMITTER_*` environment variables — none
  of which config-comparison can see, so a correct repo could still produce a
  wrong-authored commit. **(2) Detection was a substring match.** Keying on the literal
  `"git commit"` misses every spelling that puts something between the two words
  (`git -c … commit`, `git -C dir commit`, `VAR=value git commit`) — so those invocations
  skipped the identity *and* protected-branch guards entirely. New `git_subcommand()`
  parses the real subcommand, stepping over leading environment assignments and git's
  global options; `command_override_violation()` compares any declared override against
  the required identity, allows one that states the correct identity (being explicit is
  not evasion), and refuses an override it cannot parse rather than failing open. Both
  guards now key off the parsed subcommand. Scoped so it only ever fires on a real
  `git commit`/`push`: a script or heredoc that merely mentions git is not a commit.
  Verified end to end against all four evasion paths through the hook's own stdin
  protocol, with negative controls.
  Those hook tests now run against a throwaway governed project (configured identity =
  declared identity, HEAD on a work branch) instead of the harness checkout: CI's checkout
  has no `user.name`/`user.email`, so the configured-identity rule denied every commit
  there — failing the negative control and letting the override test pass for the wrong
  reason. The override test now also asserts the denial came from the override rule.
- `merge.sh` now merges the **governed project**, not borromeanRings itself (closes #121).
  It unconditionally `cd`-ed into `BORROMEANRINGS_HOME`, so invoking it from a governed
  project checked *borromeanRings's* working tree for dirtiness and would have merged
  *borromeanRings's* branches — the wrong repository. Found in the field: an untracked file
  in the harness blocked a clean merge in another repo. `verify.sh` has always honoured
  `BORROMEANRINGS_PROJECT`/`CLAUDE_PROJECT_DIR`; `merge.sh` now resolves the same two roots
  (ADR-0013) and runs every git/`gh` call, the gate, the policy check and the audit receipt
  against `PROJECT_ROOT`, while loading harness code from `BORROMEANRINGS_HOME`. It also
  refuses outright when the target has no `borromeanrings.toml`. Regression-tested against
  a real fixture repo with a local bare origin; both tests fail against the pre-fix script
  with the exact symptom from the report.

### Added
- Shell lint gate (ADR-0050, closes #52): `16_shellcheck` lints the project's own shell,
  **fail-closed on any finding at any severity**. borromeanRings is 43 scripts / ~2.8k lines
  of bash and that bash IS the trust root — the gate itself, every check, the four Claude
  hooks — yet it was the one part of the codebase nobody linted while the Python beside it
  faced twenty checks. Running it found five issues, **two of them real defects**:
  `scripts/critic-judge.sh` piped its prompt into `python3 - <<'PY'`, where the heredoc
  overrides the pipe, so `sys.stdin.read()` returned `""` and the API-key judge path was
  sending an **empty prompt** to the model (SC2259); and `pre_bash_guard.sh` carried a dead
  `case` alternative in the dangerous-command guard, unreachable because an earlier pattern
  subsumed it (SC2221/SC2222). Both fixed, plus an unchecked `cd` in `merge.sh` (SC2164) and
  a missing shell directive. Design notes: sources are **resolved, not suppressed** — `-x`
  with `[shell].source_paths` (`SCRIPTDIR`) clears all 33 SC1091 notes that a blanket
  `-e SC1091` would have muted along with real unreadable-source bugs; the file list is
  git-tracked shell (an untracked scratch script never fails a gate) with a filesystem-walk
  fallback; no shell ⇒ `noop`, not a hollow pass; and **no `xargs`**, which would split a
  long list across invocations and report only the last exit code. `shellcheck-py` is added
  to the dev extras so CI needs no apt step. A missing shellcheck is `error`, never a skip.
- Honest no-op status + source-coherence guard + self-status (ADR-0049) — the fix for a
  **hollow green**. A governed project reported `ok: true`, 12/12, while seven of those
  checks had inspected *nothing*: `src_dir` pointed at a missing `src/` and the real code
  lived in `tools/`. Root cause: `_lib.sh` derived status from the exit code alone, so "I
  inspected nothing" and "I inspected everything and it's clean" were indistinguishable
  (`50_security` was worst — `bandit -r src` on a missing dir exits 0 with *empty* output).
  Four parts: (1) a fourth receipt status **`noop`** (`emit_noop`, plus exit code 3 as the
  heredoc→bash signal), surfaced in the gate output (`inspected NOTHING: N of M`), the
  persisted verdict and its history; (2) **fail-closed by allowlist** —
  `verdict.NON_FAILING_STATUSES` / `is_failing()` replace the old `status != "pass"`
  negation, so an unknown/typo'd/forged status still fails (regression-tested), and
  `status_assess` no longer mislabels a `noop` check as *failed*; (3) **`01_source_coherence`**,
  which fails the gate when a declared source path resolves to nothing *while tracked
  source exists elsewhere*, naming where the code actually is — genuine greenfield stays
  green as `noop`, and untracked files never fail a gate; (4) **self-status**: `status.sh`
  now reports **this project** by default (governed? enforcement AUTO/PARTIAL/MANUAL? last
  verdict? how many checks were hollow?), with the `$HOME` portfolio roster demoted to
  opt-in `--all`, plus a `borromeanrings-status` skill so any session can be asked "check
  my borromeanRings status". Enforcement is detected by hook *script name*, not path, so a
  self-governing repo isn't misreported as unenforced. Unit- + integration-tested
  (misconfigured fixture gates red; greenfield gates green-as-noop; correctly-configured
  passes for the right reason). Remaining vacuity in `05_hygiene`/`07_layout`/`09_commits`
  is documented as deferred in the ADR — the hollow count is a floor, not a total.
- Harness versioning + per-run version stamping (ADR-0048): a top-level `VERSION` file
  (`0.1.0`) as the human-declared release marker, and every gate run now records **which
  borromeanRings governed it**. `verify.sh` computes `HARNESS_VERSION` from
  `git describe --tags --always --dirty` on `BORROMEANRINGS_HOME` (honest about
  dirty/ahead-of-tag state), falling back to `VERSION`. It's printed in the gate output
  (`harness-version:`), carried on the persisted `Verdict` (new `harness_version` field →
  `last_verdict.json` + `verdict_history.jsonl`, back-compatible default `""`), and written
  as `harness_version.txt` into the receipt bundle. Answers "is it stable / which version
  verified this project?". Surfacing it as a `status.sh` column is a deferred follow-up.
- Checks catalog (`docs/CHECKS.md`): the single reference for **every** check (all 29 across
- Checks catalog (`docs/CHECKS.md`): the single reference for **every** check (all 27 across
  the shared / Python / heavy-CI lanes) — what each enforces, its `borromeanrings.toml`
  config keys, its lane, whether it's a threshold-free ratchet, and its ADR. Plus how to
  enable a check (`init.sh`/`adopt.sh`/manual) and how to opt a project into *automatic*
  governance (the per-project hooks model). Closes the "how do I know how to use all its
  features" gap.
- `docs/RENAME.md` (issue #62): the borromeo -> borromeanRings rename tail — what was
  renamed, what deliberately was not and why, and the exact commands to fix a local
  clone's remote URL, re-run `install-global.sh`, and refresh the GitHub label
  descriptions that still say "borromeo".
### Changed
- Enhancement catalog health-audited (#133): entries carry `maintained_as_of` / `needs_api_key` / `applies_to`, `recommend()` filters by substrate, RouteLLM (dead) and OmniRoute (search-query URL) removed, Serena / Repomix / ast-grep / pyright-lsp added.

### Added
- Issue forms, PR template, and label scheme (closes #61): YAML issue forms for bug
  report (repro, expected/actual, gate output + receipt path, `harness-version`),
  feature request (user story, acceptance checkboxes, quality attributes, the check
  that would enforce it, ADR/milestone fit) and research/spike (question, sources,
  deliverable under `docs/research/`); blank issues disabled, vulnerabilities routed to
  the private advisory. `PULL_REQUEST_TEMPLATE.md` now mirrors the real definition of
  done (fast gate, `--heavy` with `60_mutation`/`74_secret_history`, sub-agent review
  on the PR, ADR/CHANGELOG/spec when applicable, no new CI/packaging, subject ≤ 72).
  `docs/LABELS.md` documents the label + milestone vocabulary reconciled with the
  labels that exist; `scripts/labels.sh` (idempotent, `--dry-run`, shellcheck-clean)
  applies it — run by a human on purpose, never by a hook.
- Platform self-assessment (`docs/SELF-ASSESSMENT.md`, issue #51): how the gate, receipts,
  hooks, ratchets and lanes work with every claim cited; the defect-class table built from
  this cycle's 25 sub-agent PR reviews (#148–#185) plus the full-source licence sweep, and
  whether a mechanism or only review catches each class; gaps ranked fail-closed → vacuous evidence → matrix coverage →
  ergonomics; ten prioritised improvements with tracking issues (four newly filed:
  #186 fail-closed enumeration, #187 mutation-lane vacuity guard, #188 citation check,
  #189 license shingle check); the constraints honoured and where each is enforced.
- Toolchain pinning (ADR-0077): `[project.optional-dependencies].dev` pins with `==`
  every package that decides a verdict — the check tools, plus `coverage` (measures the
  ratchet) and `libcst` (generates mutmut's mutants). The rest of the closure stays free
  to resolve current, because pinning it froze four packages at versions with known CVEs
  and `70_pip_audit` correctly went red. `meta_harness.toolchain` + integration tests fail
  closed when the gate runs a version other than the pinned one, when a version cannot be
  read, when a `dev` requirement is not exact, or when a tool reachable from `checks/**.sh`
  has no pin. Each tool is observed through **the argv its check uses** (`ruff` from
  `PATH`, `pytest` via `python3 -m`), because those resolve to different installs on a
  machine with a user-site shim.
- CI prints the log of every check that did not pass, marking checks outside the required
  set as advisory. A red gate used to name the failing check and nothing else. Adding a check that
  invokes a new binary now also requires registering and pinning it; the failure message
  names the three steps.
- Effectiveness ledger (ADR-0047): `ledger.sh` + `meta_harness.ledger` + append-only
  verdict history — answers "is governing this project actually *catching* anything?"
  (which `status` can't). `verify.sh` now appends each run's `Verdict` to
  `.meta-harness/verdict_history.jsonl` (best-effort, alongside the last-verdict write);
  `read_history`/`append_history` are fail-soft (missing → `[]`, bad lines skipped).
  `ledger.sh [PATH ...]` renders per project: gate RUNS, failures CAUGHT (the gate is
  load-bearing, not decorative), and current pass/fail STREAK, plus a portfolio tally.
  Reuses `discover_projects` + the gate's own verdict; pure core, unit-tested (100%),
  threshold-free (counts + streak, no score). Ratchet-baseline movement deferred to a
  follow-up.
- Portfolio status / roster view (ADR-0046): `status.sh` + `meta_harness.status` +
  `meta_harness.verdict` — the missing view *across* governed projects. One table shows,
  per project: git-or-not, required-check count, last gate verdict
  (`pass`/`fail`/never-gated), config drift (uncommitted `borromeanrings.toml`), and
  adoption drift (recommended checks not yet required, via `plan_adoption`). The gate
  now persists a compact last-known `Verdict` to `.meta-harness/last_verdict.json`
  (best-effort — a write failure never turns a PASS into a FAIL); `status` reads it, so
  the default view is instant. `--run` re-gates each project first (authoritative,
  CI-usable exit); `--list` prints paths. Reuses the single sources of truth
  (`load_config`, `plan_adoption`/`RECOMMENDED`, the gate's own verdict) — no duplicated
  policy. Threshold-free (a per-project table, not a blended score). Unit-tested (100%,
  23 cases) + dogfooded on the maintainer's real 10-project portfolio.
- Static accessibility (a11y) invariants gate (ADR-0045): `15_a11y` +
  `meta_harness.accessibility` — the deterministic, threshold-free slice of matrix #6
  (Product/UX). Native stdlib `html.parser` scan of tracked `*.html`/`*.htm`/`*.xhtml`
  (minus `[a11y].exclude`) reports WCAG-cited violations for a per-project rule set
  `[a11y].require`: `html_lang` (a full document declares a non-empty `<html lang>` —
  WCAG 3.1.1), `img_alt` (every `<img>` carries an `alt`; `alt=""` allowed — WCAG
  1.1.1), `page_title` (a full document has a non-empty `<title>` — WCAG 2.4.2).
  Document-level rules gate on the presence of `<html>`, so HTML *fragments* are never
  falsely flagged. No tracked HTML ⇒ pass. Dogfooded on **fire** (Electron; five
  renderer pages, *all* missing `<html lang>` — the justified need); borromeanRings has
  no HTML so it does not declare the check. Threshold-free (no Lighthouse-style score);
  rendered a11y (contrast/ARIA/focus) is deferred to a future heavy lane. Unit-tested
  (11 cases) + adversarially verified.
- Container (Dockerfile) hygiene gate (ADR-0044): `14_container` +
  `meta_harness.container` — the deterministic, threshold-free slice of matrix #4
  (SRE / operational). Native stdlib Dockerfile parse (multi-stage, line-continuations,
  comments, registry `host:port`, digests) reports violations for a per-project rule
  set `[container].require`: `non_root` (final stage must end on a non-root `USER`),
  `pinned_base` (external `FROM` pins a non-`latest` tag or digest; `scratch`/`$`-var
  exempt), `healthcheck` (a `HEALTHCHECK` is declared). No Dockerfile ⇒ pass. A
  run-and-exit gate-runner omits `healthcheck`; a service keeps the full set. Fixes
  borromeanRings's **own** image (was root — added a non-root `USER`) and dogfoods
  `["non_root", "pinned_base"]` on it; the full set is validated against AutoApply's
  real service Dockerfile (flags its missing HEALTHCHECK). Unit-tested (13 cases) +
  adversarially verified.
- ADR-discipline gate (ADR-0043): `13_adr` + `meta_harness.adr_discipline` — on a
  feature branch (name starts with `[adr].require_prefixes`, default `feat/`), a
  change that touches `src` must also add/modify an ADR under `[adr].dir`
  (`docs/adr/`), so a new capability can't land with no recorded decision. Fills
  coverage-map rows D/H; deterministic, threshold-free, git-derivable (merge-base
  diff, `--relative` so it works for git-root and subdir projects). The buildable,
  no-telemetry slice of the delivery/process matrix. Native, unit-tested +
  adversarially verified.
- Secret-scanning completeness (ADR-0042): `74_secret_history` (heavy lane) scans
  every blob reachable from any ref for high-confidence secrets — a
  committed-then-deleted secret still lives in history and is compromised.
  Reachable-only (dangling objects excluded), fail-closed, deduped by a one-way
  fingerprint (the secret is never emitted); acknowledge rotated/benign findings
  via `[secrets].history_allow`. Native (`meta_harness.secret_history`),
  unit-tested + adversarially verified. Also hardens `12_secrets` to **fail
  closed on a non-git directory** (was a vacuous pass — found in rollout).
- Adoption helper for existing projects: `adopt.sh` + `meta_harness.adopt` —
  migrates a project already governed at the founding baseline onto the newer
  quality/security checks. Plans the missing recommended set (`12_secrets`,
  `11_changelog`, `32_complexity`, `33_coupling`, `45_docstrings`), seeds each
  ratchet's baseline from current state, creates a `CHANGELOG.md` if needed, and
  rewrites `[checks].required` in place. Idempotent, native, no installs.
  Complements `init.sh` (new projects); piloted on `reliefq` 7 → 12 checks green
  (ADR-0041).
- Public-API breaking-change detection: `34_api_diff` — diffs the public
  surface vs the merge-base; a removed symbol / removed-renamed param / new
  required param fails unless `[api].allow_breaking=true`. Native ast+git,
  dogfooded on `examples/textkit` (ADR-0040).
- Example governed project: `examples/textkit` — a small library (different
  archetype) with its own `borromeanrings.toml`, governed by borromeanRings's
  gate end-to-end (11 checks). Proves the 'any project' portability claim; a
  permanent integration test asserts its gate passes.
- Coupling ratchet: `33_coupling` — worst-case efferent coupling (fan-out) over
  the internal module graph, non-regression, native (ADR-0038).
- Critic activation: `scripts/critic-judge.sh` (provider-agnostic, fail-closed
  judge — claude CLI or ANTHROPIC_API_KEY) + `docs/CRITIC-ACTIVATION.md`; the
  Wave-2 critics are now one config line from live (ADR-0030/0036).
- Agent-enhancement recommender (advisory): `meta_harness.enhancements` — a
  curated, maintainer-verified catalog of open-source tools that improve the
  *wrapped agent* (model routing, MCP servers, observability, caching), with a
  `[enhancements].interests` filter. Proposes, never gates (ADR-0037).
- **Enforcement-coverage program** — turning the SWE best-practice matrix into
  real gates:
  - Adversarial self-test corpus: the gate must reject known-bad and accept
    known-good (ADR-0025).
  - Tamper-evident receipts: content digest + fail-closed verdict, run-digest
    anchor (ADR-0026).
  - Native import-direction architectural fitness: `leaves` / `private` /
    `forbidden` / `forbid_cycles` contracts over the internal module graph
    (ADR-0027).
  - Changelog discipline (this check): presence + `Unreleased` section, with an
    opt-in strict "entry on source change" rule (ADR-0028).
  - Native secret scanning: high-confidence provider tokens + private keys in
    tracked files, fail-closed, `allow-secret` escape hatch (ADR-0032).
  - Docstring-coverage ratchet: native, non-regression, no absolute target
    (ADR-0029).
  - Wave-2 critic rubrics (advisory): `56_critics` judges functions against
    error-handling / naming / security / boundary-value / test-smell rubrics
    via a live model judge; a DRY registry over the doc-drift machinery,
    dormant until `[critic].judge_command` is wired (ADR-0036).
  - Doc-drift critic: first live application of the T2 seam — a model judge
    external to the generator checks docstrings against code; advisory-first,
    opt-in via `[critic].judge_command` (ADR-0030).
  - Cyclomatic-complexity ratchet: native McCabe, worst-case non-regression, no
    absolute ceiling (ADR-0031).

  - Mutation-score ratchet (heavy): `60_mutation` runs mutmut in CI and
    ratchets assertion strength vs `.borromeanrings-mutation-baseline`
    (0.80; current 0.83), fail-closed on 0-evaluated (ADR-0022).
  - License compliance (heavy): `72_licenses` runs pip-licenses in CI and
    denies incompatible copyleft (`[licenses].deny`), with `allow_packages`
    exceptions (ADR-0035).
  - Dependency CVE audit (heavy): `70_pip_audit` runs pip-audit in CI and
    fails on known vulnerabilities; base tooling / accepted CVEs ignorable
    via `[audit]` (ADR-0034).
  - CI-tier heavy lane: `verify.sh --heavy` runs + requires `checks/ci/`
    (`[checks].heavy`), the home for expensive tool-checks; landed dormant
    (ADR-0033).

### Changed
- Stewardship reconciled as a **cadence over the four AI Fluency competencies**, not a fifth
  (ADR-0020 amendment, #177): its three questions reduce to Delegation, Discernment and
  Diligence asked mid-run, and the framework's authors never proposed a fifth. The
  `ai-fluency-stewardship` skill is rewritten as that schedule — two speeds (fast per turn,
  full per task), checkpoints each tied to a detector this repo has (Stop verdict flip and
  bounded-retry escalation, `22_charter`, PreCompact/SessionStart brief, the rewrite-contract
  record once merged), and back-edges (product failure → Description, process failure →
  Delegation). `docs/AI-FLUENCY.md` gains a Cadence section; SPEC-ai-fluency and MANIFESTO
  drop the "plus a 5th" wording. Docs and skill text only; skill growth paid for by trims in
  the same file.
- Enforcement-coverage map corrected to reality: coverage-ratchet was mis-claimed
  ✅ but no check exists (now ❌ candidate); coupling (`33_coupling`), public-API
  breaking-change (`34_api_diff`), and the adoption path (`adopt.sh`) marked ✅;
  doc-drift noted as activation-paused (agent-only, no API keys); added §6 for the
  other governance matrices (security, DORA, SRE, data/ML, product/UX).
- Grouped `tests/` into `unit/` (23) + `integration/` (5 shell-out tests); layout
  threshold back to 15; mutmut ignore paths updated; retires the 30 workaround.
- Enforcement-coverage map refreshed to reflect the shipped suite (T1 filled,
  T2 critic seam + rubric family live-advisory); honest scorecard updated.
- Changelog strict rule (`require_entry_on_src_change`) turned **on** now the
  PR queue has cleared (ADR-0028).

### Notes
- Earlier increments that are in review: mutation-score ratchet (ADR-0022),
  external rubric-critic seam (ADR-0023), project profiler (ADR-0024), and the
  enforcement-coverage map.
