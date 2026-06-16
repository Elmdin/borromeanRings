#!/usr/bin/env bash
# Build / installable: the project's source compiles and (if a package is declared) imports cleanly.
# Vacuous-pass on a GREENFIELD project (no source yet) so ideation/planning is never forced to
# scaffold code just to make the gate green ("nothing to build" is not "build broken").
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

src_dir="$(borromeo_project_cfg src_dir)"
package="$(borromeo_project_cfg package)"

if [ -z "$(find "$PROJECT_ROOT/$src_dir" -name '*.py' -print -quit 2>/dev/null)" ]; then
  log="$RECEIPT_DIR/00_build.log"
  echo "no Python source in '$src_dir' yet (greenfield) — nothing to build" >"$log"
  emit_receipt "00_build" "build (no source yet)" 0 "$log" "pass"
  exit 0
fi

cmd="python3 -m compileall -q $src_dir"
if [ -n "$package" ]; then
  cmd="$cmd && PYTHONPATH=$src_dir python3 -c \"import $package\""
fi
run_check "00_build" "python3" "$cmd"
