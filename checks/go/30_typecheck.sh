#!/usr/bin/env bash
# Typecheck: the compiler already type-checks in 00_build, so this slot holds the ecosystem's
# type-aware static analyzer (staticcheck: offline, no key) — an honest noop when absent.
# Lane contract: docs/specs/SPEC-multi-language.md (ADR-0068). Missing tool ⇒ noop naming
# it (never installed, never fails the project); tool ran and failed ⇒ fail (closed).
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="30_typecheck"
src_dir="$(borromeanrings_project_cfg src_dir)"
if [ "$(borromeanrings_source_count "$src_dir" .go)" -eq 0 ]; then
  borromeanrings_noop_greenfield "$id" "staticcheck ./..." "Go" "$src_dir"
  exit 0
fi

tool="$(borromeanrings_lane_tool staticcheck)" || {
  borromeanrings_noop_missing_tool "$id" "staticcheck ./..." "staticcheck"
  exit 0
}
run_check "$id" "$tool" "staticcheck ./..."
