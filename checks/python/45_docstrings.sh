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

# A crashed measurement left
# `current` empty, the comparison below silently did not fire, and the ratchet passed
# over a measurement nobody got (#186).
current=""
if ! current="$(PYTHONPATH="$BORROMEANRINGS_HOME/src" borromeanrings_py - "$PROJECT_ROOT/$src_dir" "$package" <<'PY'
import sys

from meta_harness.docstrings import measure_package

print(f"{measure_package(sys.argv[1], sys.argv[2]).coverage:.6f}")
PY
)"; then
  borromeanrings_cannot_read "$id" "$cmd" "$log" "this project's docstring coverage" "$current"
fi
borromeanrings_number_or_fail "$current" "$id" "$cmd" "$log" "this project's docstring coverage"
baseline=""
borromeanrings_baseline baseline "$baseline_file" 0 "$id" "$cmd" "$log" number
echo "docstring coverage: $current (baseline $baseline)" >"$log"

# The comparison is itself a tool call: if it cannot run, there is no comparison, and
# an empty answer is not "no regression" (#186).
regressed=""
if ! regressed="$(borromeanrings_py -c "import sys; print(1 if float(sys.argv[1]) + 1e-9 < float(sys.argv[2]) else 0)" "$current" "$baseline" 2>&1)"; then
  borromeanrings_cannot_read "$id" "$cmd" "$log" "the comparison to the baseline" "$regressed"
fi
status="pass"
code=0
if [ "$regressed" = "1" ]; then
  echo "DOCSTRING REGRESSION: $current is below baseline $baseline" >>"$log"
  status="fail"
  code=1
fi
extra="$(borromeanrings_py -c "import json,sys; print(json.dumps({'docstring_coverage': round(float(sys.argv[1]),6), 'docstring_baseline': float(sys.argv[2])}))" "$current" "$baseline" 2>/dev/null || echo '')"
emit_receipt "$id" "$cmd" "$code" "$log" "$status" "$extra"
exit "$code"
