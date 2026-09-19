# borromeanRings as a Claude Code plugin

One install wires the six governance hooks and the skills into Claude Code for every
project you open. **Nothing is governed until a project opts in** by having a
`borromeanrings.toml`: every hook exits immediately without one. ADR-0057.

## Install (one line)

From a local checkout (the marketplace is the checkout itself):

```bash
claude plugin marketplace add /path/to/borromeanrings && claude plugin install borromeanrings@borromeanrings
```

From GitHub (no checkout needed):

```bash
claude plugin marketplace add 3MagicLabs/borromeanRings && claude plugin install borromeanrings@borromeanrings
```

Inside a session the same two steps are `/plugin marketplace add …` and
`/plugin install borromeanrings@borromeanrings`; add `--scope project` to the install to
share it with collaborators through `.claude/settings.json` instead of your user config.
Restart Claude Code or run `/reload-plugins`.

For a single session without installing anything: `claude --plugin-dir /path/to/borromeanrings`
(the checkout is used in place). Both marketplace installs **copy** the repository into
`~/.claude/plugins/cache/…`; a checkout kept under `~/.claude/skills/<dir>`
with its `.claude-plugin/plugin.json` is instead loaded in place as `borromeanrings@skills-dir`
— the by-reference option if you already keep a checkout. Do not combine that with
`install-global.sh`, which writes `~/.claude/skills/borromeanrings/` itself.

Check what loaded: `claude plugin list`; validate the layout: `claude plugin validate .`.

### Windows checkouts

`skills/borromeanrings-status` and `skills/borromeanrings-research` are git **symlinks** to
`.claude/skills/<name>`. On a Windows clone without symlink support (no Developer Mode /
`core.symlinks` off) git checks them out as plain text files holding the target path, and
the plugin then loads neither skill — silently. Remedy: enable Developer Mode (or run git
elevated) and clone with `git -c core.symlinks=true clone …` (or set
`git config --global core.symlinks true` first), or clone under WSL. Detect it with
`ls -l skills/` (entries should show `-> ../.claude/skills/…`) or by running
`install-global.sh`, which warns about it; the repo's own test
(`test_project_skills_are_exposed_by_symlink_not_copy`) also reports such a checkout as
"degraded" rather than as a bug.

## What it installs — and what it does not

Installs: the six hooks (`UserPromptSubmit`, `Stop`, `PostToolUse` on Edit|Write|MultiEdit,
`PreToolUse` on Bash, `PreCompact`, `SessionStart` on compact and resume) wired to the
scripts in the plugin's `.claude/hooks/`, and the skills — the project skills
`borromeanrings:borromeanrings-status` and `borromeanrings:borromeanrings-research`, the
bootstrap skill `borromeanrings:borromeanrings`, `borromeanrings:borromeanrings-contribute`,
and the five `ai-fluency-*` skills. Plugin skills are namespaced `borromeanrings:<name>`.

Does **not**: write a `borromeanrings.toml` anywhere, edit `~/.claude/settings.json`, touch
any project, or run anything in a project that has no `borromeanrings.toml`.

## Opting a project in

The plugin only carries the hooks; the project still declares itself governed:

- With a checkout: `/path/to/borromeanrings/init.sh /path/to/project` (writes the starter
  `borromeanrings.toml` and a project-level `.claude/settings.json`), then `adopt.sh` later
  to pick up new checks. Run these from a **checkout**, not from the plugin cache — the
  cache path is versioned and replaced on `claude plugin update`, so hooks pointed at it
  would go stale.
- Without one: create `borromeanrings.toml` by hand (the starter is the heredoc at the top
  of `init.sh`). The plugin hooks alone govern the project.

## Coexisting with `init.sh` / `install-global.sh`

A project set up with `init.sh` registers the same hooks at project level; `install-global.sh`
registers them at user level. With the plugin active too, Claude Code appends the handlers
— it never overrides — so the same script runs more than once per event. The hooks
already handle this: `prompt_rewrite.sh`, `stop_gate.sh` and `session_start.sh` take a
first-writer-wins claim per event (`meta_harness.hook_dedupe.claim`, freshness window 5 s,
fail-open) and the duplicate invocation yields, so the directive is injected once and the
gate runs once; the remaining three hooks are idempotent and simply repeat. You can keep
both, or drop the project-level entries once the plugin is installed. One honest gap:
`./status.sh` reads the *project's* settings, so a project governed by the plugin alone
shows enforcement MANUAL although the hooks run (ADR-0057).

## Uninstall

```bash
claude plugin uninstall borromeanrings@borromeanrings
claude plugin marketplace remove borromeanrings   # optional; also uninstalls its plugins
```

Or `/plugin` → Installed → uninstall. Projects keep their `borromeanrings.toml` and any
`init.sh`-written settings; delete those to un-govern a project.
