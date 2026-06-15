# ADR-0013 — Portability: govern any project by reference (BORROMEO_HOME vs PROJECT_ROOT)

**Status:** Accepted

## Context
borromeo was only usable on its *own* repo: checks hard-coded its layout (`import meta_harness`,
`src/`), and `verify.sh` set the project root to its own directory. To make borromeo actually useful
— govern *other* projects — we must separate "where borromeo's code lives" from "the project being
governed," and let the checks target the governed project.

## Decision
- **`BORROMEO_HOME`** = where borromeo's code lives (the dir of `verify.sh`). **`PROJECT_ROOT`** = the
  project being governed = `BORROMEO_PROJECT` | `CLAUDE_PROJECT_DIR` | `$PWD`. They coincide when
  borromeo governs itself; they differ when it's referenced from another project.
- **borromeo's own code (`meta_harness`) is always imported from `$BORROMEO_HOME/src`;** the governed
  project's code is targeted at `PROJECT_ROOT` via config-driven `[project]` (`package`, `src_dir`).
- **Reference model (no copy):** `init.sh <target>` writes a starter `borromeo.toml` + a
  `.claude/settings.json` into the target whose hooks point back at `$BORROMEO_HOME`. Any agent
  prompted in the target is governed; borromeo's code is not duplicated.
- Receipts and the coverage-ratchet baseline live **with the governed project** (`PROJECT_ROOT`).

## Alternatives considered
- **Copy/vendor the bundle into each target** — rejected: duplicates borromeo across repos and drifts
  out of sync; the Maintainer explicitly wanted to *reference* borromeo, not copy it.
- **Publish borromeo as a pip package** — deferred: cleaner long-term, but premature (no packaging/
  publishing pipeline yet); the reference model works today.

## Consequences
- (+) borromeo can govern **any** project by reference; **proven live** on an external project
  (`/tmp/widget-app`): green when clean, caught an injected type error, Stop hook blocked the agent.
- (+) Self-governance preserved — all defaults resolve to borromeo's own setup, so the self-gate
  stays green.
- (−) The target couples to borromeo's filesystem path (`BORROMEO_HOME` baked into its
  `.claude/settings.json`); moving borromeo means re-`init`. Acceptable for a referenced tool.
- (−) Check targeting is still **Python-only** (ruff/mypy/pytest/bandit); other stacks need their own
  checks behind the same contract (future).
