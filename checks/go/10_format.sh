#!/usr/bin/env bash
# Format: gofmt lists no files. gofmt -l exits 0 even when files need formatting, so the
# verdict is on the LIST being empty, not on the exit code.
# Lane contract: docs/specs/SPEC-multi-language.md (ADR-0068). Missing tool ⇒ noop naming
# it (never installed, never fails the project); tool ran and failed ⇒ fail (closed).
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="10_format"
src_dir="$(borromeanrings_project_cfg src_dir)"
if [ "$(borromeanrings_source_count "$src_dir" .go)" -eq 0 ]; then
  borromeanrings_noop_greenfield "$id" "gofmt -l <src_dir>" "Go" "$src_dir"
  exit 0
fi

tool="$(borromeanrings_lane_tool gofmt)" || {
  borromeanrings_noop_missing_tool "$id" "gofmt -l <src_dir>" "gofmt"
  exit 0
}
log="$RECEIPT_DIR/$id.log"
borromeanrings_run_bounded "$log" "unformatted=\$(\"$tool\" -l \"$src_dir\") && { [ -z \"\$unformatted\" ] || { echo \"UNFORMATTED (run gofmt -w):\"; echo \"\$unformatted\"; exit 1; }; }"
code=$?
status="fail"
[ "$code" -eq 0 ] && status="pass"
emit_receipt "$id" "gofmt -l $src_dir" "$code" "$log" "$status"
exit "$code"
