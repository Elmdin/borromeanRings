#!/usr/bin/env bash
# borromeo init <target> — set up borromeo to govern a target project BY REFERENCE.
#
# Writes a starter borromeo.toml + .claude/settings.json into <target>; the hooks
# point back at THIS borromeo ($BORROMEO_HOME). Nothing is copied — borromeo's code
# stays here, and any agent prompted in <target> is governed by it.
set -uo pipefail

BORROMEO_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:?usage: ./init.sh <target-dir>}"
TARGET="$(cd "$TARGET" && pwd)"

if [ ! -f "$TARGET/borromeo.toml" ]; then
  cat >"$TARGET/borromeo.toml" <<'EOF'
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
requires = ["README.md"]
EOF
  echo "wrote $TARGET/borromeo.toml  (edit it for your project)"
else
  echo "$TARGET/borromeo.toml already exists — leaving it"
fi

mkdir -p "$TARGET/.claude"
cat >"$TARGET/.claude/settings.json" <<EOF
{
  "hooks": {
    "UserPromptSubmit": [ { "hooks": [ { "type": "command", "command": "$BORROMEO_HOME/.claude/hooks/prompt_rewrite.sh", "timeout": 30 } ] } ],
    "Stop": [ { "hooks": [ { "type": "command", "command": "$BORROMEO_HOME/.claude/hooks/stop_gate.sh", "timeout": 600 } ] } ],
    "PostToolUse": [ { "matcher": "Edit|Write|MultiEdit", "hooks": [ { "type": "command", "command": "$BORROMEO_HOME/.claude/hooks/post_edit_format.sh", "timeout": 60 } ] } ],
    "PreToolUse": [ { "matcher": "Bash", "hooks": [ { "type": "command", "command": "$BORROMEO_HOME/.claude/hooks/pre_bash_guard.sh", "timeout": 30 } ] } ]
  }
}
EOF
echo "wrote $TARGET/.claude/settings.json  (hooks reference borromeo at $BORROMEO_HOME)"
echo
echo "borromeo now governs $TARGET. Run the gate with:"
echo "  cd '$TARGET' && '$BORROMEO_HOME/verify.sh'"
echo "  (or: BORROMEO_PROJECT='$TARGET' '$BORROMEO_HOME/verify.sh')"
