#!/usr/bin/env bash
# Git-identity backstop: every commit unique to this branch must be authored by the
# identity declared in borromeo.toml ([git].name/email). Fail-closed on a wrong
# author. Not declared ⇒ pass (not enforced). Not a git repo ⇒ pass. This checks
# commit *provenance* (metadata that travels with the commit, so it holds in CI and
# fresh clones). The repo's transient `git config user.*` is the PreToolUse guard's
# concern (developer-time prevention), NOT the gate's — a CI runner legitimately has
# a different/unset config. See docs/specs/SPEC-git-identity.md and ADR-0017.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="06_git_identity"
log="$RECEIPT_DIR/$id.log"
cmd="branch commits authored by the declared [git] identity"

is_repo="$(git -C "$PROJECT_ROOT" rev-parse --is-inside-work-tree 2>/dev/null || echo false)"

# Authors of commits unique to this branch. Base = first of main / origin/main that
# exists (full-range check locally); otherwise just the tip non-merge commit (CI
# checks out a detached merge-ref with no local base — the guard already vetted each
# commit at creation, so the tip is a sufficient backstop).
authors=""
if [ "$is_repo" = "true" ]; then
  base=""
  for ref in main origin/main; do
    if git -C "$PROJECT_ROOT" rev-parse --verify -q "$ref" >/dev/null 2>&1; then base="$ref"; break; fi
  done
  if [ -n "$base" ]; then
    authors="$(git -C "$PROJECT_ROOT" log --no-merges --format='%an%x09%ae' "$base..HEAD" 2>/dev/null || true)"
  else
    authors="$(git -C "$PROJECT_ROOT" log --no-merges --format='%an%x09%ae' -1 HEAD 2>/dev/null || true)"
  fi
fi

PYTHONPATH="$BORROMEO_HOME/src" \
  BORROMEO_IS_REPO="$is_repo" BORROMEO_AUTHORS="$authors" \
  python3 - "$PROJECT_ROOT/borromeo.toml" >"$log" 2>&1 <<'PY'
import os
import sys

from meta_harness.git_identity import Identity, author_violations, is_enforced
from meta_harness.spine import load_config

cfg = load_config(sys.argv[1])
declared = Identity(name=cfg.git_name, email=cfg.git_email)

if not is_enforced(declared):
    print("no [git] identity declared — identity enforcement off (pass)")
    sys.exit(0)
if os.environ.get("BORROMEO_IS_REPO") != "true":
    print("not a git repository — nothing to attribute (pass)")
    sys.exit(0)

authors = []
for line in os.environ.get("BORROMEO_AUTHORS", "").splitlines():
    if not line.strip():
        continue
    name, _, email = line.partition("\t")
    authors.append(Identity(name=name, email=email))

offenders = author_violations(authors, declared)
if offenders:
    print(f"COMMITS BY THE WRONG AUTHOR (must be {cfg.git_name} <{cfg.git_email}>):")
    for who in offenders:
        print(f"  - {who}")
    sys.exit(1)
print(f"git identity OK — branch commits authored by {cfg.git_name} <{cfg.git_email}>")
PY
code=$?
status="fail"
[ "$code" -eq 0 ] && status="pass"
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
