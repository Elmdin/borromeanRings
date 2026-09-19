#!/usr/bin/env bash
# Security: gosec (offline, static) reports nothing. govulncheck contacts a vulnerability
# database and is EXCLUDED from the fast lane (SPEC-multi-language.md §2.6).
# Lane contract: docs/specs/SPEC-multi-language.md (ADR-0068). Missing tool ⇒ noop naming
# it (never installed, never fails the project); tool ran and failed ⇒ fail (closed).
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="50_security"
src_dir="$(borromeanrings_project_cfg src_dir)"
if [ "$(borromeanrings_source_count "$src_dir" .go)" -eq 0 ]; then
  borromeanrings_noop_greenfield "$id" "gosec ./..." "Go" "$src_dir"
  exit 0
fi

tool="$(borromeanrings_lane_tool gosec)" || {
  borromeanrings_noop_missing_tool "$id" "gosec ./..." "gosec"
  exit 0
}
run_check "$id" "$tool" "\"$tool\" -quiet ./..."
