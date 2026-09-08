#!/usr/bin/env bash
# demo.sh — a scripted, reproducible walk-through of borromeanRings governing a project.
#
# Builds a throwaway Python project in a temp dir, has THIS borromeanRings govern it by
# reference (init.sh), and walks the gate through every verdict a newcomer should be
# able to recognise: a HOLLOW green (checks that inspected nothing), a REAL green, a
# RED (a type/test violation), green again after the fix, then adopt.sh + status.sh.
#
# It is itself a test: every step asserts the exact verdict it expects and the script
# exits non-zero on the first deviation. The transcript it prints is what README.md
# quotes. See docs/DEMO.md.
#
#   ./demo.sh           # run, then delete the temp project
#   ./demo.sh --keep    # run, leave the temp project on disk for a look
set -uo pipefail

BORROMEANRINGS_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEEP=0
for arg in "$@"; do
  case "$arg" in
    --keep) KEEP=1 ;;
    *) echo "demo: unknown argument '$arg' (usage: ./demo.sh [--keep])" >&2; exit 2 ;;
  esac
done

# --- preconditions: the same toolchain the Python checks shell out to ------------------
for tool in python3 git ruff mypy pytest bandit; do
  command -v "$tool" >/dev/null 2>&1 || {
    echo "demo: '$tool' not on PATH — install the check toolchain first (pip install -e '.[dev]')" >&2
    exit 2
  }
done

DEMO="$(mktemp -d "${TMPDIR:-/tmp}/borromeanrings-demo.XXXXXX")" || exit 2
cleanup() {
  if [ "$KEEP" = "1" ]; then
    echo "demo: kept $DEMO"
  else
    rm -rf "$DEMO"
  fi
}
trap cleanup EXIT

# --- helpers ------------------------------------------------------------------------------
STEP=0
step() {                       # step <title>: announce a step of the walk-through
  STEP=$((STEP + 1))
  printf '\n### %d. %s\n' "$STEP" "$1"
}
show() {                       # show <cmd...>: echo the command, run it, capture + print output
  printf '$ %s\n' "$*"
  OUT="$("$@" 2>&1)"
  RC=$?
  printf '%s\n' "$OUT"
  return 0
}
expect() {                     # expect <pattern> <why>: the last output must contain the pattern
  if ! grep -qF -- "$1" <<<"$OUT"; then
    echo "demo: DEVIATION at step $STEP — expected output to contain '$1' ($2)" >&2
    exit 1
  fi
}
reject() {                     # reject <pattern> <why>: the last output must NOT contain the pattern
  if grep -qF -- "$1" <<<"$OUT"; then
    echo "demo: DEVIATION at step $STEP — output must not contain '$1' ($2)" >&2
    exit 1
  fi
}
expect_rc() {                  # expect_rc <code> <why>: the last command's exit code
  if [ "$RC" != "$1" ]; then
    echo "demo: DEVIATION at step $STEP — exit code $RC, expected $1 ($2)" >&2
    exit 1
  fi
}
gate() {                       # run the gate against the demo project; print the real command
  printf '$ BORROMEANRINGS_PROJECT=%s %s/verify.sh\n' "$DEMO" "$BORROMEANRINGS_HOME"
  OUT="$(BORROMEANRINGS_PROJECT="$DEMO" bash "$BORROMEANRINGS_HOME/verify.sh" 2>&1)"
  RC=$?
  printf '%s\n' "$OUT"
  return 0
}

echo "borromeanRings demo — governing a throwaway project at $DEMO"
echo "borromeanRings lives at $BORROMEANRINGS_HOME (nothing is copied; the project references it)"

# --- 1. an empty project, governed ------------------------------------------------------
step "Govern an empty project (init.sh)"
git -C "$DEMO" init -q
show bash "$BORROMEANRINGS_HOME/init.sh" "$DEMO"
expect_rc 0 "init.sh must succeed"
[ -f "$DEMO/borromeanrings.toml" ] || { echo "demo: DEVIATION — no borromeanrings.toml written" >&2; exit 1; }
[ -f "$DEMO/.claude/settings.json" ] || { echo "demo: DEVIATION — no .claude/settings.json written" >&2; exit 1; }

# --- 2. the hollow green -----------------------------------------------------------------
step "Run the gate on nothing: a HOLLOW green"
gate
expect_rc 0 "an empty project must not fail the gate"
expect "RESULT: PASS" "greenfield is green"
expect "inspected NOTHING: 4 of 7" "the gate must say which checks looked at nothing"

# --- 3. real code, real green ------------------------------------------------------------
step "Add real code and tests: a REAL green"
mkdir -p "$DEMO/src/app" "$DEMO/tests"
printf '# app\n' >"$DEMO/README.md"
cat >"$DEMO/pyproject.toml" <<'EOF'
[project]
name = "app"
version = "0.0.0"
requires-python = ">=3.10"
[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
[tool.coverage.run]
source = ["src"]
branch = true
EOF
: >"$DEMO/src/app/__init__.py"
printf 'def add(a: int, b: int) -> int:\n    return a + b\n' >"$DEMO/src/app/core.py"
printf 'from app.core import add\n\n\ndef test_add() -> None:\n    assert add(2, 3) == 5\n' >"$DEMO/tests/test_core.py"
sed -i 's/^package = ""/package = "app"/' "$DEMO/borromeanrings.toml"
git -C "$DEMO" add -A
git -C "$DEMO" -c user.name=demo -c user.email=demo@example.com commit -qm "chore: demo fixture"
echo "(wrote src/app/core.py, tests/test_core.py, pyproject.toml; set [project].package = \"app\")"
gate
expect_rc 0 "a correct project must pass"
expect "RESULT: PASS" "real code passes"
reject "inspected NOTHING" "every check inspected something now"

# --- 4. a violation: red -----------------------------------------------------------------
step "Introduce a violation (return a str from an int function): RED"
printf 'def add(a: int, b: int) -> int:\n    return "oops"\n' >"$DEMO/src/app/core.py"
gate
expect_rc 1 "the gate must fail closed"
expect "RESULT: FAIL" "the violation is caught"
expect "30_typecheck   FAIL" "mypy catches the return type"
expect "40_test        FAIL" "the test catches the behaviour"

# --- 5. the fix: green again ---------------------------------------------------------------
step "Fix it: green again"
printf 'def add(a: int, b: int) -> int:\n    return a + b\n' >"$DEMO/src/app/core.py"
gate
expect_rc 0 "the fixed project passes"
expect "RESULT: PASS" "fixed"

# --- 6. adopt the recommended set ----------------------------------------------------------
step "Adopt the recommended quality/security checks (adopt.sh)"
show bash "$BORROMEANRINGS_HOME/adopt.sh" "$DEMO"
expect_rc 0 "adopt.sh must succeed"
expect "added [" "adopt adds checks"
expect "seeded" "ratchet baselines are seeded from the current state"
gate
expect_rc 0 "the adopted set is green on first run (baselines seeded from current)"
expect "RESULT: PASS" "adopted and green"

# --- 7. status -------------------------------------------------------------------------------
step "Ask the project how it is governed (status.sh)"
printf '$ cd %s && %s\n' "$DEMO" "$BORROMEANRINGS_HOME/status.sh"
OUT="$(cd "$DEMO" && bash "$BORROMEANRINGS_HOME/status.sh" 2>&1)"
RC=$?
printf '%s\n' "$OUT"
expect_rc 0 "status is advisory and exits 0"
expect "Governed:     yes" "the project reports as governed"
expect "Last verdict: PASS" "the last verdict is the green we just saw"
expect "Enforcement: AUTO" "init.sh wired all hooks"

echo
echo "demo: every step matched its expected verdict."
