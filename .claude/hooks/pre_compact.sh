#!/usr/bin/env bash
# PreCompact hook — snapshot the governance brief before context is summarised.
#
# Compaction is where governance state goes silently missing: the last verdict, the
# obligations still open, the identity policy. PreCompact cannot inject context (the
# event supports no additionalContext), so this hook records the brief as evidence at the
# moment of compaction; the SessionStart(compact) hook re-injects a fresh one afterwards.
# Never blocks compaction. See docs/specs/SPEC-compaction-brief.md, ADR-0053 (#137).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BORROMEANRINGS_HOME="$(cd "$HERE/../.." && pwd)"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
. "$HERE/_lib.sh"

# Safe to install globally: do nothing unless this workspace is borromeanRings-governed.
[ -f "$PROJECT_DIR/borromeanrings.toml" ] || exit 0

input="$(borromeanrings_read_stdin)"
trigger="$(printf '%s' "$input" | python3 -c "import json,sys; print(json.load(sys.stdin).get('trigger','unknown'))" 2>/dev/null || echo unknown)"

out_dir="$PROJECT_DIR/.meta-harness"
mkdir -p "$out_dir" 2>/dev/null || exit 0
PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_DIR" "$BORROMEANRINGS_HOME" "$trigger" "$out_dir/compaction_brief.txt" <<'PY' || exit 0
import sys
from datetime import datetime, timezone
from pathlib import Path

from meta_harness.compaction_brief import gather_brief

project, home, trigger, out = sys.argv[1:5]
stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
brief = gather_brief(project, home)
Path(out).write_text(f"# snapshot {stamp} (trigger: {trigger})\n{brief}\n", encoding="utf-8")
PY
exit 0
