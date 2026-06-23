#!/usr/bin/env bash
# Stop hook — borromeo's generate -> verify -> retry loop, bounded then escalating.
# A thin ADAPTER over the substrate-neutral gate. Works whether borromeo governs
# itself or is referenced from another project: it runs $BORROMEO_HOME/verify.sh
# against the project the agent is working in (CLAUDE_PROJECT_DIR).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BORROMEO_HOME="$(cd "$HERE/../.." && pwd)"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
CAP=3   # max retry attempts before escalating to the human

# Safe to install globally: do nothing unless this workspace is borromeo-governed.
[ -f "$PROJECT_DIR/borromeo.toml" ] || exit 0

input="$(cat)"
read -r stop_active session_id <<EOF
$(printf '%s' "$input" | python3 -c "import json,sys; d=json.load(sys.stdin); print(str(d.get('stop_hook_active', False)).lower(), d.get('session_id','default'))" 2>/dev/null || echo "false default")
EOF

if [ "$stop_active" = "true" ]; then
  exit 0
fi

# No-op guard: if the governed input state is identical to the last proven-green
# state (e.g. the agent only answered a question), skip the full gate — re-running
# it adds no assurance and wastes compute/tokens. Fail-closed: any error or change
# ⇒ fall through and run the gate.
if PYTHONPATH="$BORROMEO_HOME/src" python3 - "$PROJECT_DIR" <<'PY'
import sys
from pathlib import Path

try:
    from meta_harness.change_detect import should_skip_gate
    from meta_harness.spine import load_config

    project = Path(sys.argv[1])
    config = load_config(project / "borromeo.toml")
    sys.exit(0 if should_skip_gate(project, config) else 1)
except Exception:
    sys.exit(1)  # never skip on error — run the gate
PY
then
  exit 0
fi

attempt_dir="$PROJECT_DIR/.meta-harness/stop_attempts"
mkdir -p "$attempt_dir"
counter_file="$attempt_dir/$session_id"
attempts="$(cat "$counter_file" 2>/dev/null || echo 0)"

if summary="$(BORROMEO_PROJECT="$PROJECT_DIR" bash "$BORROMEO_HOME/verify.sh" 2>&1)"; then
  rm -f "$counter_file"
  exit 0
fi

attempts=$((attempts + 1))
printf '%s' "$attempts" >"$counter_file"

if [ "$attempts" -lt "$CAP" ]; then
  {
    echo "borromeo gate FAILED (attempt $attempts/$CAP). Fix the failing checks below, then finish again."
    echo "$summary"
  } >&2
  exit 2
fi

{
  echo "ESCALATION: borromeo gate failed $attempts times — handing control to the human."
  echo "$summary"
} >&2
rm -f "$counter_file"
exit 0
