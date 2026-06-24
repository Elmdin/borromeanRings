#!/usr/bin/env bash
# Typecheck: no type errors in the project's source (mypy). Vacuous-pass on greenfield (no source).
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

src_dir="$(borromeanrings_project_cfg src_dir)"
if [ -z "$(find "$PROJECT_ROOT/$src_dir" -name '*.py' -print -quit 2>/dev/null)" ]; then
  log="$RECEIPT_DIR/30_typecheck.log"
  echo "no Python source in '$src_dir' yet (greenfield) — nothing to typecheck" >"$log"
  emit_receipt "30_typecheck" "typecheck (no source yet)" 0 "$log" "pass"
  exit 0
fi
run_check "30_typecheck" "mypy" "mypy $src_dir"
