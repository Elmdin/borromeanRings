#!/usr/bin/env bash
# Architectural fitness: the internal import graph obeys the declared
# [architecture] contracts — foundation leaves, private testbeds, forbidden
# edges, acyclicity. Native stdlib-ast analysis; no external tool. Opt-in: off
# when no contracts are declared. See docs/specs/SPEC-architecture.md, ADR-0027.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="35_architecture"
log="$RECEIPT_DIR/$id.log"
cmd="architectural import-direction fitness (declared [architecture] contracts)"

PYTHONPATH="$BORROMEANRINGS_HOME/src" borromeanrings_py - "$PROJECT_ROOT" "$PROJECT_ROOT/borromeanrings.toml" >"$log" 2>&1 <<'PY'
import sys
from pathlib import Path

from meta_harness.architecture import build_import_graph, evaluate
from meta_harness.spine import load_config

root, config_path = Path(sys.argv[1]), sys.argv[2]
cfg = load_config(config_path)

declared = (
    cfg.architecture_leaves
    or cfg.architecture_private
    or cfg.architecture_forbidden
    or cfg.architecture_forbid_cycles
)
if not declared:
    print("no [architecture] contracts declared — rule off")
    sys.exit(0)
if not cfg.package:
    print("no [project].package to analyze — rule off")
    sys.exit(0)

graph = build_import_graph(root / cfg.src_dir, cfg.package)
report = evaluate(
    graph,
    leaves=cfg.architecture_leaves,
    private=cfg.architecture_private,
    forbidden=cfg.architecture_forbidden,
    forbid_cycles=cfg.architecture_forbid_cycles,
)
if not report.ok:
    print("ARCHITECTURE VIOLATIONS:")
    for v in report.violations:
        print(f"  - [{v.kind}] {v.detail}")
    sys.exit(1)
print(f"architecture OK — {len(graph)} modules obey the declared contracts")
PY
code=$?
status="fail"
[ "$code" -eq 0 ] && status="pass"
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
