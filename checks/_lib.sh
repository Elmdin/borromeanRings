#!/usr/bin/env bash
# borromeanRings — shared check library, sourced by every checks/NN_*.sh.
#
# Module secret it hides: the receipt format/location and the missing-tool
# policy. Stable contract it exposes to checks: emit_receipt / run_check, plus
# the exported $PROJECT_ROOT and $RECEIPT_DIR. Changing the receipt schema or a
# tool touches one place, not the gate (see docs/ARCHITECTURE.md).
set -uo pipefail

: "${PROJECT_ROOT:?_lib.sh: PROJECT_ROOT must be exported by verify.sh}"
: "${RECEIPT_DIR:?_lib.sh: RECEIPT_DIR must be exported by verify.sh}"
: "${BORROMEANRINGS_HOME:?_lib.sh: BORROMEANRINGS_HOME must be exported by verify.sh}"

# borromeanrings_project_cfg <Config-attr> — print a [project] value from the GOVERNED
# project's borromeanrings.toml (meta_harness is borromeanRings's own code at BORROMEANRINGS_HOME).
borromeanrings_project_cfg() {
  PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_ROOT/borromeanrings.toml" "$1" <<'PY'
import sys

from meta_harness.spine import load_config

print(getattr(load_config(sys.argv[1]), sys.argv[2]))
PY
}

# emit_receipt <id> <command> <exit_code> <log> <status> [extra_json]
# Writes the receipt with a tamper-evident content hash (see meta_harness.receipts):
# the digest covers every field + the log content, so a later status/log edit no
# longer matches. The verdict step re-verifies it. Evidence, not proof (ADR-0026).
emit_receipt() {
  PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$1" "$2" "$3" "$4" "$5" "$RECEIPT_DIR/$1.json" "${6:-}" <<'PY'
import json
import sys

from meta_harness.receipts import finalize_receipt

cid, command, exit_code, log, status, out, extra = sys.argv[1:8]
receipt = {
    "check": cid,
    "command": command,
    "exit_code": int(exit_code),
    "log": log,
    "status": status,
}
if extra:
    receipt.update(json.loads(extra))
try:
    with open(log, encoding="utf-8", errors="replace") as fh:
        log_text = fh.read()
except OSError:
    log_text = ""
receipt = finalize_receipt(receipt, log_text)
with open(out, "w") as fh:
    json.dump(receipt, fh, indent=2)
    fh.write("\n")
PY
}

# emit_noop <id> <command> <log>
# The check RAN but inspected NOTHING — no source yet, no Dockerfile, no rule declared.
# Distinct from "pass" on purpose: "I inspected nothing" must never be indistinguishable
# from "I inspected everything and found nothing wrong". Without this, a project whose
# src_dir points at an empty path reports a full green while every source-reading check
# is blind. Non-failing, but reported everywhere (gate output, verdict, self-status).
# See meta_harness.verdict.NON_FAILING_STATUSES and ADR-0049.
emit_noop() {
  emit_receipt "$1" "$2" 0 "$3" "noop"
}

# Exit code an embedded python step uses to signal "nothing to inspect". A heredoc's only
# channel back to bash is its exit code, and 0 there is indistinguishable from a real pass.
BORROMEANRINGS_NOOP_EXIT=3

# borromeanrings_status_for_code <exit_code> — map a check's exit code to a receipt status.
borromeanrings_status_for_code() {
  case "$1" in
    0) echo "pass" ;;
    "$BORROMEANRINGS_NOOP_EXIT") echo "noop" ;;
    *) echo "fail" ;;
  esac
}

# borromeanrings_run_bounded <log> <command>
# Run <command> from PROJECT_ROOT, stdout+stderr -> <log>, bounded by a wall-clock
# timeout so a hanging tool fails CLOSED instead of hanging the gate forever (and
# orphaning the child until the Stop-hook's own timeout). Uses coreutils `timeout`
# (or `gtimeout`); if neither is present it runs unbounded — no worse than before,
# never a hard error on exotic hosts. Limit is BORROMEANRINGS_CHECK_TIMEOUT seconds
# (default 300; set 0 to disable). On timeout the tool is SIGTERM'd, then SIGKILL'd
# after a short grace, and exit 124 is surfaced with a clear note in the log.
borromeanrings_run_bounded() {
  local log="$1" cmd="$2"
  local secs="${BORROMEANRINGS_CHECK_TIMEOUT:-300}"
  local tbin=""
  if command -v timeout >/dev/null 2>&1; then
    tbin="timeout"
  elif command -v gtimeout >/dev/null 2>&1; then
    tbin="gtimeout"
  fi

  local code
  if [ -n "$tbin" ] && [ "$secs" != "0" ]; then
    ( cd "$PROJECT_ROOT" && "$tbin" -k 10 "$secs" bash -c "$cmd" ) >"$log" 2>&1
    code=$?
    if [ "$code" -eq 124 ]; then
      printf '\nTIMED OUT after %ss (borromeanRings wall-clock limit; raise BORROMEANRINGS_CHECK_TIMEOUT if legitimate)\n' \
        "$secs" >>"$log"
    fi
  else
    ( cd "$PROJECT_ROOT" && bash -c "$cmd" ) >"$log" 2>&1
    code=$?
  fi
  return "$code"
}

# --- Language-lane helpers (checks/typescript, checks/go; SPEC-multi-language.md, ADR-0068)

# borromeanrings_source_count <src_dir> <suffix>... — how many source files of the lane's
# language sit under <src_dir>, counted by meta_harness.source_coherence.walk_sources so
# vendored trees (node_modules, vendor, dist, ...) never count as the project's own code.
borromeanrings_source_count() {
  local src_dir="$1"; shift
  PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_ROOT/$src_dir" "$@" <<'PY'
import sys
from pathlib import Path

from meta_harness.source_coherence import walk_sources

root = Path(sys.argv[1])
total = sum(len(walk_sources(root, suffix)) for suffix in sys.argv[2:]) if root.is_dir() else 0
print(total)
PY
}

# borromeanrings_lane_tool <name> — resolve a lane tool: the project's node_modules/.bin
# first (JavaScript tools are project-local by convention), then PATH. Prints the path
# and returns 0, or prints nothing and returns 1. Never installs anything.
borromeanrings_lane_tool() {
  local local_bin="$PROJECT_ROOT/node_modules/.bin/$1"
  if [ -x "$local_bin" ]; then
    echo "$local_bin"
    return 0
  fi
  command -v "$1" 2>/dev/null
}

# borromeanrings_noop_missing_tool <id> <command> <tool-label>
# A language lane's tool is the GOVERNED project's to provide (unlike Python's, which is
# borromeanRings's own dev dependency), so its absence is an honest "inspected nothing",
# reported as `noop` with the tool named — never an install, never a failed project.
borromeanrings_noop_missing_tool() {
  local log="$RECEIPT_DIR/$1.log"
  printf '%s not installed\n' "$3" >"$log"
  emit_noop "$1" "$2" "$log"
}

# borromeanrings_noop_greenfield <id> <command> <language> <src_dir>
# No source of the lane's language yet: nothing to inspect, say so (ADR-0049).
borromeanrings_noop_greenfield() {
  local log="$RECEIPT_DIR/$1.log"
  printf "no %s source in '%s' yet (greenfield) — nothing to inspect\n" "$3" "$4" >"$log"
  emit_noop "$1" "$2" "$log"
}

# run_check <id> <tool> <command>
# A missing required tool is a HARD failure (status "error"), never a silent skip.
run_check() {
  local id="$1" tool="$2" cmd="$3"
  local log="$RECEIPT_DIR/$id.log"
  if ! command -v "$tool" >/dev/null 2>&1; then
    printf "required tool '%s' not found on PATH\n" "$tool" >"$log"
    emit_receipt "$id" "$cmd" 127 "$log" "error"
    return 127
  fi
  local code
  borromeanrings_run_bounded "$log" "$cmd"
  code=$?
  local status="fail"
  [ "$code" -eq 0 ] && status="pass"
  emit_receipt "$id" "$cmd" "$code" "$log" "$status"
  return "$code"
}
