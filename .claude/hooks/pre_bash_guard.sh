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
  *"rm -rf /"* | *"rm -rf ~"*)
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

# What git subcommand is this, however the invocation is spelled? Matching the literal
# substring "git commit" misses every form that puts something between the two words --
# a global option, a directory switch, a leading VAR=value environment assignment -- and
# those are exactly the spellings that walked past this guard (issue #54). The shell
# pattern below is a cheap pre-filter; the parser decides. Fail-open on any error, as
# everywhere else here: the gate check is the backstop.
git_action=""
case "$cmd" in
  *git*commit* | *git*push*)
    git_action="$(PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$cmd" <<'SUBCMD' 2>/dev/null || true
import sys

try:
    from meta_harness.git_identity import git_subcommand

    print(git_subcommand(sys.argv[1]))
except Exception:
    print("")
SUBCMD
)" ;;
esac

# Protected-branch guard (Tier A collaboration): block 'git commit'/'git push'
# while ON a declared [collaboration].protected_branches branch — work belongs on
# feature branches (Gitflow-lite, ADR-0021). Local aid; the platform branch
# protection is the backstop. Fail-open on any error.
case "$git_action" in
  commit | push)
    branch="$(git -C "$PROJECT_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo HEAD)"
    reason="$(PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - \
      "$PROJECT_DIR/borromeanrings.toml" "$branch" 2>/dev/null <<'PY'
import sys

try:
    from meta_harness.spine import load_config

    cfg = load_config(sys.argv[1])
    branch = sys.argv[2]
    if branch in cfg.collaboration_protected_branches:
        print(
            f"'{branch}' is a protected branch (Gitflow-lite, ADR-0021): commit on a "
            f"work branch instead (e.g. feat/<name>, fix/<name>) and merge via PR."
        )
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
case "$git_action" in
  commit | push)
    reason="$(
      cfg_name="$(git -C "$PROJECT_DIR" config user.name 2>/dev/null || true)" \
      cfg_email="$(git -C "$PROJECT_DIR" config user.email 2>/dev/null || true)" \
      cmd_text="$cmd" \
      PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_DIR/borromeanrings.toml" <<'PY'
import os
import sys

try:
    from meta_harness.git_identity import (
        Identity,
        command_override_violation,
        configured_violation,
    )
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
    else:
        # Correct repo config does not mean a correct COMMIT: --author,
        # -c user.email= and the GIT_AUTHOR_*/GIT_COMMITTER_* variables each
        # override config for one invocation, and configured_violation cannot
        # see any of them (issue #54, ADR-0017).
        o = command_override_violation(os.environ.get("cmd_text", ""), declared)
        if o:
            print(
                f"Git identity override refused: {o}. borromeanRings requires "
                f"{cfg.git_name} <{cfg.git_email}> for commits in this repo."
            )
except Exception:
    pass  # never block on guard error — fail open here (the gate is the backstop)
PY
    )"
    [ -n "$reason" ] && deny "$reason"
    ;;
esac
exit 0
