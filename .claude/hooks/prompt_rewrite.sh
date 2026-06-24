#!/usr/bin/env bash
# UserPromptSubmit hook — borromeanRings prompt rewriting (ENFORCED by borromeanRings, PERFORMED by the agent).
#
# If enabled in the governed project's borromeanrings.toml ([prompt_rewriting].enabled), injects a
# directive (built from that project's [context]) telling the agent to rewrite the user's prompt
# and show the rewrite before acting. Works referenced from another project: meta_harness comes
# from $BORROMEANRINGS_HOME; the config + context come from the governed project (CLAUDE_PROJECT_DIR).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BORROMEANRINGS_HOME="$(cd "$HERE/../.." && pwd)"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"

[ -f "$PROJECT_DIR/borromeanrings.toml" ] || exit 0

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
