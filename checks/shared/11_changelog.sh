#!/usr/bin/env bash
# Changelog discipline (Keep a Changelog): the changelog exists with an
# 'Unreleased' section; optionally (strict) it must be updated when source
# changes on this branch. Opt-in via [changelog].enabled. The strict diff-rule is
# separately gated by require_entry_on_src_change (retroactive — enable when a PR
# queue is clear). See docs/specs/SPEC-changelog.md and ADR-0028.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="11_changelog"
log="$RECEIPT_DIR/$id.log"
cmd="changelog discipline (presence + Unreleased; optional entry-on-source-change)"

# Changed files base..HEAD (same base resolution as 09_commits), for the strict rule.
base=""
for candidate in origin/dev dev origin/main main; do
  if git -C "$PROJECT_ROOT" rev-parse --verify --quiet "$candidate" >/dev/null 2>&1; then
    base="$candidate"
    break
  fi
done
# A git query that FAILS must never read as "nothing changed" (#186): the verdict below
# is computed from what git returns, so an empty answer from a repository nobody could
# read would report a clean pass. `merge-base` exits 1 for "no common ancestor", which
# is an answer, not a failure — anything above that is.
changed=""
git_error=""
merge_base=""
if [ -n "$base" ]; then
  borromeanrings_git_capture merge_base git_error merge-base HEAD "$base"
  [ $? -le 1 ] || borromeanrings_cannot_read "$id" "$cmd" "$log" "this branch's base" "$git_error"
  if [ -n "$merge_base" ]; then
    borromeanrings_git_capture changed git_error diff --name-only "$merge_base..HEAD" ||
      borromeanrings_cannot_read "$id" "$cmd" "$log" "what this branch changed" "$git_error"
  fi
fi

PYTHONPATH="$BORROMEANRINGS_HOME/src" BORROMEANRINGS_CHANGED="$changed" \
  borromeanrings_py - "$PROJECT_ROOT" "$PROJECT_ROOT/borromeanrings.toml" >"$log" 2>&1 <<'PY'
import os
import sys
from pathlib import Path

from meta_harness.changelog import presence_violation, src_change_violation
from meta_harness.spine import load_config

root, config_path = Path(sys.argv[1]), sys.argv[2]
cfg = load_config(config_path)

if not cfg.changelog_enabled:
    print("changelog discipline not enabled ([changelog].enabled=false) — rule off")
    sys.exit(0)

path = cfg.changelog_path
full = root / path
text = full.read_text(encoding="utf-8", errors="replace") if full.exists() else None

problems: list[str] = []
presence = presence_violation(text, path)
if presence:
    problems.append(presence)

if cfg.changelog_require_entry_on_src_change:
    changed = [p for p in os.environ.get("BORROMEANRINGS_CHANGED", "").splitlines() if p.strip()]
    strict = src_change_violation(changed, cfg.src_dir, path)
    if strict:
        problems.append(strict)

if problems:
    print("CHANGELOG VIOLATIONS:")
    for problem in problems:
        print(f"  - {problem}")
    sys.exit(1)
print("changelog OK")
PY
code=$?
status="fail"
[ "$code" -eq 0 ] && status="pass"
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
