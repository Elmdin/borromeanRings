#!/usr/bin/env bash
# Branch-naming gate (Tier A collaboration): the current work branch must match
# a declared [collaboration].branch_patterns glob. Skips (passes) on the declared
# protected branches (post-merge CI) and on detached HEAD (PR merge refs); off
# when no patterns are declared. Fail-closed once declared. See
# docs/specs/SPEC-collaboration.md and ADR-0021.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="08_branch"
log="$RECEIPT_DIR/$id.log"
cmd="branch naming (declared [collaboration].branch_patterns)"

branch="$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo HEAD)"

PYTHONPATH="$BORROMEANRINGS_HOME/src" \
  python3 - "$PROJECT_ROOT/borromeanrings.toml" "$branch" >"$log" 2>&1 <<'PY'
import sys

from meta_harness.collaboration import branch_violation
from meta_harness.spine import load_config

cfg = load_config(sys.argv[1])
branch = sys.argv[2]

if not cfg.collaboration_branch_patterns:
    print("branch naming not declared ([collaboration].branch_patterns empty) — rule off")
    sys.exit(0)

violation = branch_violation(
    branch, cfg.collaboration_protected_branches, cfg.collaboration_branch_patterns
)
if violation:
    print(f"BRANCH VIOLATION: {violation}")
    sys.exit(1)
print(f"branch OK — '{branch}' conforms (or naming rules don't apply to it)")
PY
code=$?
status="fail"
[ "$code" -eq 0 ] && status="pass"
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
