#!/usr/bin/env bash
# Git-identity backstop: every commit unique to this branch must be authored by the
# identity declared in borromeanrings.toml ([git].name/email). Fail-closed on a wrong
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
# A git query that FAILS must never read as "no commits to attribute" (#186): the
# verdict below is computed entirely from this list, so an empty one from a broken
# repository would print "git identity OK" over commits nobody read.
authors=""
git_error=""
err="$RECEIPT_DIR/$id.git-error"
if [ "$is_repo" = "true" ]; then
  base=""
  for ref in main origin/main; do
    if git -C "$PROJECT_ROOT" rev-parse --verify -q "$ref" >/dev/null 2>&1; then base="$ref"; break; fi
  done
  if [ -n "$base" ]; then
    authors="$(git -C "$PROJECT_ROOT" log --no-merges --format='%an%x09%ae' "$base..HEAD" 2>"$err")" ||
      git_error="$(tail -3 "$err")"
  else
    authors="$(git -C "$PROJECT_ROOT" log --no-merges --format='%an%x09%ae' -1 HEAD 2>"$err")" ||
      git_error="$(tail -3 "$err")"
  fi
  rm -f "$err"
fi

PYTHONPATH="$BORROMEANRINGS_HOME/src" \
  BORROMEANRINGS_IS_REPO="$is_repo" BORROMEANRINGS_AUTHORS="$authors" \
  BORROMEANRINGS_GIT_ERROR="$git_error" \
  BORROMEANRINGS_NOOP_EXIT="$BORROMEANRINGS_NOOP_EXIT" \
  borromeanrings_py - "$PROJECT_ROOT/borromeanrings.toml" >"$log" 2>&1 <<'PY'
import os
import sys

from meta_harness.git_identity import (
    Identity,
    author_violations,
    is_enforced,
    required_identity,
)
from meta_harness.spine import load_config

cfg = load_config(sys.argv[1])
# What the project requires of an author: the address, or the display name too
# ([git].require, #229). Only the fields the declared identity carries are checked.
declared = required_identity(cfg.git_name, cfg.git_email, cfg.git_require)

NOOP = int(os.environ["BORROMEANRINGS_NOOP_EXIT"])

if not is_enforced(declared):
    # Nothing was inspected, and ADR-0049 says so out loud: "not enforced" must never
    # be indistinguishable from "every commit was checked and is right".
    print("no [git] identity declared — nothing to attribute")
    sys.exit(NOOP)
if os.environ.get("BORROMEANRINGS_IS_REPO") != "true":
    print("not a git repository — nothing to attribute")
    sys.exit(NOOP)

git_error = os.environ.get("BORROMEANRINGS_GIT_ERROR", "").strip()
if git_error:
    print("could not list this branch's commits, so their authors cannot be checked:")
    print(f"  {git_error}")
    sys.exit(1)

authors = []
for line in os.environ.get("BORROMEANRINGS_AUTHORS", "").splitlines():
    if not line.strip():
        continue
    name, _, email = line.partition("\t")
    authors.append(Identity(name=name, email=email))

offenders = author_violations(authors, declared)
if offenders:
    must_be = f"{declared.name} <{declared.email}>" if declared.name else declared.email
    print(f"COMMITS BY THE WRONG AUTHOR (must be {must_be}):")
    for who in offenders:
        print(f"  - {who}")
    sys.exit(1)
checked = f"{declared.name} <{declared.email}>" if declared.name else declared.email
print(f"git identity OK — branch commits authored by {checked}")
PY
code=$?
status="$(borromeanrings_status_for_code "$code")"
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
[ "$code" -eq "$BORROMEANRINGS_NOOP_EXIT" ] && exit 0
exit "$code"
