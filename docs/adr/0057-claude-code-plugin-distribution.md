# ADR-0057: Ship borromeanRings as a Claude Code plugin (by-reference governance, one-line install)

**Status:** Accepted · 2026-09-08 · closes #136

## Context
Three hand-rolled install paths exist: `init.sh` (per-project `.claude/settings.json` +
skills copy), `install-global.sh` (user-level hooks + skills, edits `~/.claude/settings.json`),
`adopt.sh` (upgrade an already-governed project). Claude Code plugins are GA and bundle
hooks + skills as one installable, versioned unit. The 2026-09 tooling survey listed
"ship as a plugin" as the adoption gap; #136 asked for it with three constraints that
cannot bend (HANDOFF §3): per-project opt-in, governance by reference (ADR-0013), and
hooks inert outside a governed project.

Every field and behaviour below was read from the official docs on 2026-09-08
(code.claude.com/docs/en/plugins, /plugins-reference, /plugin-marketplaces,
/discover-plugins); section names are cited so the claims can be re-verified.

## Decision
1. **The plugin root is the repository root.** `.claude-plugin/plugin.json` sits at the
   root; `hooks/hooks.json` and `skills/` are at the root, never inside `.claude-plugin/`
   (reference, "Plugin directory structure": "All other directories must be at plugin
   root"). This is the only layout in which the installed plugin is self-sufficient: the
   hooks derive `BORROMEANRINGS_HOME` from their own location (`$HERE/../..`) and run
   `verify.sh`, `src/` and `checks/` from it — so those must live *inside*
   `${CLAUDE_PLUGIN_ROOT}`. The six scripts are **unchanged**.
2. **`hooks/hooks.json` wires the six `HOOK_SCRIPTS` events** with the same matchers and
   timeouts as `init.sh`, spelling every command `"${CLAUDE_PLUGIN_ROOT}"/.claude/hooks/<x>.sh`
   (reference, "Environment variables": `${CLAUDE_PLUGIN_ROOT}` = "Absolute path to the
   plugin's installation directory", shown quoted in the shell-form example). The file's
   top-level key is `hooks`, the same shape as `settings.json` (plugins guide, "Migrate
   hooks": "Copy the `hooks` object from your `.claude/settings.json` … since the format
   is the same").
3. **Skills are exposed by symlink, not copy.** `skills/` is the default scan directory
   (reference, "Default locations"); it already holds the user-level skills that
   `install-global.sh` installs. The two project skills in `.claude/skills/` are linked
   in as `skills/<name> -> ../.claude/skills/<name>`. One source of truth; a test pins the
   links. `claude plugin validate` reports the links as a warning and states "A session
   loading this plugin does follow them" — so this is a validator limitation, not a load
   one. The manifest `skills` field was rejected: it "adds to the default `skills/` scan"
   under `--plugin-dir` but *replaces* it for a marketplace-root source (reference,
   "Path behavior rules") — two install paths would expose different skill sets.
4. **The templated skills use `${CLAUDE_PLUGIN_ROOT}` as their path token.** Claude Code
   substitutes it in skill content (reference, "Substitution scope": skill/agent content,
   "anywhere placeholder appears"); `install-global.sh` substitutes the same token when
   it copies skills to `~/.claude/skills/`, so one file serves both delivery modes. The
   legacy `__BORROMEANRINGS_HOME__` spelling stays honoured by the installer.
5. **A self-hosted single-plugin marketplace** (`.claude-plugin/marketplace.json`, entry
   `source: "./"`) makes the one-line install real from a local checkout and from the
   GitHub URL (marketplaces guide, "Self-hosting: single plugin at marketplace root";
   discover guide, "Add from GitHub" / "Add from local paths"). It is a file in this repo,
   not a submission to any public catalog. The entry carries no `version`: the marketplace
   version would take precedence over `plugin.json` (reference, "Version management")
   and could drift from `VERSION`.
6. **Opt-in is untouched.** The plugin writes no `borromeanrings.toml`; every hook exits 0
   unless the project has one. `init.sh`/`adopt.sh`/`install-global.sh` remain the
   non-plugin path. When both register the same hook, the hooks' claim mechanism
   (`hook_dedupe.claim`, first-writer-wins with a freshness window; `_lib.sh`
   `borromeanrings_claim`) makes the duplicate yield — the same defence already built
   for the project-level + user-level duplication (#53).

## Alternatives considered
- **Plugin in a `plugin/` subdirectory** with hooks reaching `../.claude/hooks` — rejected:
  a marketplace install *copies* the plugin directory to `~/.claude/plugins/cache/…`
  (marketplaces guide, "Local-path plugins: copied, not symlinked"), so the parent is
  gone and `verify.sh` with it.
- **Copy `.claude/skills/` into `skills/` with a sync script + identity test** — rejected
  in favour of symlinks (fewer moving parts; git and the loader both follow them).
- **Registering the plugin as a skills-directory plugin** (`~/.claude/skills/<name>` →
  checkout; reference, "Skills-directory plugins": "discovered in place rather than
  copied") — not chosen as *the* path but documented in `docs/PLUGIN.md` as the
  in-place, by-reference option for people who keep a checkout.

## Consequences
- (+) One command installs hooks + skills for every project; `~/.claude/settings.json`
  is never edited; uninstall is one command (`claude plugin uninstall`).
- (+) `status_assess.classify_enforcement` matches on script *name*, so the plugin
  spelling reads AUTO (tests: `test_plugin_path_spelling_counts_as_enforced`,
  `test_self_status_reads_plugin_wiring_as_automatic_enforcement`).
- (−) **Hook-collision risk.** Context Mode / any other tool registering the same six
  events, or a project with both `init.sh` settings and the plugin, runs each script
  twice per event. Non-idempotent hooks (`prompt_rewrite`, `stop_gate`, `session_start`)
  dedupe by claim; the idempotent ones (`pre_bash_guard`, `post_edit_format`,
  `pre_compact`) simply repeat. Plugin hooks "append handlers (no override)" to project
  hooks (reference, "Hook merging") — nothing is silently replaced.
- (−) **A marketplace install is a copy**, versioned under the plugin cache and pruned
  after an update's grace period (reference, `${CLAUDE_PLUGIN_ROOT}` "changes on plugin
  update"). Governance is still by reference from the *project's* point of view (nothing
  is copied into it), but a project whose `.claude/settings.json` points *at the cache*
  goes stale on update. `docs/PLUGIN.md` therefore says: run `init.sh` from a checkout,
  never from the cache; or opt in by writing `borromeanrings.toml` alone.
- (−) The self-status view reads only the project's own `settings.json`, so a project
  governed by the plugin alone reports enforcement MANUAL although the hooks run.
  Recorded as a known gap; fixing it needs a way to read the active plugin set, which
  the docs do not expose to hooks today.
- (−) **Symlinks need symlink support.** A Windows clone without `core.symlinks` /
  Developer Mode checks `skills/<name>` out as text files holding the target path, and
  the plugin silently loads neither project skill. Documented with the remedy in
  `docs/PLUGIN.md` ("Windows checkouts"); `install-global.sh` warns when it sees one;
  the symlink test recognises the degraded state (file content == target path) and
  reports it as such instead of as corruption. Found in PR #166 review.
- (−) `borromeanrings-contribute` assumes a git checkout (`git pull`); under a cache
  copy there is none. The skill is for contributors, who have one.
