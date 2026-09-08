#!/usr/bin/env bash
# Branch gate (Tier A collaboration + trunk-based policy). Two rules, both
# config-driven and opt-in:
#   1. naming — the work branch must match a declared [collaboration].branch_patterns
#      glob (skips on protected branches and detached HEAD; off when undeclared).
#   2. direct commits — when HEAD is a declared protected branch, it must carry NO
#      commits beyond its remote ref (someone committed directly instead of landing
#      via PR + gate). The backstop for the PreToolUse guard; cannot judge (passes)
#      when no remote ref exists to compare against.
# Fail-closed once declared. See docs/specs/SPEC-collaboration.md,
# docs/specs/SPEC-branch-policy.md, ADR-0021 and ADR-0058.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="08_branch"
log="$RECEIPT_DIR/$id.log"
cmd="branch policy (declared [collaboration].branch_patterns / protected_branches)"

branch="$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo HEAD)"

# Commits on HEAD that its remote counterpart lacks: the upstream if set, else
# origin/<branch> if it exists, else unknown (empty ⇒ the rule cannot judge).
remote_ref=""
ahead=""
if [ -n "$branch" ] && [ "$branch" != "HEAD" ]; then
  remote_ref="$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref --symbolic-full-name \
    "$branch@{upstream}" 2>/dev/null || true)"
  if [ -z "$remote_ref" ] &&
    git -C "$PROJECT_ROOT" rev-parse --verify -q "refs/remotes/origin/$branch" >/dev/null 2>&1; then
    remote_ref="origin/$branch"
  fi
  if [ -n "$remote_ref" ]; then
    ahead="$(git -C "$PROJECT_ROOT" rev-list --count "$remote_ref..HEAD" 2>/dev/null || echo "")"
  fi
fi

PYTHONPATH="$BORROMEANRINGS_HOME/src" \
  python3 - "$PROJECT_ROOT/borromeanrings.toml" "$branch" "$remote_ref" "$ahead" >"$log" 2>&1 <<'PY'
import sys

from meta_harness.collaboration import branch_violation
from meta_harness.spine import load_config
from meta_harness.trunk_policy import direct_commit_violation

cfg = load_config(sys.argv[1])
branch, remote_ref, ahead_raw = sys.argv[2:5]
protected = cfg.collaboration_protected_branches
patterns = cfg.collaboration_branch_patterns

if not patterns and not protected:
    print(
        "branch policy not declared ([collaboration].branch_patterns and "
        "protected_branches empty) — rule off"
    )
    sys.exit(0)

violation = branch_violation(branch, protected, patterns)
if violation:
    print(f"BRANCH VIOLATION: {violation}")
    sys.exit(1)

ahead = int(ahead_raw) if ahead_raw.isdigit() else None
direct = direct_commit_violation(branch, protected, ahead, remote_ref)
if direct:
    print(direct)
    sys.exit(1)

if branch in protected:
    where = f"in sync with {remote_ref}" if ahead is not None else "no remote ref to compare"
    print(f"branch OK — protected '{branch}' carries no direct commits ({where})")
else:
    print(f"branch OK — '{branch}' conforms (or naming rules don't apply to it)")
PY
code=$?
status="fail"
[ "$code" -eq 0 ] && status="pass"
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
