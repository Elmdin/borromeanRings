#!/usr/bin/env bash
# PreToolUse(Bash) — defense-in-depth guard. Denies a small, conservative
# deny-list of obviously destructive commands, and blocks commits/pushes under
# the wrong git identity (preventive layer; gate check 06 is the backstop). This
# is a guard, not the policy engine; the normal permission prompt still applies
# to everything else. See docs/specs/SPEC-git-identity.md and ADR-0017.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BORROMEANRINGS_HOME="$(cd "$HERE/../.." && pwd)"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
. "$HERE/_lib.sh"

# Safe to install globally: do nothing unless this workspace is borromeanRings-governed.
[ -f "$PROJECT_DIR/borromeanrings.toml" ] || exit 0

# No dedupe needed here: a duplicate registration just re-checks the same
# command and reaches the same verdict (idempotent). The read stays bounded.
input="$(borromeanrings_read_stdin)"
cmd="$(printf '%s' "$input" | python3 -c "import json,sys; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || echo '')"

deny() {
  python3 -c "import json,sys; print(json.dumps({'hookSpecificOutput':{'hookEventName':'PreToolUse','permissionDecision':'deny','permissionDecisionReason':sys.argv[1]}}))" "$1"
  exit 0
}

# Is `$1` a real `git push --force` / `-f`? True only for a statement that
# INVOKES git push with a bare force flag — not for the safe `--force-with-lease`
# (which this guard permits), and not for a mere mention of the string inside
# another command (e.g. a `grep` pattern). We split the command into statements
# and inspect each: a substring match on the whole line conflated all three.
# `read` (not word-splitting) avoids glob-expanding the statements.
is_force_push() {
  local c="$1" seg
  c="${c//&&/$'\n'}"; c="${c//;/$'\n'}"; c="${c//|/$'\n'}"
  while IFS= read -r seg; do
    seg="${seg#"${seg%%[![:space:]]*}"}"  # left-trim whitespace
    case "$seg" in
      "git push" | "git push "*)
        case "$seg" in
          *--force-with-lease*) : ;;                     # safe force — allow
          *--force* | *" -f "* | *" -f") return 0 ;;     # bare force — deny
        esac ;;
    esac
  done <<<"$c"
  return 1
}

case "$cmd" in
  *"rm -rf /"* | *"rm -rf ~"* | *"rm -rf /*"*)
    deny "Refusing destructive recursive delete of a root or home path." ;;
  *":(){ :|:& };:"*)
    deny "Refusing fork bomb." ;;
  *"git reset --hard"*)
    deny "Refusing 'git reset --hard' via guard; run it manually if intended." ;;
  *"DROP TABLE"* | *"DROP DATABASE"*)
    deny "Refusing destructive SQL DROP." ;;
esac

is_force_push "$cmd" &&
  deny "Refusing bare force-push. Use --force-with-lease (allowed) so you never clobber unseen upstream commits."

# Protected-branch guard (trunk-based policy, ADR-0058, issue #75): deny any
# command that would land work directly on a declared
# [collaboration].protected_branches branch — commit/merge/rebase/cherry-pick/
# reset while ON one, a push to one in ANY spelling (origin main, HEAD:main,
# +main, refs/heads/main, --delete, --all), or deleting/force-moving one locally.
# The decision is meta_harness.trunk_policy (pure, unit-tested per matrix row);
# HEAD is read with a fixed argv. It is never narrower than the substring match it
# replaced (the floor). Local aid; server-side protection (#60) is the backstop.
# Fail-open on any error. See docs/specs/SPEC-branch-policy.md.
case "$cmd" in
  *git*)
    branch="$(git -C "$PROJECT_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo HEAD)"
    reason="$(BORROMEANRINGS_GUARD_CMD="$cmd" PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - \
      "$PROJECT_DIR/borromeanrings.toml" "$branch" 2>/dev/null <<'PY'
import os
import sys

try:
    from meta_harness.spine import load_config
    from meta_harness.trunk_policy import branch_policy_violation

    cfg = load_config(sys.argv[1])
    reason = branch_policy_violation(
        os.environ.get("BORROMEANRINGS_GUARD_CMD", ""),
        sys.argv[2],
        cfg.collaboration_protected_branches,
    )
    if reason:
        print(reason)
except Exception:
    pass  # fail open — the platform protection is the backstop
PY
    )"
    [ -n "$reason" ] && deny "$reason"
    ;;
esac

# Wrong git-identity guard: block 'git commit'/'git push' when the governed repo's
# configured identity doesn't match borromeanrings.toml [git]. Catches the systemic case
# (repo configured under the wrong account); the gate backstop catches the rest.
case "$cmd" in
  *"git commit"* | *"git push"*)
    reason="$(
      cfg_name="$(git -C "$PROJECT_DIR" config user.name 2>/dev/null || true)" \
      cfg_email="$(git -C "$PROJECT_DIR" config user.email 2>/dev/null || true)" \
      PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_DIR/borromeanrings.toml" <<'PY'
import os
import sys

try:
    from meta_harness.git_identity import Identity, configured_violation
    from meta_harness.spine import load_config

    cfg = load_config(sys.argv[1])
    declared = Identity(name=cfg.git_name, email=cfg.git_email)
    configured = Identity(
        name=os.environ.get("cfg_name", ""), email=os.environ.get("cfg_email", "")
    )
    v = configured_violation(configured, declared)
    if v:
        print(
            f"Wrong git identity for this repo: {v}. borromeanRings requires "
            f"{cfg.git_name} <{cfg.git_email}>. Fix: "
            f"git config user.name '{cfg.git_name}' && "
            f"git config user.email '{cfg.git_email}'."
        )
except Exception:
    pass  # never block on guard error — fail open here (the gate is the backstop)
PY
    )"
    [ -n "$reason" ] && deny "$reason"
    ;;
esac
exit 0
