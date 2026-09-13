#!/usr/bin/env bash
# Commit-message gate (Tier A collaboration): every commit on base..HEAD must be
# Conventional (type(scope)?: subject, declared [collaboration].commit_types,
# subject length bound). Base = merge-base with the integration branch (dev,
# falling back to main; local or origin/). Merge commits exempt. Off when no
# commit_types are declared; skips when no base branch resolves (nothing to
# diff against). See docs/specs/SPEC-collaboration.md and ADR-0021.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="09_commits"
log="$RECEIPT_DIR/$id.log"
cmd="conventional commits over base..HEAD (declared [collaboration].commit_types)"

# Resolve the comparison base: first existing of dev/main (origin- or local-).
base=""
for candidate in origin/dev dev origin/main main; do
  if git -C "$PROJECT_ROOT" rev-parse --verify --quiet "$candidate" >/dev/null 2>&1; then
    base="$candidate"
    break
  fi
done

# Commit list: "<sha>\t<subject>" per line, merges excluded. Empty when no base
# (nothing to compare) — the Python side then validates nothing, by design.
commits=""
if [ -n "$base" ]; then
  merge_base="$(git -C "$PROJECT_ROOT" merge-base HEAD "$base" 2>/dev/null || true)"
  if [ -n "$merge_base" ]; then
    commits="$(git -C "$PROJECT_ROOT" log --no-merges --format='%H%x09%s' "$merge_base"..HEAD 2>/dev/null || true)"
  fi
fi

PYTHONPATH="$BORROMEANRINGS_HOME/src" BORROMEANRINGS_COMMITS="$commits" \
  borromeanrings_py - "$PROJECT_ROOT/borromeanrings.toml" >"$log" 2>&1 <<'PY'
import os
import sys

from meta_harness.collaboration import commit_violations
from meta_harness.spine import load_config

cfg = load_config(sys.argv[1])

if not cfg.collaboration_commit_types:
    print("commit convention not declared ([collaboration].commit_types empty) — rule off")
    sys.exit(0)

commits: list[tuple[str, str]] = []
for line in os.environ.get("BORROMEANRINGS_COMMITS", "").splitlines():
    sha, _, subject = line.partition("\t")
    if sha.strip():
        commits.append((sha, subject))

violations = commit_violations(
    commits, cfg.collaboration_commit_types, cfg.collaboration_subject_max_length
)
if violations:
    print("COMMIT VIOLATIONS:")
    for v in violations:
        print(f"  - {v}")
    sys.exit(1)
print(f"commits OK — {len(commits)} commit(s) on base..HEAD conform (or none to check)")
PY
code=$?
status="fail"
[ "$code" -eq 0 ] && status="pass"
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
