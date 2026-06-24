#!/usr/bin/env bash
# Git-identity backstop: the repo's configured identity and every commit unique to
# this branch must be the identity declared in borromeo.toml ([git].name/email).
# Fail-closed on mismatch. Not declared ⇒ pass (not enforced). Not a git repo ⇒
# pass. The preventive layer is the PreToolUse guard; this catches what it missed.
# See docs/specs/SPEC-git-identity.md and ADR-0017.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="06_git_identity"
log="$RECEIPT_DIR/$id.log"
cmd="git identity matches declared [git] identity"

# Gather git facts from the GOVERNED repo (works when borromeo is referenced).
cfg_name="$(git -C "$PROJECT_ROOT" config user.name 2>/dev/null || true)"
cfg_email="$(git -C "$PROJECT_ROOT" config user.email 2>/dev/null || true)"
is_repo="$(git -C "$PROJECT_ROOT" rev-parse --is-inside-work-tree 2>/dev/null || echo false)"

# Authors of commits unique to this branch (base = main when it exists, else just HEAD).
authors=""
if [ "$is_repo" = "true" ]; then
  if git -C "$PROJECT_ROOT" rev-parse --verify -q main >/dev/null 2>&1; then
    range="main..HEAD"
  else
    range="HEAD -1"
  fi
  # NUL-free, one "name<TAB>email" per line.
  authors="$(git -C "$PROJECT_ROOT" log --no-merges --format='%an%x09%ae' $range 2>/dev/null || true)"
fi

PYTHONPATH="$BORROMEO_HOME/src" \
  BORROMEO_CFG_NAME="$cfg_name" BORROMEO_CFG_EMAIL="$cfg_email" \
  BORROMEO_IS_REPO="$is_repo" BORROMEO_AUTHORS="$authors" \
  python3 - "$PROJECT_ROOT/borromeo.toml" >"$log" 2>&1 <<'PY'
import os
import sys

from meta_harness.git_identity import Identity, author_violations, configured_violation, is_enforced
from meta_harness.spine import load_config

cfg = load_config(sys.argv[1])
declared = Identity(name=cfg.git_name, email=cfg.git_email)

if not is_enforced(declared):
    print("no [git] identity declared — identity enforcement off (pass)")
    sys.exit(0)
if os.environ.get("BORROMEO_IS_REPO") != "true":
    print("not a git repository — nothing to attribute (pass)")
    sys.exit(0)

configured = Identity(
    name=os.environ.get("BORROMEO_CFG_NAME", ""),
    email=os.environ.get("BORROMEO_CFG_EMAIL", ""),
)
authors = []
for line in os.environ.get("BORROMEO_AUTHORS", "").splitlines():
    if not line.strip():
        continue
    name, _, email = line.partition("\t")
    authors.append(Identity(name=name, email=email))

failed = False
reason = configured_violation(configured, declared)
if reason:
    failed = True
    print(f"CONFIGURED IDENTITY MISMATCH: {reason}")
    print(f"  fix: git -C <repo> config user.name '{cfg.git_name}' && "
          f"git -C <repo> config user.email '{cfg.git_email}'")

offenders = author_violations(authors, declared)
if offenders:
    failed = True
    print("COMMITS BY THE WRONG AUTHOR (must be "
          f"{cfg.git_name} <{cfg.git_email}>):")
    for who in offenders:
        print(f"  - {who}")

if failed:
    sys.exit(1)
print(f"git identity OK — configured + branch commits are {cfg.git_name} <{cfg.git_email}>")
PY
code=$?
status="fail"
[ "$code" -eq 0 ] && status="pass"
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
