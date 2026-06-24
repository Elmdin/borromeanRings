#!/usr/bin/env bash
# borromeanRings init <target> — set up borromeanRings to govern a target project BY REFERENCE.
#
# Writes a starter borromeanrings.toml + .claude/settings.json into <target>; the hooks
# point back at THIS borromeanRings ($BORROMEANRINGS_HOME). Nothing is copied — borromeanRings's code
# stays here, and any agent prompted in <target> is governed by it.
set -uo pipefail

BORROMEANRINGS_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:?usage: ./init.sh <target-dir>}"
TARGET="$(cd "$TARGET" && pwd)"

if [ ! -f "$TARGET/borromeanrings.toml" ]; then
  cat >"$TARGET/borromeanrings.toml" <<'EOF'
[project]
package = ""        # importable package name (optional; "" skips the import check)
src_dir = "src"
tests_dir = "tests"

[checks]
required = ["00_build", "05_hygiene", "10_format", "20_lint", "30_typecheck", "40_test", "50_security"]

[context]
account = ""
value_priorities = ["correctness", "security", "maintainability", "performance"]

[prompt_rewriting]
enabled = true

[hygiene]
# Engineering-surround files this project must have. Empty by default so a fresh/greenfield
# project starts GREEN; add requirements as it matures, e.g.:
#   requires = ["README.md", "LICENSE", ".github/workflows", "Dockerfile"]
requires = []
EOF
  echo "wrote $TARGET/borromeanrings.toml  (edit it for your project)"
else
  echo "$TARGET/borromeanrings.toml already exists — leaving it"
fi

mkdir -p "$TARGET/.claude"
cat >"$TARGET/.claude/settings.json" <<EOF
{
  "hooks": {
    "UserPromptSubmit": [ { "hooks": [ { "type": "command", "command": "$BORROMEANRINGS_HOME/.claude/hooks/prompt_rewrite.sh", "timeout": 30 } ] } ],
    "Stop": [ { "hooks": [ { "type": "command", "command": "$BORROMEANRINGS_HOME/.claude/hooks/stop_gate.sh", "timeout": 600 } ] } ],
    "PostToolUse": [ { "matcher": "Edit|Write|MultiEdit", "hooks": [ { "type": "command", "command": "$BORROMEANRINGS_HOME/.claude/hooks/post_edit_format.sh", "timeout": 60 } ] } ],
    "PreToolUse": [ { "matcher": "Bash", "hooks": [ { "type": "command", "command": "$BORROMEANRINGS_HOME/.claude/hooks/pre_bash_guard.sh", "timeout": 30 } ] } ]
  }
}
EOF
echo "wrote $TARGET/.claude/settings.json  (hooks reference borromeanRings at $BORROMEANRINGS_HOME)"

# Install borromeanRings's skills (e.g. borromeanrings-research) so a Claude session in the target finds them.
if [ -d "$BORROMEANRINGS_HOME/.claude/skills" ]; then
  mkdir -p "$TARGET/.claude/skills"
  cp -R "$BORROMEANRINGS_HOME/.claude/skills/." "$TARGET/.claude/skills/"
  echo "installed borromeanRings skills into $TARGET/.claude/skills/ (e.g. borromeanrings-research)"
fi

echo
echo "borromeanRings now governs $TARGET. Run the gate with:"
echo "  cd '$TARGET' && '$BORROMEANRINGS_HOME/verify.sh'"
echo "  (or: BORROMEANRINGS_PROJECT='$TARGET' '$BORROMEANRINGS_HOME/verify.sh')"
