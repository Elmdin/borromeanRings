#!/usr/bin/env bash
# Test + coverage RATCHET (not an absolute %): tests must pass, and coverage
# may not regress below the recorded baseline. Coverage is recorded in the
# receipt. Mutation testing (the real oracle-strength signal) is deferred.
# See docs/REQUIREMENTS.md QAS-7 and docs/TEST-PLAN.md §5.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

id="40_test"
log="$RECEIPT_DIR/$id.log"
covjson="$RECEIPT_DIR/coverage.json"
baseline_file="$PROJECT_ROOT/.borromeo-coverage-baseline"
cmd="pytest --cov (ratchet vs baseline)"

if ! python3 -m pytest --version >/dev/null 2>&1; then
  printf "required tool 'pytest' (python3 -m pytest) not available\n" >"$log"
  emit_receipt "$id" "$cmd" 127 "$log" "error"
  exit 127
fi

( cd "$PROJECT_ROOT" && python3 -m pytest -q --cov --cov-report=json:"$covjson" ) >"$log" 2>&1
code=$?

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
