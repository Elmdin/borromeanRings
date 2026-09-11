#!/usr/bin/env bash
# Stop hook — borromeanRings's generate -> verify -> retry loop, bounded then escalating.
# A thin ADAPTER over the substrate-neutral gate. Works whether borromeanRings governs
# itself or is referenced from another project: it runs $BORROMEANRINGS_HOME/verify.sh
# against the project the agent is working in (CLAUDE_PROJECT_DIR).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BORROMEANRINGS_HOME="$(cd "$HERE/../.." && pwd)"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
CAP=3   # max retry attempts before escalating to the human
. "$HERE/_lib.sh"

# Safe to install globally: do nothing unless this workspace is borromeanRings-governed.
[ -f "$PROJECT_DIR/borromeanrings.toml" ] || exit 0

input="$(borromeanrings_read_stdin)"
read -r stop_active session_id <<EOF
$(printf '%s' "$input" | python3 -c "import json,sys; d=json.load(sys.stdin); print(str(d.get('stop_hook_active', False)).lower(), d.get('session_id','default'))" 2>/dev/null || echo "false default")
EOF

if [ "$stop_active" = "true" ]; then
  exit 0
fi

# Duplicate-registration dedupe: with both a project-level and the user-level
# hook entry active, this script runs TWICE per Stop — the gate would run twice
# and the retry counter below would double-count toward CAP. First claim wins;
# the winner RELEASES on exit so the claim only shadows the concurrent
# duplicate (and, briefly, a crashed run) — never the next legitimate Stop,
# however fast the retry loop turns around. Losing must not release the
# winner's marker, so the trap is set only after the claim is won.
borromeanrings_claim stop "$session_id" || exit 0
trap 'borromeanrings_release stop "$session_id"' EXIT TERM INT

# No-op guard: if the governed input state is identical to the last proven-green
# state (e.g. the agent only answered a question), skip the full gate — re-running
# it adds no assurance and wastes compute/tokens. Fail-closed: any error or change
# ⇒ fall through and run the gate.
if PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_DIR" <<'PY'
import sys
from pathlib import Path

try:
    from meta_harness.change_detect import should_skip_gate
    from meta_harness.spine import load_config

    project = Path(sys.argv[1])
    config = load_config(project / "borromeanrings.toml")
    sys.exit(0 if should_skip_gate(project, config) else 1)
except Exception:
    sys.exit(1)  # never skip on error — run the gate
PY
then
  exit 0
fi

# The retry count lives OUTSIDE the governed tree, under
# $XDG_STATE_HOME/borromeanrings/<project-digest>/ (ADR-0079, #218): kept in the
# tree, one `rm` by the agent it governs bought unlimited attempts. The decisions
# (where, how much, retry or escalate, legacy migration) are in
# meta_harness.retry_state; this adapter only dispatches on its one-line verdict.
# That defeats a same-TREE adversary. A same-USER one can still write there.
borromeanrings_retry_state() {
  PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$@" 2>/dev/null <<'PY'
import os
import sys

# `python3 -` puts the working directory -- the governed project -- first on
# sys.path, so an in-tree `meta_harness/` package would replace this logic.
sys.path[:] = [p for p in sys.path if p not in ("", ".")]
from meta_harness.retry_state import main

sys.exit(main(sys.argv[1:], os.environ))
PY
}

# Bounded: a hanging check inside the gate must fail closed here, not park this
# hook (and its children) until the substrate's own hook timeout — or forever.
# Keep the bound under the Stop hook's 600s budget in .claude/settings.json.
summary="$(BORROMEANRINGS_PROJECT="$PROJECT_DIR" borromeanrings_bounded \
  "${BORROMEANRINGS_GATE_TIMEOUT:-540}" bash "$BORROMEANRINGS_HOME/verify.sh" 2>&1)"
gate_code=$?
if [ "$gate_code" -eq 0 ]; then
  borromeanrings_retry_state clear "$PROJECT_DIR" "$session_id" >/dev/null
  exit 0
fi
if [ "$gate_code" -eq 124 ]; then
  summary="$summary
(gate TIMED OUT after ${BORROMEANRINGS_GATE_TIMEOUT:-540}s wall-clock — a check is hanging; treated as FAIL, fail-closed)"
fi

read -r verdict detail <<EOF
$(borromeanrings_retry_state fail "$PROJECT_DIR" "$session_id" "$CAP")
EOF

case "$verdict" in
  retry)
    {
      echo "borromeanRings gate FAILED (attempt $detail/$CAP). Fix the failing checks below, then finish again."
      echo "$summary"
    } >&2
    exit 2
    ;;
  escalate)
    {
      echo "ESCALATION: borromeanRings gate failed $detail times — handing control to the human."
      echo "$summary"
    } >&2
    exit 0
    ;;
  *)
    # Fail closed: without a durable count every Stop would read as attempt 1,
    # which is the unbounded loop this bound exists to stop. Escalate now.
    {
      echo "ESCALATION: borromeanRings could not record the retry count (${detail:-no answer from meta_harness.retry_state}) — without it the retry bound cannot hold, so control goes to the human now instead of retrying without a limit."
      echo "$summary"
    } >&2
    exit 0
    ;;
esac
