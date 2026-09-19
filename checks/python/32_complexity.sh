#!/usr/bin/env bash
# Cyclomatic-complexity RATCHET (not an absolute ceiling): the worst-case function
# complexity may not regress above the recorded baseline
# (.borromeanrings-complexity-baseline; default a large number ⇒ vacuous until set —
# opt-in by adding this check to [checks].required and recording a baseline).
# Native McCabe over stdlib ast; no external tool. Greenfield passes.
# See docs/specs/SPEC-complexity.md and ADR-0031.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="32_complexity"
log="$RECEIPT_DIR/$id.log"
baseline_file="$PROJECT_ROOT/.borromeanrings-complexity-baseline"
cmd="cyclomatic complexity (ratchet vs baseline)"

src_dir="$(borromeanrings_project_cfg src_dir)"
package="$(borromeanrings_project_cfg package)"

if [ -z "$package" ] || [ -z "$(find "$PROJECT_ROOT/$src_dir" -name '*.py' -print -quit 2>/dev/null)" ]; then
  echo "no package/source to measure (greenfield) — nothing to analyze" >"$log"
  emit_noop "$id" "$cmd" "$log"
  exit 0
fi

read -r current worst < <(PYTHONPATH="$BORROMEANRINGS_HOME/src" borromeanrings_py - "$PROJECT_ROOT/$src_dir" "$package" <<'PY'
import sys

from meta_harness.complexity import worst_complexity

value, name = worst_complexity(sys.argv[1], sys.argv[2])
print(value, name or "-")
PY
)
# Default baseline is effectively "off" (huge) so an unconfigured project never fails.
baseline="$(cat "$baseline_file" 2>/dev/null || echo 100000)"
echo "worst cyclomatic complexity: $current at $worst (baseline $baseline)" >"$log"

status="pass"
code=0
if [ "$current" -gt "$baseline" ]; then
  echo "COMPLEXITY REGRESSION: $worst is $current, above baseline $baseline — simplify it" >>"$log"
  status="fail"
  code=1
fi
extra="$(borromeanrings_py -c "import json,sys; print(json.dumps({'worst_complexity': int(sys.argv[1]), 'complexity_baseline': int(sys.argv[2]), 'worst_function': sys.argv[3]}))" "$current" "$baseline" "$worst" 2>/dev/null || echo '')"
emit_receipt "$id" "$cmd" "$code" "$log" "$status" "$extra"
exit "$code"
