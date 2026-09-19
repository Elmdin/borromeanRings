# SPEC — Claude Code plugin distribution

Issue #136 · ADR-0057 · files `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`hooks/hooks.json`, `skills/<project-skill>` symlinks · doc `docs/PLUGIN.md`

## User story
As a new user, I want one command that wires borromeanRings's hooks and skills into my
Claude Code, so that adoption does not depend on running `init.sh` / `install-global.sh` /
`adopt.sh` in the right order — while every project still opts in explicitly.

## Contract
- `.claude-plugin/plugin.json`: `name = "borromeanrings"`, `version` equal to `VERSION`,
  a `description`; every key is one documented in the plugins reference (no invented
  fields; `claude plugin validate --strict` treats unknown keys as errors).
- `.claude-plugin/marketplace.json`: one entry, name equal to the plugin's, `source: "./"`,
  no entry-level `version` (the plugin manifest is the single version source).
- `hooks/hooks.json`: top-level `hooks`; exactly the `HOOK_SCRIPTS` events; per event the
  same matchers, order and timeouts `init.sh` writes (SessionStart: two entries, `compact`
  then `resume`); every command is `"${CLAUDE_PLUGIN_ROOT}"/.claude/hooks/<script>` where
  `<script>` is that event's `HOOK_SCRIPTS` entry, exists, and is executable.
- The wiring is identical — modulo the path prefix — across all four spellings: plugin,
  `init.sh` output, `install-global.sh` output, and this repo's own `.claude/settings.json`.
- `skills/<name>` is a symlink to `.claude/skills/<name>` for every project skill, and no
  other symlink lives in `skills/`. Skill text carries `${CLAUDE_PLUGIN_ROOT}` (never the
  legacy `__BORROMEANRINGS_HOME__`); `install-global.sh` substitutes it with the home path.
- `classify_enforcement` reports `auto` for hooks spelled the plugin way.
- The hook scripts are unchanged; they stay inert without a `borromeanrings.toml`.

## Edge cases
- Both the plugin and a project's `init.sh` settings register a hook ⇒ the script runs
  twice; non-idempotent hooks yield on the duplicate via `hook_dedupe.claim`.
- The plugin is installed from a marketplace ⇒ `${CLAUDE_PLUGIN_ROOT}` is a versioned
  cache copy; project settings must not point at it (see `docs/PLUGIN.md`).
- `VERSION` is bumped without `plugin.json` ⇒ the version test fails the gate.
- A project skill is added under `.claude/skills/` without a link ⇒ the symlink test fails.

## Constraints
- No `~/.claude` writes by the repo itself; no publishing to any public marketplace; no
  CI, packaging, or model calls. Nothing is copied into a governed project.
- Tests that load repo files by path live in `tests/integration/` and are excluded from
  mutmut's sandbox (`setup.cfg`), like the other shell-integration suites.

## Acceptance
Integration: `tests/integration/test_claude_plugin.py`. Unit:
`tests/unit/test_self_status.py::test_plugin_path_spelling_counts_as_enforced`.
`claude plugin validate .claude-plugin/plugin.json` and `claude plugin validate .`
(marketplace) both pass.
