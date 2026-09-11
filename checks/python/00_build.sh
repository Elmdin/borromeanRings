#!/usr/bin/env bash
# Build / installable: the project's source compiles and (if a package is declared) imports cleanly.
# Vacuous-pass on a GREENFIELD project (no source yet) so ideation/planning is never forced to
# scaffold code just to make the gate green ("nothing to build" is not "build broken").
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

src_dir="$(borromeanrings_project_cfg src_dir)"
package="$(borromeanrings_project_cfg package)"

if [ -z "$(find "$PROJECT_ROOT/$src_dir" -name '*.py' -print -quit 2>/dev/null)" ]; then
  log="$RECEIPT_DIR/00_build.log"
  echo "no Python source in '$src_dir' yet (greenfield) — nothing to build" >"$log"
  emit_receipt "00_build" "build (no source yet)" 0 "$log" "pass"
  exit 0
fi

log="$RECEIPT_DIR/00_build.log"
if ! command -v python3 >/dev/null 2>&1; then
  printf "required tool 'python3' not found on PATH\n" >"$log"
  emit_receipt "00_build" "build" 127 "$log" "error"
  exit 127
fi

# Compile (syntax) step — ROUTED. compileall only parses/byte-compiles; it never
# imports project code, and it takes a path argument, so running the real stdlib
# compileall from a neutral directory on an ABSOLUTE path is equivalent AND closes the
# shadow: a compileall.py planted at the project root can no longer forge exit 0 on a
# syntax-error tree (#222 / #224 review S2). This is the part that is safely closeable.
borromeanrings_py -m compileall -q "$PROJECT_ROOT/$src_dir" >"$log" 2>&1
code=$?
cmd="compileall -q $src_dir"

# Import step — NOT routed (M7 boundary). `import <package>` actually RUNS the
# project's own code (executes the package's __init__), which the gate already trusts
# regardless of cwd — a malicious package forges this whether or not we cd away, the
# same #218 limit as pytest/mypy. It stays on the project path, bounded like any tool
# run. Only attempted if the source compiled.
if [ "$code" -eq 0 ] && [ -n "$package" ]; then
  cmd="$cmd && PYTHONPATH=$src_dir python3 -c \"import $package\""
  import_log="$RECEIPT_DIR/00_build.import.log"
  borromeanrings_run_bounded "$import_log" "PYTHONPATH=\"$src_dir\" python3 -c \"import $package\""
  code=$?
  cat "$import_log" >>"$log" 2>/dev/null || true
  rm -f "$import_log"
fi

status="fail"
[ "$code" -eq 0 ] && status="pass"
emit_receipt "00_build" "$cmd" "$code" "$log" "$status"
exit "$code"
