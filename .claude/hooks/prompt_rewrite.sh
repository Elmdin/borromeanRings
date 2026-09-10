#!/usr/bin/env bash
# UserPromptSubmit hook — borromeanRings prompt rewriting (ENFORCED by borromeanRings, PERFORMED by the agent).
#
# If enabled in the governed project's borromeanrings.toml ([prompt_rewriting].enabled), injects a
# directive (built from that project's [context]) telling the agent to rewrite the user's prompt
# and open its reply with a one-line "Reading this as:" rendering of it. Works referenced from
# another project: meta_harness comes from $BORROMEANRINGS_HOME; the config + context come from
# the governed project (CLAUDE_PROJECT_DIR).
#
# The payload read is BOUNDED (an unclosed stdin pipe must not orphan this shell) and the
# directive is DEDUPED per (session, prompt): with both a project-level and the user-level
# registration active this script runs twice per prompt, and the directive must inject once.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BORROMEANRINGS_HOME="$(cd "$HERE/../.." && pwd)"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
. "$HERE/_lib.sh"

[ -f "$PROJECT_DIR/borromeanrings.toml" ] || exit 0

input="$(borromeanrings_read_stdin)"
if [ -n "$input" ]; then
  key="$(printf '%s' "$input" | python3 -c "
import hashlib, json, sys
d = json.load(sys.stdin)
digest = hashlib.sha256(d.get('prompt', '').encode()).hexdigest()[:16]
print(f\"{d.get('session_id', 'default')}:{digest}\")
" 2>/dev/null || echo '')"
  if [ -n "$key" ]; then
    borromeanrings_claim user_prompt_submit "$key" || exit 0
  fi
fi
# Empty/unparseable payload ⇒ no dedupe key ⇒ emit anyway (fail-open: a timed-out
# read must never silently drop the directive).

# Also the one-line charter reminder (ADR-0063): when [charter] is enabled but the
# charter file is absent, say so — under 120 bytes, advisory, independent of
# [prompt_rewriting].enabled. Validity is the gate's job (22_charter), not this hook's.
PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_DIR/borromeanrings.toml" "$PROJECT_DIR" <<'PY'
import sys
from pathlib import Path

try:
    from meta_harness.charter import missing_charter_reminder
    from meta_harness.prompt_rewrite import build_directive
    from meta_harness.spine import load_config

    config = load_config(sys.argv[1])
except Exception:
    sys.exit(0)  # missing/invalid config → do nothing; never block the user's prompt

if config.prompt_rewriting_enabled:
    print(build_directive(config.context))
if config.charter_enabled and not (Path(sys.argv[2]) / config.charter_path).is_file():
    print(missing_charter_reminder(config.charter_path))
PY
exit 0
