#!/usr/bin/env bash
# Security: no bandit findings at/above the configured severity in the project's source.
#
# Guarded for vacuity first: pointed at a path with no Python, bandit exits 0 and prints
# NOTHING — the most misleading result in the suite, a clean security receipt produced by
# scanning nothing at all. Report that honestly as "noop" instead (ADR-0049); check
# 01_source_coherence is what decides whether an empty source path is legitimate.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

src_dir="$(borromeanrings_project_cfg src_dir)"
if [ -z "$(find "$PROJECT_ROOT/$src_dir" -name '*.py' -print -quit 2>/dev/null)" ]; then
  log="$RECEIPT_DIR/50_security.log"
  echo "no Python source in '$src_dir' — nothing to scan" >"$log"
  emit_noop "50_security" "security scan (no source)" "$log"
  exit 0
fi
run_check "50_security" "bandit" "bandit -q -r $src_dir"
