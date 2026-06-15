# The Borromeo Manifesto

> The north star. This is *why* borromeo exists and what it is ultimately for. Everything in
> `VISION.md`, `ROADMAP.md`, and the code serves this. Written summer 2026.

## The problem
A disorganized life is the limiting factor on growth. Thoughts, notes, plans, and options are
scattered across paper and apps; there's too much to know and no reliable way to (a) **find** the
best information, (b) **organize** what you find, and (c) decide **what to do** with it. Time and
attention are scarce — you cannot be part of everything — so the real task is to **minimize waste**
and spend yourself only on the highest-value things, while still having a hand in the rest.

## The three problems, and the three tools
There is an optimal way to **find** information, an optimal way to **organize** it, and — emergent
from both — an optimal way to **act** on it. Solving this needs software; building that software
well needs the right foundation. So borromeo is a **three-layer stack**, built bottom-up because
each layer builds and improves the next, and all three reinforce each other:

| Layer | The tool | "The best way to…" |
|---|---|---|
| **1** | **The SWE harness** (borromeo today) | …build **pristine software** — model/harness-agnostic, gates best practices, verifies code & claims, ever-growing |
| **2** | **The Deep Research tool** | …**find & synthesize information** — deterministic, visualized step-by-step, cited, synthesized, ad/BS/virus-free, on any browser/engine, with any agent or bare LLM |
| **3** | **The Borromeo Kernel** | …**organize notes/thoughts/plans into tasks, roadmaps, and visual maps/graphs** — a second brain that turns everything into actionable next steps |

**They reinforce each other:** the harness builds the research tool and the kernel; the research
tool tells us what's worth building (and whether it already exists); the kernel organizes it all and
feeds priorities back. Improving any one improves the others.

## Why this order (the bootstrap)
First build **the best way to build software**, because software is the prerequisite for everything
else. Then use it to build the **Deep Research tool** (so we can find the best resources and verify
nothing is missed), then use both to build (or assemble) the **Kernel** that organizes an entire
life into a navigable, modifiable map — which can then be presented to family, friends, and
investors, and used to choose next steps with eyes open.

The harness is also the **low-regret** first move: it makes *everything* built afterward better, no
matter how the larger plan evolves. That dissolves the chicken-and-egg ("is this even the optimal
thing to focus on?") — the harness pays off under every future, so starting there is correct even
under total uncertainty. The Deep Research tool then de-risks the rest by checking what already
exists and what's truly best.

## Operating principles
- **Don't reinvent the wheel.** Where a great tool exists, use it. Notes live in **Obsidian**;
  research runs **on top of** real browsers/search engines. borromeo's value is the *organizing,
  verifying, and acting intelligence layered on top* — not rebuilding editors or search engines.
- **Recursive, but shipping.** The stack improves itself, but beware infinite recursion: each layer
  must produce real value before polishing the layer below it forever.
- **Optimality under scarcity.** Limited time and cognition → maximize value, minimize waste; be a
  part of only the best things, and let a **lab** carry the rest (a hand in everything without using
  your own hands — see, learn, and direct the main results while focusing personal effort where it
  compounds).
- **Recursive self-improvement, never self-rewriting.** The stack extends itself with human-approved
  merges; it never autonomously rewrites its own core (see `adr/0007`).

## The near-term mission
Build Layer 1 to "pristine" (in progress — the gate, CI, and gated auto-merge already work), then
build Layer 2 (Deep Research), then assemble Layer 3 (the Kernel) on top of Obsidian. The first
external proof is a research tool good enough to answer, rigorously: *what already exists, and what
is actually the best path?*
