#!/usr/bin/env bash
# 13_adr — ADR-discipline gate.
#
# On a feature branch (name starts with a declared prefix, default `feat/`), a change
# that touches the source tree must also add or modify an ADR under docs/adr/ — so
# the decision behind a new capability is documented, not left to convention. Fills
# matrix rows D/H ("ADR present, not gated"). Git-derivable, threshold-free; off
# unless 13_adr is in [checks].required. Non-feature branches, doc/test-only changes,
# no base to diff, or a change that touches an ADR all pass. See SPEC-adr-discipline.md,
# ADR-0043.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="13_adr"
log="$RECEIPT_DIR/$id.log"
cmd="ADR discipline (feature touching src must record a decision)"

branch="$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo HEAD)"

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
  emit_receipt "$id" "$cmd" 0 "$log" "pass"
  exit 0
fi

# --relative yields paths relative to PROJECT_ROOT (correct for a git-root OR a
# subdirectory-governed project), so the src_dir / adr_dir prefixes match either way.
changed="$(git -C "$PROJECT_ROOT" diff --relative --name-only "$merge_base"...HEAD 2>/dev/null || true)"

PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_ROOT/borromeanrings.toml" "$branch" "$changed" >"$log" 2>&1 <<'PY'
import sys

from meta_harness.adr_discipline import adr_violation
from meta_harness.spine import load_config

cfg = load_config(sys.argv[1])
branch = sys.argv[2]
changed = [line for line in sys.argv[3].splitlines() if line.strip()]

violation = adr_violation(
    branch,
    changed,
    src_dir=cfg.src_dir,
    adr_dir=cfg.adr_dir,
    require_prefixes=cfg.adr_require_prefixes,
)
if violation:
    print(f"ADR DISCIPLINE: {violation}")
    sys.exit(1)
print(f"ADR discipline satisfied (branch '{branch}')")
PY
code=$?
status="fail"
[ "$code" -eq 0 ] && status="pass"
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
