#!/usr/bin/env bash
# SessionStart hook — re-inject the governance brief after compaction (or a resume).
#
# Whatever the compaction summary kept, the post-compaction context starts from the
# evidence on disk: last verdict, open obligations, enforcement mode, identity policy.
# Plain stdout from a SessionStart hook is added to the model's context; that is the
# whole mechanism. Reads fresh state rather than the PreCompact snapshot, so a gate that
# ran between the two is reflected. Advisory; never blocks. ADR-0053 (#137).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BORROMEANRINGS_HOME="$(cd "$HERE/../.." && pwd)"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
. "$HERE/_lib.sh"

[ -f "$PROJECT_DIR/borromeanrings.toml" ] || exit 0

input="$(borromeanrings_read_stdin)"
trigger="$(printf '%s' "$input" | python3 -c "import json,sys; print(json.load(sys.stdin).get('trigger','unknown'))" 2>/dev/null || echo unknown)"
# Only the events where state was just summarised or reloaded; a fresh startup already
# gets the project's CLAUDE.md and the status skill.
case "$trigger" in compact|resume) ;; *) exit 0 ;; esac

PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_DIR" "$BORROMEANRINGS_HOME" <<'PY' || exit 0
import sys

from meta_harness.compaction_brief import gather_brief

print(gather_brief(sys.argv[1], sys.argv[2]))
PY
exit 0
