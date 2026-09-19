#!/usr/bin/env bash
# borromeanRings — STATUS.
#
# Bare invocation reports THIS project: whether it is governed, whether enforcement is
# actually on (hooks wired vs. disabled), the last verdict, and — the part a raw verdict
# hides — how many of those checks inspected NOTHING (ADR-0049).
#
# The portfolio roster is opt-in (`--all`), not the default: scanning every governed
# project under $HOME answers a fleet question nobody asked when they wanted to know
# about the project in front of them.
#
# Usage:
#   ./status.sh                     # THIS project only (default)
#   ./status.sh --all [ROOT ...]    # portfolio roster (default root: $HOME)
#   ./status.sh PATH ...            # roster over the named roots
#   ./status.sh --run [PATH ...]    # re-gate first (authoritative, slower)
#   ./status.sh --list [PATH ...]   # just print discovered project paths
#   ./status.sh --swe               # + the SWE-state report (practises / lacks / adopt next)
#   ./status.sh --advise            # + the approach advice (questions to ask, approaches that fit)
#
# Advisory, not a gate: the read-only report always exits 0. Under --run, the exit code
# is non-zero if any re-gated project fails (so it is CI-usable). See SPEC-status.md,
# ADR-0046.
set -uo pipefail

BORROMEANRINGS_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export BORROMEANRINGS_HOME
# Which borromeanRings is installed here, computed the same way verify.sh does (ADR-0048).
# The self-report contrasts it with the version that produced the last verdict, which is
# how you notice the harness moved since it last verified this project.
HARNESS_VERSION="$(git -C "$BORROMEANRINGS_HOME" describe --tags --always --dirty 2>/dev/null || true)"
[ -n "$HARNESS_VERSION" ] || HARNESS_VERSION="$(cat "$BORROMEANRINGS_HOME/VERSION" 2>/dev/null || echo unknown)"
export HARNESS_VERSION
# Invoke the module's main() via -c (house convention; keeps status.py free of an
# uncoverable __main__ block). sys.argv[1:] forwards this function's arguments.
PY() {
  PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 -c \
    'import sys; from meta_harness.status import main; sys.exit(main(sys.argv[1:]))' "$@"
}

RUN=0
SWE=0
ADVISE=0
args=()
for a in "$@"; do
  case "$a" in
    --run) RUN=1 ;;
    --swe) SWE=1 ;;
    --advise) ADVISE=1 ;;
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
# What the project practises, lacks and should adopt next — the sibling view the
# self-status block does not answer (SPEC-swe-state.md, ADR-0067). Advisory: never
# changes the exit code.
[ "$SWE" = "1" ] && bash "$BORROMEANRINGS_HOME/swe-state.sh"
# The right questions and approaches before building — advisory, never a gate
# (SPEC-approach-advisor.md, ADR-0072). Never changes the exit code.
[ "$ADVISE" = "1" ] && bash "$BORROMEANRINGS_HOME/advise.sh"
exit "$rc"
