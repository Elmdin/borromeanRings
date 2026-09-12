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

# borromeo.toml = pre-rename config name, still governed (issue #62, docs/RENAME.md).
{ [ -f "$PROJECT_DIR/borromeanrings.toml" ] || [ -f "$PROJECT_DIR/borromeo.toml" ]; } || exit 0

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

PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_DIR/borromeanrings.toml" <<'PY'
import sys

try:
    from meta_harness.prompt_rewrite import build_directive
    from meta_harness.spine import load_config

    config = load_config(sys.argv[1])
except Exception:
    sys.exit(0)  # missing/invalid config → do nothing; never block the user's prompt

if config.prompt_rewriting_enabled:
    print(build_directive(config.context))
PY
exit 0
