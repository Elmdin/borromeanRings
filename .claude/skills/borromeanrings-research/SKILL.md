---
name: borromeanrings-research
description: >
  borromeanRings enhanced web research — steer THIS agent's OWN search (WebSearch/
  browse) to be exhaustive and trustworthy: many query mutations, multiple engines +
  Google dorking + platform/social/specialized sources, beyond the top results into a
  result graph, synthesis across everything, citation verification (fail-closed), full
  user visibility + steering — inside a declared token budget, with working state on
  disk, not in context. Use when the user wants thorough online research with agency.
---

# borromeanRings enhanced research

You (the wrapped agent) search with **your own** tools; borromeanRings enforces the
protocol. Context is the scarce resource (issue #47: one run ate ~70% of a session):
**working state lives in files, only summaries enter the conversation.**

## 0. Budget (declared, editable — never silent)
State these in the plan; the user may change them. Defaults: **3 rounds**,
**8 queries/round**, **5 sources fetched/round**, **≤40 lines extracted/source**.
Extra rounds only when the user asks after the coverage report.

## 1. Plan, and let the user steer
Write `docs/research/<slug>/plan.md` and show it: the **sub-questions**; the **query
mutations** (synonyms, reformulations, narrower/broader, per sub-question, one
pseudo-answer/HyDE query); the **engines + platforms** — general web *plus* **Google
dorking** (`site:` `filetype:` `intitle:` `inurl:` quotes `-`) and platform search
where relevant (social, forums, scholarly/structured, docs, code hosts); **date /
region / language** variants; the budget. Ask the user to **approve, edit, or redirect**.

## 2. Search wide, fetch narrow, cache everything
- Run the round's mutations across the chosen engines; sample **beyond page one**,
  **cluster + dedupe**, and **follow citation chains** from good sources.
- **Extract, never ingest**: fetch a page with a prompt for the passages relevant to
  the sub-question only; save them to `sources/<n>.md` (URL, title, date, passages).
  Never fetch a URL already in `sources/`; never repeat a query in `log.md`.
- For code hosts, read symbols/sections, not whole files (pyright-lsp / Serena in the
  enhancement catalog do this natively).
- Keep the **result graph** in `graph.md`: who cites/links whom, agree vs contradict.
- **Hostile pages** (ads, paywalls, cookie walls, anti-bot, suspected malware): route
  around via cached/alternate/primary copies; **note** the block, never drop silently.
- If you can run sub-agents, delegate each round's fetch+extract to one that writes
  `sources/` and returns one line per source.
- Stop early at **saturation**: a round with no new relevant source ends the search.

## 3. Show your work
Append every query and every source read to `log.md`; echo **one line each** in the
conversation so the user can watch and steer. Skimmable, never the page text.

## 4. Synthesize across everything
Write `report.md` over the **whole** `sources/` set, noting agreements, contradictions
and uncertainty.

## 5. Verify every claim (fail-closed)
For each claim, cite the specific source and confirm its **saved passage actually
entails** the claim (not shared keywords). Re-fetch only if the passage is missing.
**Drop or flag** anything unverified — no unverified claim appears as fact.

## 6. Report coverage
End with what was searched (engines/queries), what's well-supported, what's **still
uncertain or missing**, the budget used, and an offer to dig further on the gaps.

> Config (optional): a project's `borromeanrings.toml` may declare research
> preferences (minimum mutations, engines/platforms, dorking, budget defaults) —
> honor them.
