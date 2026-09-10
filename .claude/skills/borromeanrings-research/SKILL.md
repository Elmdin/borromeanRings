---
name: borromeanrings-research
description: >
  borromeanRings enhanced web research — steer THIS agent's OWN search (WebSearch/
  browse) to be exhaustive and trustworthy: many query mutations, multiple engines +
  Google dorking + platform/social/specialized sources, beyond the top results into a
  result graph, synthesis across everything, citation verification (fail-closed), full
  user visibility + steering — inside a declared budget, working state on disk, not in
  context. Use for thorough online research with agency + visibility.
---

# borromeanRings enhanced research

You search with **your own** tools; borromeanRings enforces the protocol. Context is
scarce (issue #47): **working state lives in files, only summaries enter chat.** All
files go under `docs/research/<slug>/` — committed state, not scratch; write nowhere
else.

## 0. Budget (declared, editable, never silent)
State these in the plan; the user may change them. Defaults: **3 rounds**,
**8 queries/round**, **5 sources fetched/round**, **≤40 lines extracted/source**.
More rounds only on request after the coverage report.

## 1. Plan, and let the user steer
Write `plan.md` and show it: the **sub-questions**; the **query mutations** (synonyms,
reformulations, narrower/broader, per sub-question, one pseudo-answer/HyDE query); the
**engines + platforms** — general web *plus* **Google dorking** (`site:` `filetype:`
`intitle:` `inurl:` quotes `-`) and platform search (social, forums,
scholarly/structured, docs, code hosts); **date / region / language** variants; the
budget. Ask the user to **approve, edit, or redirect**.

## 2. Search wide, fetch narrow, cache
- Run the round's mutations across the chosen engines; sample **beyond page one**,
  **cluster + dedupe**, **follow citation chains** from good sources.
- **Extract, never ingest**: fetch with a prompt for only the sub-question's
  passages; save them to `sources/<n>.md` (URL, title, date, passages).
  Never re-fetch a URL in `sources/`; never repeat a query in `log.md`.
- For code hosts, read symbols/sections, not whole files: pyright-lsp / Serena if
  installed, else grep/sed ranges.
- Keep the **result graph** in `graph.md`: who cites whom, agree vs contradict.
- **Hostile pages** (ads, paywalls, anti-bot, malware): route around via cached /
  alternate / primary copies; **note** the block, never drop silently.
- If sub-agents exist, delegate each round's fetch+extract to one that writes
  `sources/` and returns one line per source.
- Stop at **saturation**: a round with no new relevant source ends the search.

## 3. Show your work
Append every query and source read to `log.md`; echo **one line each** in chat so the
user can steer. Never the page text.

## 4. Synthesize across everything
Write `report.md` over the **whole** `sources/` set: agreements, contradictions,
uncertainty.

## 5. Verify every claim (fail-closed)
For each claim, cite the specific source and confirm its **saved passage actually
entails** the claim (not shared keywords). Re-fetch only if the passage is missing. If
it exceeds the extract cap, save it whole in the slug dir and quote only the entailing
lines in chat. Mark each verbatim quote in `report.md` for `24_quotes`: a blockquote,
then `— source: docs/research/<slug>/sources/<n>.md#L<a>-L<b>`. **Drop or flag** anything
unverified — never as fact.

## 6. Report coverage
End with what was searched (engines/queries), what's well-supported, what's **still
uncertain or missing**, budget used; offer to dig into the gaps.

> Config: `borromeanrings.toml` may declare research preferences (mutations, engines,
> platforms, dorking, budget defaults) — honor them.
