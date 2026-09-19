#!/usr/bin/env bash
# Format: no unformatted files (prettier; respects the project's .prettierignore).
# Lane contract: docs/specs/SPEC-multi-language.md (ADR-0068). Missing tool ⇒ noop naming
# it (never installed, never fails the project); tool ran and failed ⇒ fail (closed).
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="10_format"
src_dir="$(borromeanrings_project_cfg src_dir)"
if [ "$(borromeanrings_source_count "$src_dir" .ts .tsx)" -eq 0 ]; then
  borromeanrings_noop_greenfield "$id" "prettier --check ." "TypeScript" "$src_dir"
  exit 0
fi

tool="$(borromeanrings_lane_tool prettier)" || {
  borromeanrings_noop_missing_tool "$id" "prettier --check ." "prettier"
  exit 0
}
run_check "$id" "$tool" "\"$tool\" --check ."
