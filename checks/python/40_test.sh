#!/usr/bin/env bash
# Test + coverage RATCHET (not an absolute %): tests must pass, and coverage
# may not regress below the recorded baseline. Coverage is recorded in the
# receipt. Mutation testing (the real oracle-strength signal) is deferred.
# See docs/REQUIREMENTS.md QAS-7 and docs/TEST-PLAN.md §5.
#
# Two lanes (ADR-0081). On the FAST (interactive) lane — verify.sh --fast, which the
# Stop hook runs — this check runs only the paths the project declared in
# [test].fast_paths, without coverage, and marks the receipt as a partial result. On
# every other lane, and in any project that declared no fast paths, it runs the whole
# suite with the coverage ratchet exactly as it always has.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="40_test"
log="$RECEIPT_DIR/$id.log"
covjson="$RECEIPT_DIR/coverage.json"
baseline_file="$PROJECT_ROOT/.borromeanrings-coverage-baseline"
cmd="pytest --cov (ratchet vs baseline)"

# Which pytest paths this lane runs. meta_harness.lane owns that decision and validates
# the declared paths (they reach a command line); this check only asks for the arguments
# and gets "" when there is no fast lane to take — in which case nothing below changes.
# A non-zero exit is a bad declaration: fail closed rather than silently run everything.
if ! fast_args="$(PYTHONPATH="$BORROMEANRINGS_HOME/src" borromeanrings_py - \
  "$PROJECT_ROOT/borromeanrings.toml" 2>"$log" <<'PY'
import os
import sys

from meta_harness.lane import fast_pytest_args, lane_from_env
from meta_harness.spine import load_config

print(fast_pytest_args(load_config(sys.argv[1]), lane_from_env(os.environ)))
PY
)"; then
  # The rejection (with the offending path) landed in $log via stderr — keep it as the
  # evidence and add the instruction, rather than spilling a traceback on the console.
  printf "\ninvalid [test].fast_paths in borromeanrings.toml — fix the declaration\n" >>"$log"
  emit_receipt "$id" "$cmd" 1 "$log" "fail"
  exit 1
fi

if ! python3 -m pytest --version >/dev/null 2>&1; then
  printf "required tool 'pytest' (python3 -m pytest) not available\n" >"$log"
  emit_receipt "$id" "$cmd" 127 "$log" "error"
  exit 127
fi

# Erase stale coverage data first. A crashed/interrupted prior run can leave
# orphan parallel files (.coverage.<host>.<pid>) that poison coverage's combine
# step ("no such table: other_db.file") and fail the gate for a non-code reason.
# The gate must fail only on real regressions, never on leftover artifacts.
rm -f "$PROJECT_ROOT/.coverage" "$PROJECT_ROOT"/.coverage.* 2>/dev/null || true

if [ -n "$fast_args" ]; then
  # The narrowed run. No --cov: coverage of a deliberate subset is not the project's
  # coverage, and ratcheting a baseline against it would either fail every fast gate or
  # quietly lower a real baseline. The ratchet stays on the full lane, where the number
  # means something. The log says so — the trade-off is documented where it is taken.
  fast_meta="$(PYTHONPATH="$BORROMEANRINGS_HOME/src" borromeanrings_py - \
    "$PROJECT_ROOT/borromeanrings.toml" <<'PY'
import json
import sys

from meta_harness.lane import FAST, FAST_LANE_NOTE, fast_lane_summary, fast_test_paths
from meta_harness.spine import load_config

paths = fast_test_paths(load_config(sys.argv[1]), FAST)
print(json.dumps({"lane": FAST, "fast_paths": list(paths), "summary": fast_lane_summary(paths)}))
print(FAST_LANE_NOTE)
PY
)"
  fast_extra="$(printf '%s\n' "$fast_meta" | head -1)"
  cmd="pytest $fast_args (FAST lane — no coverage ratchet)"
  printf '%s\n\nrunning: python3 -m pytest -q %s\n\n' \
    "$(printf '%s\n' "$fast_meta" | tail -n +2)" "$fast_args" >"$log"
  borromeanrings_run_bounded "$log.fast" "exec python3 -m pytest -q $fast_args"
  code=$?
  cat "$log.fast" >>"$log"
  rm -f "$log.fast"
  # Exit 5 here means the DECLARED fast paths collected no tests — a broken declaration,
  # not a greenfield project, so the full lane's exit-5 reasoning below does not transfer.
  if [ "$code" -eq 5 ]; then
    echo "no tests collected from the declared [test].fast_paths — fix the declaration" >>"$log"
    code=1
  fi
  status="fail"
  [ "$code" -eq 0 ] && status="pass"
  emit_receipt "$id" "$cmd" "$code" "$log" "$status" "$fast_extra"
  exit "$code"
fi

# `exec` so pytest is the timeout's direct child: on a hang it gets SIGTERM/SIGKILL
# directly (no orphaned pytest lingering past the gate). See checks/_lib.sh.
borromeanrings_run_bounded "$log" "exec python3 -m pytest -q --cov --cov-report=json:\"$covjson\""
code=$?

# pytest exit 5 = "no tests collected". On a GREENFIELD project (no source either) that's not a
# failure — there's simply nothing to test yet (don't force scaffolding during planning). But if
# source exists with no tests, that IS a gap → fail (untested code).
if [ "$code" -eq 5 ]; then
  src_dir="$(borromeanrings_project_cfg src_dir)"
  if [ -z "$(find "$PROJECT_ROOT/$src_dir" -name '*.py' -print -quit 2>/dev/null)" ]; then
    echo "no tests and no source yet (greenfield) — nothing to test" >>"$log"
    emit_noop "$id" "$cmd" "$log"
    exit 0
  fi
  echo "no tests collected, but source exists — add tests" >>"$log"
  emit_receipt "$id" "$cmd" 1 "$log" "fail"
  exit 1
fi

baseline="$(cat "$baseline_file" 2>/dev/null || echo 0)"
current="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['totals']['percent_covered'])" "$covjson" 2>/dev/null || echo 0)"

status="fail"
if [ "$code" -eq 0 ]; then
  drop="$(python3 -c "import sys; print(1 if float(sys.argv[1]) + 1e-9 < float(sys.argv[2]) else 0)" "$current" "$baseline")"
  if [ "$drop" = "1" ]; then
    printf "\nCOVERAGE REGRESSION: %.2f%% is below baseline %.2f%%\n" "$current" "$baseline" >>"$log"
    code=1
  else
    status="pass"
  fi
fi

extra="$(python3 -c "import json,sys; print(json.dumps({'coverage_percent': round(float(sys.argv[1]),2), 'coverage_baseline': float(sys.argv[2])}))" "$current" "$baseline" 2>/dev/null || echo '')"
emit_receipt "$id" "$cmd" "$code" "$log" "$status" "$extra"
exit "$code"
