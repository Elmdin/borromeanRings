#!/usr/bin/env bash
# 04_self_description — the README's stated counts must equal the registry.
#
# The README's check count drifted three times in one cycle ("eight" -> "nineteen" ->
# "twenty"), each time under-reporting what the harness does. A number written in prose
# is a claim; this makes it a checked one. Equalities, not targets: the number is THE
# number, so the threshold-free rule holds. No stated count => noop (a README may choose
# not to state one). See docs/specs/SPEC-describe.md and ADR-0052.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="04_self_description"
log="$RECEIPT_DIR/$id.log"
cmd="self-description (README counts equal the check registry)"

PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_ROOT" "$BORROMEANRINGS_HOME" >"$log" 2>&1 <<'PY'
import sys
from pathlib import Path

from meta_harness.describe import count_claims, discover_checks
from meta_harness.spine import load_config

project, home = Path(sys.argv[1]), Path(sys.argv[2])
readme = project / "README.md"
if not readme.is_file():
    print("no README.md — nothing to check")
    sys.exit(3)
claims = count_claims(readme.read_text(encoding="utf-8", errors="replace"))
if not claims:
    print("README states no check/gate counts — nothing to verify")
    sys.exit(3)

truth = {
    "checks": len(discover_checks(home / "checks")),
    "gates": len(load_config(project / "borromeanrings.toml").required_checks),
}
bad = {k: (claims[k], truth[k]) for k in claims if claims[k] != truth[k]}
if bad:
    print("README COUNT DRIFT (stated != registry):")
    for k, (said, real) in bad.items():
        print(f"  {k}: README says {said}, registry has {real}")
    print("Fix the README (or regenerate its block with describe.sh); never the registry.")
    sys.exit(1)
print("README counts match the registry: " + ", ".join(f"{k}={v}" for k, v in truth.items()))
PY
code=$?
status="$(borromeanrings_status_for_code "$code")"
[ "$status" = "noop" ] && code=0
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
