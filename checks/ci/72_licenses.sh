#!/usr/bin/env bash
# 72_licenses — HEAVY (CI-tier) dependency license compliance.
#
# pip-licenses reads the installed closure (in CI = the project's declared deps).
# Opt-in via [licenses].deny (case-insensitive substring patterns to reject, e.g.
# GPL/AGPL/SSPL); off when unset. allow_packages exempts vetted deps. Runs only
# under --heavy. See docs/specs/SPEC-licenses.md and ADR-0035.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="72_licenses"
log="$RECEIPT_DIR/$id.log"
cmd="dependency license compliance (pip-licenses; heavy/CI)"

if ! command -v pip-licenses >/dev/null 2>&1; then
  printf "required tool 'pip-licenses' not found on PATH\n" >"$log"
  emit_receipt "$id" "$cmd" 127 "$log" "error"
  exit 127
fi

raw="$RECEIPT_DIR/$id.report.json"
borromeanrings_run_bounded "$RECEIPT_DIR/$id.tool.log" "pip-licenses --format=json > '$raw'" || true

PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_ROOT/borromeanrings.toml" "$raw" >"$log" 2>&1 <<'PY'
import sys
from pathlib import Path

from meta_harness.licenses import license_violations, parse_pip_licenses
from meta_harness.spine import load_config

cfg = load_config(sys.argv[1])
if not cfg.license_deny:
    print("no [licenses].deny configured — license check off")
    sys.exit(0)

report = Path(sys.argv[2])
if not report.exists() or not report.read_text().strip():
    print("pip-licenses produced no report (tool failure) — fail closed")
    sys.exit(1)

violations = license_violations(
    parse_pip_licenses(report.read_text(encoding="utf-8")),
    deny=cfg.license_deny,
    allow_packages=cfg.license_allow_packages,
)
if violations:
    print(f"INCOMPATIBLE LICENSES in {len(violations)} dependency(ies):")
    for v in violations:
        print(f"  - {v.name} {v.version}: {v.license} (matched deny '{v.matched}')")
    print("Replace the dependency, or vet + add it to [licenses].allow_packages.")
    sys.exit(1)
print("all dependency licenses compliant")
PY
code=$?
status="fail"
[ "$code" -eq 0 ] && status="pass"
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
