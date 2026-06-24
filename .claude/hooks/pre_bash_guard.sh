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

# Safe to install globally: do nothing unless this workspace is borromeanRings-governed.
[ -f "$PROJECT_DIR/borromeanrings.toml" ] || exit 0

input="$(cat)"
cmd="$(printf '%s' "$input" | python3 -c "import json,sys; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || echo '')"

deny() {
  python3 -c "import json,sys; print(json.dumps({'hookSpecificOutput':{'hookEventName':'PreToolUse','permissionDecision':'deny','permissionDecisionReason':sys.argv[1]}}))" "$1"
  exit 0
}

case "$cmd" in
  *"rm -rf /"* | *"rm -rf ~"* | *"rm -rf /*"*)
    deny "Refusing destructive recursive delete of a root or home path." ;;
  *":(){ :|:& };:"*)
    deny "Refusing fork bomb." ;;
  *"git push --force"* | *"git push -f"*)
    deny "Refusing force-push. Use --force-with-lease deliberately if truly required." ;;
  *"git reset --hard"*)
    deny "Refusing 'git reset --hard' via guard; run it manually if intended." ;;
  *"DROP TABLE"* | *"DROP DATABASE"*)
    deny "Refusing destructive SQL DROP." ;;
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
