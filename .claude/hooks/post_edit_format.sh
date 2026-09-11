#!/usr/bin/env bash
# PostToolUse(Edit|Write|MultiEdit) — auto-format edited Python files so the
# format check never becomes the reason the Stop gate blocks. Cheap, per-edit.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/_lib.sh"

# Safe to install globally: do nothing unless this workspace is borromeanRings-governed.
[ -f "${CLAUDE_PROJECT_DIR:-$PWD}/borromeanrings.toml" ] || exit 0

# No dedupe needed here: formatting the same file twice is idempotent. The
# read stays bounded so an unclosed pipe can't orphan this shell.
input="$(borromeanrings_read_stdin)"
fp="$(printf '%s' "$input" | borromeanrings_py -c "import json,sys; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null || echo '')"

case "$fp" in
  *.py)
    if command -v ruff >/dev/null 2>&1; then
      ruff format "$fp" >/dev/null 2>&1 || true
    fi
    ;;
esac
exit 0
