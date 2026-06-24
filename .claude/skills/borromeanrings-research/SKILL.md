---
name: borromeanrings-research
description: >
  borromeanRings enhanced web research — steer THIS agent's OWN search (its WebSearch/
  browse tools) to be far more exhaustive and trustworthy: many query mutations,
  multiple engines + Google dorking + platform-specific tricks + social/specialized
  sources, going beyond the top results to build a result graph and synthesize
  across everything, with citation verification (fail-closed) and full user
  visibility + steering. borromeanRings ENFORCES the discipline; the agent PERFORMS the
  searches with its own tools. Use when the user wants to research/search online
  thoroughly and wants agency + visibility into the process.
---

# borromeanRings enhanced research

You (the wrapped agent) do the searching with **your own** search/browse tools.
borromeanRings does **not** search for you — it makes your search dramatically better and
keeps the user in control. Follow this protocol every time this skill is invoked.

## 1. Plan, and let the user steer (agency first)
Before searching, produce an explicit **search plan** and show it to the user:
- the **sub-questions** the topic decomposes into;
- the **query mutations/variations** you'll run — aim for *many* (synonyms,
  reformulations, narrower/broader phrasings, sub-question queries, a
  pseudo-answer/HyDE query). Don't settle for one or two;
- the **engines + platforms** you'll use — *more than one*: general web, plus
  **Google dorking** (`site:`, `filetype:`, `intitle:`, `inurl:`, quotes for exact
  phrases, `-` to exclude), and platform-specific search where relevant
  (social media, forums, scholarly/structured sources, docs, code hosts);
- **date / region / language** variants where they matter.

Ask the user to **approve, edit, or redirect** the plan. They have agency here.

## 2. Search broadly (not just the top 20)
- Run the full set of mutations across the chosen engines/platforms.
- **Go wide**: don't ingest only the first page. Sample across many results,
  **cluster + dedupe**, and **follow citation chains** (sources cited by good
  sources) to reach what a shallow search misses.
- Build a **result graph**: track sources and how they connect (who cites/links
  whom, agreement vs. contradiction), so coverage is visible and gaps are obvious.
- **Handle hostile pages gracefully**: ads / paywalls / cookie walls / anti-bot /
  suspected-malware pages — route around them, try cached/alternate/primary
  sources, and **note** when a source was blocked rather than silently dropping it.

## 3. Show your work (visibility)
As you go, surface **each query you send and each source you read** (briefly), so
the user can watch the process and steer mid-flight. Keep it skimmable.

## 4. Synthesize across everything
Synthesize over the **whole gathered set**, not just the first few hits. Note
agreements, contradictions, and uncertainty across sources.

## 5. Verify every claim (fail-closed)
For each claim in your answer, cite the **specific source** and confirm that
source's text **actually supports** the claim (entailment — not just shared
keywords). **Drop or explicitly flag** anything you cannot verify. No unverified
claim appears as a stated fact. (This is borromeanRings's gate, applied to research.)

## 6. Report coverage
End with: what was searched (engines/queries), what's well-supported, and what's
**still uncertain or missing** — and offer to dig further on the gaps.

## Tactics to draw on
Query: synonyms, reformulation, decomposition, pseudo-answer, narrow↔broad.
Reach: multiple engines, dorking operators, social/forum/scholarly/structured
sources, region/language variants, recency filters. Quality: prefer primary +
credible + diverse sources; rank by credibility; avoid ad/SEO spam. Efficiency:
stop when new searches stop yielding new relevant material (saturation); don't
repeat queries; budget effort to the question's importance.

> Config (optional): a project's `borromeanrings.toml` may declare research preferences
> (e.g. minimum mutations, preferred engines/platforms, dorking on/off) — honor
> them. borromeanRings enforces this protocol; you execute it with your own tools.
