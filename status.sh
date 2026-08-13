#!/usr/bin/env bash
# borromeanRings — PORTFOLIO STATUS (the roster view).
#
# One table across every governed project: which are governed, how many checks each
# enforces, whether the last gate was green, config drift, and whether it is a git repo.
# Complements verify.sh (which gates ONE project). Reuses the single sources of truth —
# load_config, plan_adoption (drift), and each project's persisted last verdict.
#
# Usage:
#   ./status.sh [PATH ...]          # read last-known verdicts (fast; default root: $HOME)
#   ./status.sh --run [PATH ...]    # re-gate each project first (authoritative, slower)
#   ./status.sh --list [PATH ...]   # just print discovered project paths
#
# Advisory, not a gate: the read-only report always exits 0. Under --run, the exit code
# is non-zero if any re-gated project fails (so it is CI-usable). See SPEC-status.md,
# ADR-0046.
set -uo pipefail

BORROMEANRINGS_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export BORROMEANRINGS_HOME
# Invoke the module's main() via -c (house convention; keeps status.py free of an
# uncoverable __main__ block). sys.argv[1:] forwards this function's arguments.
PY() {
  PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 -c \
    'import sys; from meta_harness.status import main; sys.exit(main(sys.argv[1:]))' "$@"
}

RUN=0
args=()
for a in "$@"; do
  case "$a" in
    --run) RUN=1 ;;
    *) args+=("$a") ;;
  esac
done

rc=0
if [ "$RUN" = "1" ]; then
  # Re-gate each discovered project so its persisted verdict is fresh, then render.
  while IFS= read -r proj; do
    [ -n "$proj" ] || continue
    echo "  re-gating ${proj} ..." >&2
    if ! BORROMEANRINGS_PROJECT="$proj" bash "$BORROMEANRINGS_HOME/verify.sh" >/dev/null 2>&1; then
      rc=1
      # Surface the failure (the render below shows last-known state, which may be
      # stale if the gate itself crashed before persisting a fresh verdict).
      echo "  ! gate did not pass for ${proj} — inspect: BORROMEANRINGS_PROJECT=${proj} ${BORROMEANRINGS_HOME}/verify.sh" >&2
    fi
  done < <(PY --list "${args[@]}")
fi

PY "${args[@]}"
exit "$rc"
