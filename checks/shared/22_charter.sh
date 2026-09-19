#!/usr/bin/env bash
# 22_charter — session-charter gate.
#
# When [charter].enabled, the governed project's committed charter file (default
# CHARTER.toml) must exist and validate: goal, stakes (low|high — two opt-in tiers,
# never a dial), done_when / stop_when / may_not (non-empty lists of real predicates),
# owner, and at stakes "high" the [charter].high_stakes_fields. Every violation is
# reported as `<field> — <reason>`, all at once. Never noop: a declared charter is
# either valid or it is not. Rule off (pass) when [charter] is not enabled. See
# SPEC-charter.md, ADR-0063.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="22_charter"
log="$RECEIPT_DIR/$id.log"
cmd="session charter (goal, stakes tier, done_when/stop_when/may_not, owner; fail-closed)"

PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_ROOT" "$PROJECT_ROOT/borromeanrings.toml" >"$log" 2>&1 <<'PY'
import sys
from pathlib import Path

from meta_harness.charter import CharterError, load_charter, render, validate
from meta_harness.spine import load_config

root, cfg = Path(sys.argv[1]), load_config(sys.argv[2])

if not cfg.charter_enabled:
    print("charter gate not enabled ([charter].enabled=false) — rule off")
    sys.exit(0)

try:
    charter = load_charter(root / cfg.charter_path)
    violations = validate(charter, cfg)
except CharterError as exc:
    violations = exc.violations

if violations:
    print(f"CHARTER VIOLATIONS ({cfg.charter_path}):")
    for v in violations:
        print(f"  {v.field} — {v.reason}")
    sys.exit(1)
print(render(charter))
PY
code=$?
status="fail"
[ "$code" -eq 0 ] && status="pass"
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
