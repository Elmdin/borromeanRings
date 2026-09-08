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
fp="$(printf '%s' "$input" | python3 -c "import json,sys; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null || echo '')"

case "$fp" in
  *.py)
    if command -v ruff >/dev/null 2>&1; then
      ruff format "$fp" >/dev/null 2>&1 || true
    fi
    # Preventive layer for API-usage contracts (ADR-0054): tell the agent at the point of
    # writing, not at the end of the turn. Advisory here; 18_api_contracts is the backstop.
    BORROMEANRINGS_HOME="$(cd "$HERE/../.." && pwd)"
    PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
    PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_DIR/borromeanrings.toml" "$BORROMEANRINGS_HOME/contracts" "$fp" 2>/dev/null <<'PY' || true
import sys
from pathlib import Path

from meta_harness.api_contracts import check_source, load_pack, parse_rules
from meta_harness.spine import load_config

cfg_path, packs_dir, edited = sys.argv[1:4]
cfg = load_config(cfg_path)
if not cfg.api_contracts_rules and not cfg.api_contracts_packs:
    sys.exit(0)
rules = list(parse_rules(cfg.api_contracts_rules))
for pack in cfg.api_contracts_packs:
    rules.extend(load_pack(pack, packs_dir))
report = check_source(Path(edited).read_text(encoding="utf-8", errors="replace"), rules, edited)
if report.violations:
    print(f"borromeanRings API-contract violations in {edited} (the Stop gate will fail on these):")
    for v in report.violations:
        cite = f"  ({v.rule.source})" if v.rule.source else ""
        print(f"  - line {v.line} {v.rule.describe()} — {v.message}{cite}")
PY
    ;;
esac
exit 0
