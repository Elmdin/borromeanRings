# Shared helpers for borromeanRings's substrate hooks. Sourced, not executed.
# Callers using borromeanrings_claim/borromeanrings_release define
# BORROMEANRINGS_HOME and PROJECT_DIR before calling them; the other helpers
# need neither.

# borromeanrings_bounded <secs> <command...>
# Run <command> under a wall-clock bound via coreutils `timeout` (or `gtimeout`).
# If neither exists, or <secs> is 0, run unbounded — no worse than before, never
# a hard error on exotic hosts (same contract as checks/_lib.sh).
borromeanrings_bounded() {
  local secs="$1" tbin=""
  shift
  if command -v timeout >/dev/null 2>&1; then
    tbin="timeout"
  elif command -v gtimeout >/dev/null 2>&1; then
    tbin="gtimeout"
  fi
  if [ -n "$tbin" ] && [ "$secs" != "0" ]; then
    "$tbin" -k 2 "$secs" "$@"
  else
    "$@"
  fi
}

# borromeanrings_read_stdin — echo the hook payload from stdin, BOUNDED.
# Regression guard for the orphaned-shell bug: if the substrate never closes
# the pipe's write end, an unbounded `cat` blocks forever and the hook's shell
# sits idle in the process table for the rest of the session. Bound the read
# (BORROMEANRINGS_HOOK_STDIN_TIMEOUT seconds, default 5 — the payload normally
# arrives in milliseconds) and fail open with whatever was received.
borromeanrings_read_stdin() {
  borromeanrings_bounded "${BORROMEANRINGS_HOOK_STDIN_TIMEOUT:-5}" cat 2>/dev/null || true
}

# borromeanrings_claim <event> <key> — succeed if THIS invocation should handle
# the event occurrence. The same hook can be registered twice (project-level +
# the user-level install-global.sh entry); non-idempotent hooks call this so
# the duplicate yields. First-writer-wins with a freshness window
# (BORROMEANRINGS_HOOK_DEDUPE_WINDOW seconds, default 5). Fail-open by
# construction: the verdict is the script's OUTPUT — the caller yields only on
# an explicit "yield", so a dedupe infrastructure failure (python missing,
# marker dir unwritable, crash) means "proceed", never "skip governance".
borromeanrings_claim() {
  local verdict
  verdict="$(PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_DIR" "$1" "$2" \
    "${BORROMEANRINGS_HOOK_DEDUPE_WINDOW:-5}" 2>/dev/null <<'PY'
import sys
from pathlib import Path

try:
    from meta_harness.hook_dedupe import claim

    markers = Path(sys.argv[1]) / ".meta-harness" / "hook_markers"
    ok = claim(markers, sys.argv[2], sys.argv[3], window_seconds=float(sys.argv[4]))
except Exception:
    ok = True  # fail-open: never drop governance over a dedupe error
print("proceed" if ok else "yield")
PY
  )" || verdict="proceed"
  [ "$verdict" != "yield" ]
}

# borromeanrings_release <event> <key> — drop this invocation's claim so the
# next legitimate occurrence starts fresh (see hook_dedupe.release). Call it
# ONLY after winning the claim; best-effort, never fails the hook.
borromeanrings_release() {
  PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_DIR" "$1" "$2" 2>/dev/null <<'PY' || true
import sys
from pathlib import Path

try:
    from meta_harness.hook_dedupe import release

    release(Path(sys.argv[1]) / ".meta-harness" / "hook_markers", sys.argv[2], sys.argv[3])
except Exception:
    pass  # a lingering marker just expires via the freshness window
PY
}
