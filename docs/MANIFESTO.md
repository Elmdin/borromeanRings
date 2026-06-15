# The Borromeo Manifesto

> The north star. This is *why* borromeo exists and what it is ultimately for. Everything in
> `VISION.md`, `ROADMAP.md`, and the code serves this. Written summer 2026.

## The problem
A disorganized life is the limiting factor on growth. Thoughts, notes, plans, and options are
scattered across paper and apps; there's too much to know and no reliable way to (a) **find** the
best information, (b) **organize** what you find, and (c) decide **what to do** with it. Time and
attention are scarce — you cannot be part of everything — so the real task is to **minimize waste**
and spend yourself only on the highest-value things, while still having a hand in the rest.

## borromeo's scope: the meta-harness that enhances agents
**borromeo is a meta-harness: it enhances any existing AI agent so it builds software better** — and
so it does *everything* it already does, better. Most agents/harnesses already ship capabilities like
code-writing, prompting, and **deep research**; borromeo's job is to **improve those built-in
capabilities**, not to rebuild them. So borromeo *enhances*:

| Agent capability | borromeo's enhancement |
|---|---|
| writing code | best-practice **gates** (a change can't pass until it's correct/clean/safe) |
| the user's prompt | **prompt rewriting** (the agent refines intent; borromeo enforces it well) |
| **deep research** (built into most agents) | **multi-engine + comprehensive coverage, query mutation, a completeness critic ("don't miss anything"), full visibility, and fact-check + deterministic gates** on what it finds |

What borromeo does **not** do is become an end-user application. The **notes/Kernel** — organizing
all your plans/documents/social media into a navigable second brain — is a **separate product built
*with* borromeo**, not part of it. Keeping borromeo to "make agents build software better (incl.
their research)" is the scope discipline; building end-user apps into it is scope creep.

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
Make **borromeo** genuinely good at its job: enhancing existing agents (the gate, CI, gated
auto-merge, config spine, and prompt rewriting already work; **deep-research enhancement** is the
active workstream). Then *use* borromeo to build the **notes/Kernel** as a separate product, on top
of a harness proven to make building software — and research — better.
