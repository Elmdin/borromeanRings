#!/usr/bin/env bash
# Test + coverage RATCHET (not an absolute %): tests pass and line coverage may not
# regress below .borromeanrings-coverage-baseline. vitest preferred, jest the fallback;
# both emit istanbul's json-summary, parsed by meta_harness.lang_coverage.
# Lane contract: docs/specs/SPEC-multi-language.md (ADR-0068). Missing tool ⇒ noop naming
# it (never installed, never fails the project); tool ran and failed ⇒ fail (closed).
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="40_test"
src_dir="$(borromeanrings_project_cfg src_dir)"
if [ "$(borromeanrings_source_count "$src_dir" .ts .tsx)" -eq 0 ]; then
  borromeanrings_noop_greenfield "$id" "vitest/jest --coverage (ratchet vs baseline)" "TypeScript" "$src_dir"
  exit 0
fi

log="$RECEIPT_DIR/$id.log"
covdir="$RECEIPT_DIR/coverage"
baseline_file="$PROJECT_ROOT/.borromeanrings-coverage-baseline"

if tool="$(borromeanrings_lane_tool vitest)"; then
  cmd="\"$tool\" run --coverage --coverage.reporter=json-summary --coverage.reportsDirectory=\"$covdir\""
  label="vitest run --coverage (ratchet vs baseline)"
elif tool="$(borromeanrings_lane_tool jest)"; then
  cmd="\"$tool\" --ci --coverage --coverageReporters=json-summary --coverageDirectory=\"$covdir\""
  label="jest --coverage (ratchet vs baseline)"
else
  borromeanrings_noop_missing_tool "$id" "vitest/jest --coverage (ratchet vs baseline)" "vitest not installed; jest"
  exit 0
fi

# `exec` so the runner is the timeout's direct child (a hang gets the signal itself).
borromeanrings_run_bounded "$log" "exec $cmd"
code=$?
baseline="$(cat "$baseline_file" 2>/dev/null || echo 0)"

read -r current regressed <<EOF
$(PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$covdir/coverage-summary.json" "$baseline" <<'PY'
import sys

from meta_harness.lang_coverage import istanbul_line_percent
from meta_harness.ratchet import decide_ratchet

try:
    text = open(sys.argv[1], encoding="utf-8").read()
except OSError:
    text = ""
current = istanbul_line_percent(text)
if current is None:
    print("none 0")
else:
    print(f"{current:.2f} {1 if decide_ratchet(current, float(sys.argv[2])).regressed else 0}")
PY
)
EOF

status="fail"
# The parser's only channel back is its stdout; an empty read means it crashed (e.g. a
# corrupt baseline file) and nothing was validated — say so and fail, never fall through.
if [ -z "${current:-}" ] || [ -z "${regressed:-}" ]; then
  printf "\nCOVERAGE PARSE FAILED (corrupt %s?) — failing closed\n" "$baseline_file" >>"$log"
  current="none"
  code=1
fi
if [ "$code" -eq 0 ]; then
  if [ "$current" = "none" ]; then
    printf "\nNO COVERAGE NUMBER: the runner exited 0 but wrote no usable coverage-summary.json (is the coverage provider installed?) — failing closed\n" >>"$log"
    code=1
  elif [ "$regressed" = "1" ]; then
    printf "\nCOVERAGE REGRESSION: %s%% is below baseline %s%%\n" "$current" "$baseline" >>"$log"
    code=1
  else
    status="pass"
  fi
fi
extra=""
[ "$current" != "none" ] && extra="{\"coverage_percent\": $current, \"coverage_baseline\": $baseline}"
emit_receipt "$id" "$label" "$code" "$log" "$status" "$extra"
exit "$code"
