#!/usr/bin/env bash
# UserPromptSubmit hook — borromeo prompt rewriting (ENFORCED by borromeo, PERFORMED by the agent).
#
# If enabled in the governed project's borromeo.toml ([prompt_rewriting].enabled), injects a
# directive (built from that project's [context]) telling the agent to rewrite the user's prompt
# and show the rewrite before acting. Works referenced from another project: meta_harness comes
# from $BORROMEO_HOME; the config + context come from the governed project (CLAUDE_PROJECT_DIR).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BORROMEO_HOME="$(cd "$HERE/../.." && pwd)"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"

[ -f "$PROJECT_DIR/borromeo.toml" ] || exit 0

PYTHONPATH="$BORROMEO_HOME/src" python3 - "$PROJECT_DIR/borromeo.toml" <<'PY'
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
