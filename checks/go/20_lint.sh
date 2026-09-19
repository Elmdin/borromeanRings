#!/usr/bin/env bash
# Lint: go vet reports nothing.
# Lane contract: docs/specs/SPEC-multi-language.md (ADR-0068). Missing tool ⇒ noop naming
# it (never installed, never fails the project); tool ran and failed ⇒ fail (closed).
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="20_lint"
src_dir="$(borromeanrings_project_cfg src_dir)"
if [ "$(borromeanrings_source_count "$src_dir" .go)" -eq 0 ]; then
  borromeanrings_noop_greenfield "$id" "go vet ./..." "Go" "$src_dir"
  exit 0
fi

tool="$(borromeanrings_lane_tool go)" || {
  borromeanrings_noop_missing_tool "$id" "go vet ./..." "go"
  exit 0
}
run_check "$id" "$tool" "\"$tool\" vet ./..."
