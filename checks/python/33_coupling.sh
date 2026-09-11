#!/usr/bin/env bash
# Coupling RATCHET (not an absolute ceiling): the worst efferent coupling
# (fan-out) in the internal module graph may not regress above the recorded
# baseline (.borromeanrings-coupling-baseline; default huge ⇒ vacuous until set —
# opt-in via [checks].required + a baseline). Native (reuses the arch import
# graph); no external tool. Greenfield passes. See SPEC-coupling.md and ADR-0038.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="33_coupling"
log="$RECEIPT_DIR/$id.log"
baseline_file="$PROJECT_ROOT/.borromeanrings-coupling-baseline"
cmd="worst-case module coupling / fan-out (ratchet vs baseline)"

src_dir="$(borromeanrings_project_cfg src_dir)"
package="$(borromeanrings_project_cfg package)"

if [ -z "$package" ] || [ -z "$(find "$PROJECT_ROOT/$src_dir" -name '*.py' -print -quit 2>/dev/null)" ]; then
  echo "no package/source to measure (greenfield) — nothing to analyze" >"$log"
  emit_receipt "$id" "$cmd" 0 "$log" "pass"
  exit 0
fi

read -r current worst < <(PYTHONPATH="$BORROMEANRINGS_HOME/src" borromeanrings_py - "$PROJECT_ROOT/$src_dir" "$package" <<'PY'
import sys

from meta_harness.coupling import worst_fan_out

value, name = worst_fan_out(sys.argv[1], sys.argv[2])
print(value, name or "-")
PY
)
baseline="$(cat "$baseline_file" 2>/dev/null || echo 100000)"
echo "worst fan-out (efferent coupling): $current at $worst (baseline $baseline)" >"$log"

status="pass"
code=0
if [ "$current" -gt "$baseline" ]; then
  echo "COUPLING REGRESSION: $worst has fan-out $current, above baseline $baseline — reduce its internal imports" >>"$log"
  status="fail"
  code=1
fi
extra="$(borromeanrings_py -c "import json,sys; print(json.dumps({'worst_fan_out': int(sys.argv[1]), 'coupling_baseline': int(sys.argv[2]), 'worst_module': sys.argv[3]}))" "$current" "$baseline" "$worst" 2>/dev/null || echo '')"
emit_receipt "$id" "$cmd" "$code" "$log" "$status" "$extra"
exit "$code"
