#!/usr/bin/env bash
# PostToolUse(Edit|Write|MultiEdit) — auto-format edited Python files so the
# format check never becomes the reason the Stop gate blocks. Cheap, per-edit.
set -uo pipefail

input="$(cat)"
fp="$(printf '%s' "$input" | python3 -c "import json,sys; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null || echo '')"

case "$fp" in
  *.py)
    if command -v ruff >/dev/null 2>&1; then
      ruff format "$fp" >/dev/null 2>&1 || true
    fi
    ;;
esac
exit 0
