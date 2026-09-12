#!/usr/bin/env bash
# Docstring-coverage RATCHET (not an absolute target): the fraction of public
# definitions (module, public class/function/method) carrying a docstring may not
# regress below the recorded baseline (.borromeanrings-docstring-baseline;
# default 0 ⇒ vacuous until a baseline is set — opt-in by adding this check to
# [checks].required and recording a baseline). Native stdlib ast; no external
# tool. Greenfield (no source) passes. See SPEC-docstrings.md and ADR-0029.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="45_docstrings"
log="$RECEIPT_DIR/$id.log"
baseline_file="$PROJECT_ROOT/.borromeanrings-docstring-baseline"
cmd="docstring coverage (ratchet vs baseline)"

src_dir="$(borromeanrings_project_cfg src_dir)"
package="$(borromeanrings_project_cfg package)"

if [ -z "$package" ] || [ -z "$(find "$PROJECT_ROOT/$src_dir" -name '*.py' -print -quit 2>/dev/null)" ]; then
  echo "no package/source to measure (greenfield) — nothing to document" >"$log"
  emit_noop "$id" "$cmd" "$log"
  exit 0
fi

current="$(PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_ROOT/$src_dir" "$package" <<'PY'
import sys

from meta_harness.docstrings import measure_package

print(f"{measure_package(sys.argv[1], sys.argv[2]).coverage:.6f}")
PY
)"
baseline="$(cat "$baseline_file" 2>/dev/null || echo 0)"
echo "docstring coverage: $current (baseline $baseline)" >"$log"

regressed="$(python3 -c "import sys; print(1 if float(sys.argv[1]) + 1e-9 < float(sys.argv[2]) else 0)" "$current" "$baseline")"
status="pass"
code=0
if [ "$regressed" = "1" ]; then
  echo "DOCSTRING REGRESSION: $current is below baseline $baseline" >>"$log"
  status="fail"
  code=1
fi
extra="$(python3 -c "import json,sys; print(json.dumps({'docstring_coverage': round(float(sys.argv[1]),6), 'docstring_baseline': float(sys.argv[2])}))" "$current" "$baseline" 2>/dev/null || echo '')"
emit_receipt "$id" "$cmd" "$code" "$log" "$status" "$extra"
exit "$code"
