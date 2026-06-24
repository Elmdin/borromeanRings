---
name: borromeanrings-contribute
description: >
  Fix or improve borromeanRings itself (the meta-harness) from ANY project — safely. Use
  when you hit a borromeanRings bug or limitation while working elsewhere and want to fix
  the harness. It branches borromeanRings, makes the fix, runs borromeanRings's OWN gate, opens a
  PR, and STOPS for human approval. It NEVER merges or pushes to borromeanRings's main
  (self-extension, never self-rewriting; a human approves every merge to borromeanRings).
---

# Contribute a fix/improvement to borromeanRings (safely)

borromeanRings is the **trust root**: a bug — or a *weakened check* — here silently corrupts
every project borromeanRings governs. So changes follow borromeanRings's own rule:
**self-extension, never self-rewriting — a human approves every merge to borromeanRings itself.**
You PROPOSE; the human DISPOSES. **Never merge, never push to borromeanRings's `main`.**

When the user describes a borromeanRings issue/improvement, do this:

1. **Go to borromeanRings, sync main:**
   `cd __BORROMEANRINGS_HOME__ && git checkout main && git pull --ff-only`
2. **Branch** (never work on main):
   `git checkout -b fix/<short-slug>`   (or `feat/<slug>`)
3. **Make a small, focused fix.** If it's a bug: **add a failing test/check FIRST**
   (borromeanRings's "failures become permanent checks"), then fix it. **Never weaken, disable,
   or skip a check to make the gate pass** — that defeats the trust root.
4. **Pass borromeanRings's OWN gate** (same-or-stricter, because it's the trust root):
   `./verify.sh` must exit 0. Fix whatever it flags; show its output as evidence.
5. **Open a PR** (do not merge):
   `git push -u origin HEAD` then `gh pr create` with a clear what/why and how-verified.
6. **STOP. Hand to the human.** Do NOT run `merge.sh`, do NOT merge, do NOT push to `main`.
   Report: the PR link, a one-line summary of the fix, and how you verified it.
7. **After the human merges**, the fix goes live by pulling it:
   `cd __BORROMEANRINGS_HOME__ && git pull`. Then it's live immediately for the gate, checks,
   config, hook logic, and the research playbook (no session reload). Only hook/skill
   *registration* changes (settings.json / a brand-new skill) need a fresh session.

Keep it small, gated, reviewable. The gate catches breakage; **human review is the
safeguard against a check being made too lenient** — so always leave the merge to the human.
