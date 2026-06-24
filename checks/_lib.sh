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
emit_receipt() {
  python3 - "$1" "$2" "$3" "$4" "$5" "$RECEIPT_DIR/$1.json" "${6:-}" <<'PY'
import json
import sys

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
with open(out, "w") as fh:
    json.dump(receipt, fh, indent=2)
    fh.write("\n")
PY
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
