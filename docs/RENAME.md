# The borromeo -> borromeanRings rename: what changed, what did not, what you run

> Closes the rename tail (issue #62). The in-repo rename landed in PR #46
> (`a76e136 chore: rename borromeo -> borromeanRings (brand) / borromeanrings (identifiers)`).
> This page records the operational tail: the names that stay, the backward-compat
> seam, and the exact commands a human runs on their own machine and on GitHub.

## 1. Naming rules

| Surface | Name |
|---|---|
| Brand / prose | **borromeanRings** |
| Identifiers (repo slug, config file, skill dirs, env vars, shell helpers) | `borromeanrings`, `borromeanrings.toml`, `BORROMEANRINGS_HOME`, `borromeanrings_*` |
| GitHub repo | `https://github.com/3MagicLabs/borromeanRings` (GitHub slugs are case-insensitive; `borromeanrings` resolves too) |

## 2. What was renamed (PR #46 + this tail)

- Repo, README, badges, skills (`skills/borromeanrings*`), hooks, env vars, shell helpers.
- Config file: `borromeo.toml` -> `borromeanrings.toml` (with a compat fallback, section 4).
- Remaining prose that still said "borromeo" (ADR-0042, ADR-0044, ADR-0045) — fixed here.

## 3. What was deliberately NOT renamed — and why

| Old name | Where | Why it stays |
|---|---|---|
| `meta_harness` (Python package) | `src/meta_harness/`, every `from meta_harness...` import, `pyproject.toml`, `setup.cfg`, `[project].package` in `borromeanrings.toml`, mutmut config | Every governed project's checks, hooks and `adopt.sh` import it by this name; the mutation-ratchet baseline and `PYTHONPATH=$BORROMEANRINGS_HOME/src` calls depend on it. Renaming it is a separate, breaking migration (its own ADR + a major-version `[api].allow_breaking` release), not a tail. |
| `.meta-harness/` (evidence dir) | receipts, `last_verdict.json`, `verdict_history.jsonl`, ratchet baselines, hook markers — in **every** governed project | The receipts, baselines and ledger history of already-governed projects live there. Renaming would orphan their evidence and reset every ratchet. Same reasoning: its own migration. |
| "meta-harness" (the noun) | prose in ADRs, specs, PLAN-v0.md | It is the *kind of thing* borromeanRings is, not the old product name. |
| `borromeo.toml` mentioned in ADR-0020 and SPEC-ai-fluency | historical records | They refer to the legacy file name *as* the legacy file name (a decision record must not be rewritten). |

Only "borromeo" standing in for the **project** was a rename miss; "meta_harness"/"meta-harness" hits are load-bearing identifiers.

## 4. Backward compatibility for `borromeo.toml` (deprecated)

A project governed before the rename may still carry `borromeo.toml`. It must not silently
fall out of governance, so:

- `meta_harness.spine.resolve_config_path(path)`: when the requested file is the canonical
  `borromeanrings.toml` and it is absent, a sibling `borromeo.toml` is loaded instead and a
  `FutureWarning` (`... uses the deprecated config name borromeo.toml; rename it ...`) is
  printed to stderr, once per process per legacy file. It is a `FutureWarning` because
  Python's default filters show that category from any module; a `DeprecationWarning` is
  hidden outside `__main__` and never reached stderr through the real call paths. The
  canonical file always wins when both exist; no other file name is ever redirected. Every
  check and hook loads through `load_config`, so this one seam covers them all (tests:
  `tests/unit/test_spine.py`, `tests/unit/test_status.py`).
- Where you see it: `verify.sh` prints its own `DEPRECATED config name` notice on every
  run; `status.sh` and `ledger.sh` print the `FutureWarning` per legacy project; the Stop
  hook (`stop_gate`, via the gate output) and the UserPromptSubmit hook (`prompt_rewrite`)
  surface it too. The PreToolUse branch guard (`pre_bash_guard`) redirects its Python
  stderr to `/dev/null` by design, so it governs a legacy project silently.
- The substrate hooks (`prompt_rewrite`, `stop_gate`, `pre_bash_guard`, `post_edit_format`)
  and `status.sh` / `ledger.sh` discovery recognise either file name; `status.sh` reports
  "config uncommitted" against the file it actually resolved (a stray untracked
  `borromeo.toml` beside a clean `borromeanrings.toml` is not drift).
- `adopt.sh` stays strict: it rewrites the canonical file, so it asks you to rename first.

**Migrate** (one command, in the governed project):

```bash
git mv borromeo.toml borromeanrings.toml && git commit -m "chore: rename config to borromeanrings.toml"
```

The fallback is a transitional courtesy and will be removed in a later minor release
(tracked in the CHANGELOG `Deprecated` section).

## 5. Commands a human runs (nothing here is automated by the harness)

### 5.1 Fix your local clone's remote

Pushes to the old URL still work via GitHub's redirect, but print
`This repository moved. Please use the new location` on every push. Fix it once:

```bash
git remote set-url origin https://github.com/3MagicLabs/borromeanRings.git
git remote -v   # verify both fetch and push show the new URL
```

### 5.2 Re-run the global install (skills + hooks)

`install-global.sh` installs skills under their **current** names and replaces its own hook
entries, but it does not delete skill directories installed under the old names. After the
rename:

```bash
./install-global.sh                        # refreshes borromeanrings*, ai-fluency-* skills + hooks
ls ~/.claude/skills | grep -i '^borromeo'  # list stale, pre-rename skill dirs (expected: borromeo, borromeo-contribute, borromeo-research)
```

Then delete each stale directory that listing shows (they are the pre-rename copies of
`borromeanrings`, `borromeanrings-contribute`, `borromeanrings-research`) with your file
manager or `rm -r` on each named directory — review the list before removing anything.

Review `~/.claude/settings.json` afterwards: `install-global.sh` keys its hook replacement on
the *current* `BORROMEANRINGS_HOME`, so a hook entry pointing at an old clone location
(e.g. `.../borromeo/.claude/hooks/...`) is only stale if that path no longer exists.

### 5.3 Refresh the GitHub label descriptions

From `gh label list --json name,description` (read on 2026-09-08), three labels still say
"borromeo":

```bash
gh label edit separate-product --description "Belongs to a product built WITH borromeanRings, not borromeanRings core"
gh label edit deep-research    --description "borromeanRings's deep-research enhancement (harness feature)"
gh label edit harness-feature  --description "A borromeanRings meta-harness capability"
```

Re-check with `gh label list --json name,description | grep -i borromeo` (expect no output).
