#!/usr/bin/env bash
# UserPromptSubmit hook — borromeo prompt rewriting (ENFORCED by borromeo, PERFORMED by the agent).
#
# If enabled in borromeo.toml ([prompt_rewriting].enabled), this injects a directive (built from
# the spine's [context]) instructing the wrapped agent to rewrite the user's prompt — preserve and
# improve intent per the declared context + best practices — and show the rewrite before acting.
# borromeo never rewrites the prompt itself; it enforces that the agent does it well. It asks the
# agent to refine the prompt, not to follow a fixed plan (agent autonomy preserved).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$HERE/../.." && pwd)}"

# stdout of a UserPromptSubmit hook is added to the agent's context.
PYTHONPATH="$ROOT/src" python3 - "$ROOT/borromeo.toml" <<'PY'
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
