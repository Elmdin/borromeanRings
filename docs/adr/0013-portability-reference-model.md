# ADR-0013 — Portability: govern any project by reference (BORROMEANRINGS_HOME vs PROJECT_ROOT)

**Status:** Accepted

## Context
borromeanRings was only usable on its *own* repo: checks hard-coded its layout (`import meta_harness`,
`src/`), and `verify.sh` set the project root to its own directory. To make borromeanRings actually useful
— govern *other* projects — we must separate "where borromeanRings's code lives" from "the project being
governed," and let the checks target the governed project.

## Decision
- **`BORROMEANRINGS_HOME`** = where borromeanRings's code lives (the dir of `verify.sh`). **`PROJECT_ROOT`** = the
  project being governed = `BORROMEANRINGS_PROJECT` | `CLAUDE_PROJECT_DIR` | `$PWD`. They coincide when
  borromeanRings governs itself; they differ when it's referenced from another project.
- **borromeanRings's own code (`meta_harness`) is always imported from `$BORROMEANRINGS_HOME/src`;** the governed
  project's code is targeted at `PROJECT_ROOT` via config-driven `[project]` (`package`, `src_dir`).
- **Reference model (no copy):** `init.sh <target>` writes a starter `borromeanrings.toml` + a
  `.claude/settings.json` into the target whose hooks point back at `$BORROMEANRINGS_HOME`. Any agent
  prompted in the target is governed; borromeanRings's code is not duplicated.
- Receipts and the coverage-ratchet baseline live **with the governed project** (`PROJECT_ROOT`).

## Alternatives considered
- **Copy/vendor the bundle into each target** — rejected: duplicates borromeanRings across repos and drifts
  out of sync; the Maintainer explicitly wanted to *reference* borromeanRings, not copy it.
- **Publish borromeanRings as a pip package** — deferred: cleaner long-term, but premature (no packaging/
  publishing pipeline yet); the reference model works today.

## Consequences
- (+) borromeanRings can govern **any** project by reference; **proven live** on an external project
  (`/tmp/widget-app`): green when clean, caught an injected type error, Stop hook blocked the agent.
- (+) Self-governance preserved — all defaults resolve to borromeanRings's own setup, so the self-gate
  stays green.
- (−) The target couples to borromeanRings's filesystem path (`BORROMEANRINGS_HOME` baked into its
  `.claude/settings.json`); moving borromeanRings means re-`init`. Acceptable for a referenced tool.
- (−) Check targeting is still **Python-only** (ruff/mypy/pytest/bandit); other stacks need their own
  checks behind the same contract (future).
