#!/usr/bin/env bash
# 76_lockfile — HEAVY (CI-tier) lockfile integrity.
#
# If the project declares a lockfile ([supply_chain].lockfile — uv.lock, poetry.lock,
# requirements.lock, package-lock.json ...), a dependency manifest (pyproject.toml,
# package.json; [supply_chain].manifests) that changed relative to the merge-base
# WITHOUT the lockfile changing means the lock is stale: what gets installed no longer
# matches what was declared. Git-derivable, threshold-free, native (no tool). No
# lockfile declared ⇒ noop (honest: the rule is off). Fail-closed: a declared lockfile
# that does not exist, or any git error inside a repository, is a FAIL — "cannot tell
# what changed" must never read as "nothing changed". No base branch to diff against
# ⇒ noop (same doctrine as 13_adr). See docs/specs/SPEC-supply-chain.md, ADR-0061.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="76_lockfile"
log="$RECEIPT_DIR/$id.log"
cmd="lockfile integrity (manifest change must be mirrored by [supply_chain].lockfile)"

lockfile="$(borromeanrings_project_cfg supply_chain_lockfile 2>/dev/null || true)"
if [ -z "$lockfile" ]; then
  echo "no [supply_chain].lockfile declared — lockfile integrity is off" >"$log"
  emit_noop "$id" "$cmd" "$log"
  exit 0
fi

if ! git -C "$PROJECT_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "NOT A GIT REPOSITORY — cannot tell whether '$lockfile' kept up with the manifest." >"$log"
  echo "Fail-closed: run 'git init' (and commit), or clear [supply_chain].lockfile." >>"$log"
  emit_receipt "$id" "$cmd" 1 "$log" "fail"
  exit 1
fi

base=""
for candidate in origin/dev dev origin/main main; do
  if git -C "$PROJECT_ROOT" rev-parse --verify --quiet "$candidate" >/dev/null 2>&1; then
    base="$candidate"
    break
  fi
done
merge_base=""
[ -n "$base" ] && merge_base="$(git -C "$PROJECT_ROOT" merge-base HEAD "$base" 2>/dev/null || true)"
if [ -z "$merge_base" ]; then
  echo "no base branch to diff against — nothing to check" >"$log"
  emit_noop "$id" "$cmd" "$log"
  exit 0
fi

# Everything that differs from the merge-base: committed + working tree (--relative so
# paths match the declared ones for a subdirectory-governed project too), plus untracked
# files — a freshly generated, not-yet-added lockfile still counts as "changed".
changed_file="$RECEIPT_DIR/$id.changed"
if ! git -C "$PROJECT_ROOT" diff --relative --name-only "$merge_base" >"$changed_file" 2>"$log"; then
  echo "git diff against merge-base $merge_base FAILED — cannot tell what changed; failing closed." >>"$log"
  emit_receipt "$id" "$cmd" 1 "$log" "fail"
  exit 1
fi
git -C "$PROJECT_ROOT" ls-files --others --exclude-standard >>"$changed_file" 2>/dev/null || true

lockfile_exists=0
[ -f "$PROJECT_ROOT/$lockfile" ] && lockfile_exists=1

PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_ROOT/borromeanrings.toml" "$changed_file" "$lockfile_exists" >"$log" 2>&1 <<'PY'
import sys
from pathlib import Path

from meta_harness.spine import load_config
from meta_harness.supply_chain import lockfile_verdict

cfg = load_config(sys.argv[1])
changed = [line for line in Path(sys.argv[2]).read_text(encoding="utf-8").splitlines() if line]
verdict = lockfile_verdict(
    changed,
    lockfile=cfg.supply_chain_lockfile,
    manifests=cfg.supply_chain_manifests,
    lockfile_exists=sys.argv[3] == "1",
)
print(verdict.message)
sys.exit({"pass": 0, "noop": 3}.get(verdict.status, 1))
PY
code=$?
emit_receipt "$id" "$cmd" "$code" "$log" "$(borromeanrings_status_for_code "$code")"
[ "$code" -eq "$BORROMEANRINGS_NOOP_EXIT" ] && exit 0
exit "$code"
