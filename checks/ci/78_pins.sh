#!/usr/bin/env bash
# 78_pins — HEAVY (CI-tier) pinned-dependency policy.
#
# Every runtime requirement in pyproject.toml [project].dependencies (plus the optional
# groups when [supply_chain].pin_optional = true) must carry an upper bound or an
# exact/compatible pin (==, ===, ~=, <, <=). A bare name or a >=-only requirement floats
# to whatever the index serves tomorrow — an unreviewed change to what ships. Binary per
# requirement (threshold-free by construction); the log names every offending line.
# Native (stdlib tomllib; no `packaging`). No pyproject.toml / no dependencies ⇒ noop.
# Dependencies declared `dynamic` ⇒ FAIL (the check was required but cannot see them —
# declare them statically or drop 78_pins). Malformed TOML ⇒ FAIL (fail-closed). See
# docs/specs/SPEC-supply-chain.md, ADR-0061.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="78_pins"
log="$RECEIPT_DIR/$id.log"
cmd="pinned dependencies (upper bound or exact pin on every declared requirement)"

manifest="$PROJECT_ROOT/pyproject.toml"
if [ ! -f "$manifest" ]; then
  echo "no pyproject.toml — no Python dependency manifest to inspect" >"$log"
  emit_noop "$id" "$cmd" "$log"
  exit 0
fi

PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_ROOT/borromeanrings.toml" "$manifest" >"$log" 2>&1 <<'PY'
import sys
from pathlib import Path

from meta_harness.spine import load_config
from meta_harness.supply_chain import pin_report

cfg = load_config(sys.argv[1])
try:
    report = pin_report(
        Path(sys.argv[2]).read_text(encoding="utf-8"),
        pin_optional=cfg.supply_chain_pin_optional,
    )
except ValueError as exc:
    print(f"CANNOT INSPECT DEPENDENCIES: {exc} — failing closed.")
    sys.exit(1)

if report.dynamic:
    print("DEPENDENCIES ARE DYNAMIC: [project].dynamic lists 'dependencies', so nothing here")
    print("can be judged. Declare them statically in pyproject.toml, or drop 78_pins.")
    sys.exit(1)
if report.inspected == 0:
    scope = "runtime + optional" if cfg.supply_chain_pin_optional else "runtime"
    print(f"no {scope} dependencies declared — nothing to inspect")
    sys.exit(3)
if report.findings:
    print(f"UNPINNED DEPENDENCIES — {len(report.findings)} of {report.inspected} requirement(s):")
    for f in report.findings:
        print(f"  - [{f.group}] {f.requirement!r}: {f.reason}")
    print("Add an upper bound (<N) or an exact/compatible pin (==, ~=) to each line.")
    sys.exit(1)
print(f"all {report.inspected} declared requirement(s) are pinned or bounded above")
PY
code=$?
emit_receipt "$id" "$cmd" "$code" "$log" "$(borromeanrings_status_for_code "$code")"
[ "$code" -eq "$BORROMEANRINGS_NOOP_EXIT" ] && exit 0
exit "$code"
