# The Borromeo Manifesto

> The north star. This is *why* borromeo exists and what it is ultimately for. Everything in
> `VISION.md`, `ROADMAP.md`, and the code serves this. Written summer 2026.

## The problem
A disorganized life is the limiting factor on growth. Thoughts, notes, plans, and options are
scattered across paper and apps; there's too much to know and no reliable way to (a) **find** the
best information, (b) **organize** what you find, and (c) decide **what to do** with it. Time and
attention are scarce — you cannot be part of everything — so the real task is to **minimize waste**
and spend yourself only on the highest-value things, while still having a hand in the rest.

## borromeo's scope: the meta-harness, and nothing more
There is an optimal way to **find** information, an optimal way to **organize** it, and an optimal
way to **act** on it. Solving all of that needs *software* — and the prerequisite is **the best way
to build software**. **That is borromeo, and only that:** a meta-harness that enhances any existing
AI agent so it builds software better.

The other tools the broader mission needs are **separate products you build *with* borromeo** — not
parts of borromeo:

| Product | "The best way to…" | Relationship to borromeo |
|---|---|---|
| **borromeo** (this repo) | build **pristine software** — model/harness-agnostic, gates best practices, ever-growing | **is** the meta-harness |
| Deep Research tool | **find & synthesize information** | *built with* borromeo (separate product) |
| Notes/Kernel | **organize notes/plans into tasks, roadmaps, visual maps** | *built with* borromeo (separate product) |

Keeping borromeo narrow is the discipline: it must do one thing — make agents build software well —
so everything else can be built on top of it cleanly. Conflating the harness with the end-user tools
is scope creep.

## Why borromeo first (the bootstrap)
Build **the best way to build software** first, because every other product depends on it. borromeo
is the **low-regret** move: it makes *everything* built afterward better, no matter how the larger
plan evolves. That dissolves the chicken-and-egg ("is this even the optimal thing to focus on?") —
the harness pays off under every future, so starting there is correct even under total uncertainty.
A deep-research product (built with borromeo) then de-risks the rest by checking what already
exists and what's truly best.

## Operating principles
- **borromeo stays narrow.** It is the meta-harness — make agents build software better. End-user
  tools (deep research, notes/kernel) are *separate products built with it*, not features of it.
- **Don't reinvent the wheel.** Where a great tool exists, use it (e.g. the future notes product
  builds on **Obsidian**; a research product runs on top of real browsers/search engines).
- **Recursive, but shipping.** borromeo improves itself, but beware infinite recursion: ship real
  value before polishing the harness forever.
- **Optimality under scarcity.** Limited time and cognition → maximize value, minimize waste; let a
  **lab** carry the rest (a hand in everything without using your own hands).
- **Recursive self-improvement, never self-rewriting.** borromeo extends itself with human-approved
  merges; it never autonomously rewrites its own core (see `adr/0007`).

## The near-term mission
Make **borromeo** genuinely good at its one job: enhancing existing agents to build software better
(the gate, CI, gated auto-merge, config spine, and prompt rewriting already work). Then *use*
borromeo to build the separate products the broader mission needs — starting with a deep-research
tool and a notes/kernel — each in its own right, on top of a harness that's proven to make building
software better.
