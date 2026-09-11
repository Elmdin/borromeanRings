#!/usr/bin/env bash
# Stop hook — borromeanRings's generate -> verify -> retry loop, bounded then escalating.
#
# This is the `claude-code` GENERATOR ADAPTER (SPEC-generator.md §3.1): the wrapped agent
# sits in the generator's seat, the Stop event is its "I have written a change", the
# stderr text is the retry request, and the exit code (2 = retry, 0 = done/escalated) is
# how the substrate is told which. The loop's rules are NOT this script's: CAP and the
# decision live in meta_harness.generator, shared with the headless driver (generate.sh).
#
# A thin ADAPTER over the substrate-neutral gate. Works whether borromeanRings governs
# itself or is referenced from another project: it runs $BORROMEANRINGS_HOME/verify.sh
# against the project the agent is working in (CLAUDE_PROJECT_DIR).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BORROMEANRINGS_HOME="$(cd "$HERE/../.." && pwd)"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
. "$HERE/_lib.sh"

# Safe to install globally: do nothing unless this workspace is borromeanRings-governed.
# This stays the FIRST thing the hook does — an ungoverned workspace must not pay for a
# python3 start on every Stop.
[ -f "$PROJECT_DIR/borromeanrings.toml" ] || exit 0

# The retry bound is declared in ONE place (meta_harness.generator.CAP) and read by both
# generator adapters, so neither can drift from the other or quietly grant itself a
# fourth attempt. Unreadable ⇒ fail closed to a single attempt: the smallest bound still
# escalates to the human, where guessing an unbounded one never would.
CAP="$(PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 -c \
  'from meta_harness.generator import CAP; print(CAP)' 2>/dev/null || true)"
case "$CAP" in '' | *[!0-9]* | 0) CAP=1 ;; esac

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

attempt_dir="$PROJECT_DIR/.meta-harness/stop_attempts"
mkdir -p "$attempt_dir"
counter_file="$attempt_dir/$session_id"
attempts="$(cat "$counter_file" 2>/dev/null || echo 0)"

# Bounded: a hanging check inside the gate must fail closed here, not park this
# hook (and its children) until the substrate's own hook timeout — or forever.
# Keep the bound under the Stop hook's 600s budget in .claude/settings.json.
#
# BORROMEANRINGS_GENERATOR is this adapter's self-declared provenance, recorded in the
# verdict as intent.generator — like a git author line, and worth exactly as much. The
# gate makes no decision on it (ADR-0049: the generator's word is not evidence); it only
# records who claimed to write the change it judged. See ADR-0071 §4.
summary="$(BORROMEANRINGS_PROJECT="$PROJECT_DIR" \
  BORROMEANRINGS_GENERATOR="claude-code:$session_id" borromeanrings_bounded \
  "${BORROMEANRINGS_GATE_TIMEOUT:-540}" bash "$BORROMEANRINGS_HOME/verify.sh" 2>&1)"
gate_code=$?
if [ "$gate_code" -eq 0 ]; then
  rm -f "$counter_file"
  exit 0
fi
if [ "$gate_code" -eq 124 ]; then
  summary="$summary
(gate TIMED OUT after ${BORROMEANRINGS_GATE_TIMEOUT:-540}s wall-clock — a check is hanging; treated as FAIL, fail-closed)"
fi

attempts=$((attempts + 1))
printf '%s' "$attempts" >"$counter_file"

if [ "$attempts" -lt "$CAP" ]; then
  {
    echo "borromeanRings gate FAILED (attempt $attempts/$CAP). Fix the failing checks below, then finish again."
    echo "$summary"
  } >&2
  exit 2
fi

{
  echo "ESCALATION: borromeanRings gate failed $attempts times — handing control to the human."
  echo "$summary"
} >&2
rm -f "$counter_file"
exit 0
