#!/usr/bin/env bash
# PreToolUse(Bash) — defense-in-depth guard. Denies a small, conservative
# deny-list of obviously destructive commands. This is a guard, not the policy
# engine; the normal permission prompt still applies to everything else.
set -uo pipefail

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
exit 0
