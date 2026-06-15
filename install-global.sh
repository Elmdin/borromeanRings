#!/usr/bin/env bash
# Install borromeo at the USER level so you can just say "use borromeo" in ANY
# workspace — no per-project setup. It installs:
#   1. global hooks in ~/.claude/settings.json (they NO-OP unless a workspace has
#      a borromeo.toml, so they never interfere with non-borromeo projects);
#   2. the `borromeo` bootstrap skill + the `borromeo-research` skill.
#
# Re-run after moving borromeo. This MODIFIES ~/.claude/settings.json (merged, not
# clobbered) — review it first. Undo: remove borromeo's hook entries from that file
# and delete ~/.claude/skills/{borromeo,borromeo-research}.
set -uo pipefail

BORROMEO_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
mkdir -p "$CLAUDE_DIR/skills"

# 1. skills (substitute borromeo's path into the bootstrap skill)
mkdir -p "$CLAUDE_DIR/skills/borromeo"
sed "s#__BORROMEO_HOME__#$BORROMEO_HOME#g" \
  "$BORROMEO_HOME/skills/borromeo/SKILL.md" >"$CLAUDE_DIR/skills/borromeo/SKILL.md"
cp -R "$BORROMEO_HOME/.claude/skills/borromeo-research" "$CLAUDE_DIR/skills/" 2>/dev/null || true
echo "installed skills: borromeo, borromeo-research -> $CLAUDE_DIR/skills/"

# 2. merge global hooks into ~/.claude/settings.json (preserve everything else)
PYTHONPATH="" python3 - "$CLAUDE_DIR/settings.json" "$BORROMEO_HOME" <<'PY'
import json
import os
import sys

path, bh = sys.argv[1], sys.argv[2]
settings = json.load(open(path)) if os.path.exists(path) else {}
hooks = settings.setdefault("hooks", {})


def entry(rel, timeout, matcher=None):
    hook = {"hooks": [{"type": "command", "command": f"{bh}/.claude/hooks/{rel}", "timeout": timeout}]}
    if matcher:
        hook["matcher"] = matcher
    return hook


spec = {
    "UserPromptSubmit": [entry("prompt_rewrite.sh", 30)],
    "Stop": [entry("stop_gate.sh", 600)],
    "PostToolUse": [entry("post_edit_format.sh", 60, "Edit|Write|MultiEdit")],
    "PreToolUse": [entry("pre_bash_guard.sh", 30, "Bash")],
}
for event, entries in spec.items():
    kept = [e for e in hooks.get(event, []) if bh not in json.dumps(e)]  # drop prior borromeo entries
    hooks[event] = kept + entries

json.dump(settings, open(path, "w"), indent=2)
print("merged global borromeo hooks into", path)
PY

echo
echo "borromeo is installed globally. In ANY new workspace:"
echo "  1. start Claude there"
echo "  2. say: use borromeo"
echo "The agent will init the workspace; the global hooks then govern it (they"
echo "no-op in projects without a borromeo.toml)."
