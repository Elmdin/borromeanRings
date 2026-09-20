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
borromeanrings_base_ref base "$id" "$cmd" "$log" origin/dev dev origin/main main || true

# Commit list: "<sha>\t<subject>" per line, merges excluded. Empty when no base
# (nothing to compare) — the Python side then validates nothing, by design.
# A git query that FAILS must never read as "nothing changed" (#186): the verdict below
# is computed from what git returns, so an empty answer from a repository nobody could
# read would report a clean pass. `merge-base` exits 1 for "no common ancestor", which
# is an answer, not a failure — anything above that is.
commits=""
git_error=""
merge_base=""
if [ -n "$base" ]; then
  borromeanrings_git_capture merge_base git_error merge-base HEAD "$base"
  [ $? -le 1 ] || borromeanrings_cannot_read "$id" "$cmd" "$log" "this branch's base" "$git_error"
  if [ -n "$merge_base" ]; then
    borromeanrings_git_capture commits git_error log --no-merges --format='%H%x09%s' \
      "$merge_base..HEAD" ||
      borromeanrings_cannot_read "$id" "$cmd" "$log" "this branch's commits" "$git_error"
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
