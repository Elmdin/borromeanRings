#!/usr/bin/env bash
# Typecheck: the source holds under --strict (noImplicitAny, strictNullChecks, ...), a
# stronger guarantee than the project may have opted into; 00_build is the plain compile.
# Lane contract: docs/specs/SPEC-multi-language.md (ADR-0068). Missing tool ⇒ noop naming
# it (never installed, never fails the project); tool ran and failed ⇒ fail (closed).
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="30_typecheck"
src_dir="$(borromeanrings_project_cfg src_dir)"
if [ "$(borromeanrings_source_count "$src_dir" .ts .tsx)" -eq 0 ]; then
  borromeanrings_noop_greenfield "$id" "tsc -p tsconfig.json --noEmit --strict" "TypeScript" "$src_dir"
  exit 0
fi

tool="$(borromeanrings_lane_tool tsc)" || {
  borromeanrings_noop_missing_tool "$id" "tsc -p tsconfig.json --noEmit --strict" "tsc"
  exit 0
}

if [ ! -f "$PROJECT_ROOT/tsconfig.json" ]; then
  log="$RECEIPT_DIR/$id.log"
  echo "TypeScript source exists but there is no tsconfig.json — tsc cannot resolve the project (fail-closed)" >"$log"
  emit_receipt "$id" "tsc -p tsconfig.json --noEmit --strict" 1 "$log" "fail"
  exit 1
fi
run_check "$id" "$tool" "\"$tool\" -p tsconfig.json --noEmit --strict"
