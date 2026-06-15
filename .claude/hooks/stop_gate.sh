#!/usr/bin/env bash
# Stop hook — borromeo's generate -> verify -> retry loop, bounded then escalating.
# This is a thin ADAPTER over the substrate-neutral gate (verify.sh): it only
# translates Claude Code's Stop event into a gate run + loop decision. Swapping
# substrates means a new adapter, not a change to the gate. (docs/ARCHITECTURE.md)
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$HERE/../.." && pwd)}"
CAP=3   # max retry attempts before escalating to the human

input="$(cat)"
read -r stop_active session_id <<EOF
$(printf '%s' "$input" | python3 -c "import json,sys; d=json.load(sys.stdin); print(str(d.get('stop_hook_active', False)).lower(), d.get('session_id','default'))" 2>/dev/null || echo "false default")
EOF

# Documented infinite-loop escape hatch.
if [ "$stop_active" = "true" ]; then
  exit 0
fi

attempt_dir="$PROJECT_DIR/.meta-harness/stop_attempts"
mkdir -p "$attempt_dir"
counter_file="$attempt_dir/$session_id"
attempts="$(cat "$counter_file" 2>/dev/null || echo 0)"

if summary="$(bash "$PROJECT_DIR/verify.sh" 2>&1)"; then
  rm -f "$counter_file"            # PASS — reset and allow the stop.
  exit 0
fi

attempts=$((attempts + 1))
printf '%s' "$attempts" >"$counter_file"

if [ "$attempts" -lt "$CAP" ]; then
  {
    echo "borromeo gate FAILED (attempt $attempts/$CAP). Fix the failing checks below, then finish again."
    echo "$summary"
  } >&2
  exit 2                           # block the stop; feed failures back to the agent
fi

{
  echo "ESCALATION: borromeo gate failed $attempts times — handing control to the human."
  echo "$summary"
} >&2
rm -f "$counter_file"
exit 0                             # stop; never loop unbounded
