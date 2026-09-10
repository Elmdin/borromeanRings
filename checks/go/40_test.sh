#!/usr/bin/env bash
# Test + coverage RATCHET (not an absolute %): go test passes and statement coverage (the
# total: line of go tool cover -func, parsed by meta_harness.lang_coverage) may not regress
# below .borromeanrings-coverage-baseline. Source with no tests at all ⇒ fail (untested code).
# Lane contract: docs/specs/SPEC-multi-language.md (ADR-0068). Missing tool ⇒ noop naming
# it (never installed, never fails the project); tool ran and failed ⇒ fail (closed).
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="40_test"
src_dir="$(borromeanrings_project_cfg src_dir)"
if [ "$(borromeanrings_source_count "$src_dir" .go)" -eq 0 ]; then
  borromeanrings_noop_greenfield "$id" "go test -coverprofile ./... (ratchet vs baseline)" "Go" "$src_dir"
  exit 0
fi

log="$RECEIPT_DIR/$id.log"
profile="$RECEIPT_DIR/cover.out"
funclog="$RECEIPT_DIR/$id.cover-func.log"
baseline_file="$PROJECT_ROOT/.borromeanrings-coverage-baseline"
label="go test -coverprofile ./... (ratchet vs baseline)"

tool="$(borromeanrings_lane_tool go)" || {
  borromeanrings_noop_missing_tool "$id" "$label" "go"
  exit 0
}

borromeanrings_run_bounded "$log" "exec \"$tool\" test -coverprofile=\"$profile\" ./..."
code=$?
[ "$code" -eq 0 ] && borromeanrings_run_bounded "$funclog" "\"$tool\" tool cover -func=\"$profile\"" || true
baseline="$(cat "$baseline_file" 2>/dev/null || echo 0)"

# The parser's stdout is the heredoc body; `read` splits it into these variables. An
# empty body (parser crash) leaves them empty — the guard below fails closed on that.
read -r current regressed tested <<EOF
$(PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$log" "$funclog" "$baseline" <<'PY'
import sys

from meta_harness.lang_coverage import go_func_total_percent, parse_go_test_summary
from meta_harness.ratchet import decide_ratchet


def read(path: str) -> str:
    try:
        return open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


summary = parse_go_test_summary(read(sys.argv[1]))
current = go_func_total_percent(read(sys.argv[2]))
tested = 1 if summary.tested else 0
if current is None:
    print(f"none 0 {tested}")
else:
    print(f"{current:.2f} {1 if decide_ratchet(current, float(sys.argv[3])).regressed else 0} {tested}")
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
  if [ "$tested" = "0" ]; then
    printf "\nno package has test files, but source exists — add tests\n" >>"$log"
    code=1
  elif [ "$current" = "none" ]; then
    printf "\nNO COVERAGE NUMBER: go tool cover -func reported no total — failing closed\n" >>"$log"
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
