#!/usr/bin/env bash
# Project hygiene: the engineering surround declared in borromeo.toml ([hygiene].requires)
# must exist (docs, CI, containerization, license, …). Fail-closed if any is missing.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

id="05_hygiene"
log="$RECEIPT_DIR/$id.log"
cmd="project hygiene (declared engineering-surround paths exist)"

PYTHONPATH="$BORROMEO_HOME/src" python3 - "$PROJECT_ROOT" "$PROJECT_ROOT/borromeo.toml" >"$log" 2>&1 <<'PY'
import sys

from meta_harness.hygiene import missing_paths
from meta_harness.spine import load_config

root, config_path = sys.argv[1], sys.argv[2]
missing = missing_paths(root, load_config(config_path).hygiene_requires)
if missing:
    print("MISSING required engineering-surround artifacts:")
    for path in missing:
        print(f"  - {path}")
    sys.exit(1)
print("all declared hygiene artifacts present")
PY
code=$?
status="fail"
[ "$code" -eq 0 ] && status="pass"
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
