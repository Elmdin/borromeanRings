#!/usr/bin/env bash
# borromeanRings generate — the `headless` GENERATOR ADAPTER (SPEC-generator.md §3.2).
#
# Drives the same generate -> gate -> retry -> escalate loop the Stop hook drives, but
# with a scripted generator instead of an agent and with no substrate underneath: it
# runs `[generator].command` from the governed project's borromeanrings.toml, decides
# what happens next, and runs the gate itself. That makes the loop testable end to end
# (#202) and drivable without a Stop hook (#144).
#
# Usage:  ./generate.sh [project_path]
#   project_path defaults to $BORROMEANRINGS_PROJECT / $CLAUDE_PROJECT_DIR / $PWD.
#
# Environment:
#   BORROMEANRINGS_RUN_KEY            attempt-counter key (default "headless"); two keys
#                                     in one project keep independent counters.
#   BORROMEANRINGS_GENERATOR_TIMEOUT  wall-clock bound per generator invocation (540 s).
#   BORROMEANRINGS_GATE_TIMEOUT       wall-clock bound per gate run (540 s).
#
# Exit codes:  0 green · 1 escalated (the human takes over) · 2 generator-failed
#              3 refused (nothing to drive: no config, no declared command, no git).
#
# The command is invoked as `<command> <project_path> <last_verdict_path|"">` with
# BORROMEANRINGS_{FAILING_CHECKS,ATTEMPT,CAP,GENERATOR} in the environment, cwd at the
# project, stdin closed and output captured. What it may NOT do is the point: it must
# not run the gate itself (a self-run gate is a self-report — ADR-0049), must not write
# under .meta-harness/ (enforced here, not requested), must not push, and cannot see,
# reset or raise the retry bound. CAP and the decision live in meta_harness.generator,
# shared with .claude/hooks/stop_gate.sh so the two adapters cannot drift.
#
# See docs/specs/SPEC-generator.md, ADR-0071 and ADR-0078.
set -uo pipefail

BORROMEANRINGS_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$BORROMEANRINGS_HOME/src"

# Pre-flight only: "there is nothing to drive", before any attempt has been made. It
# deliberately does not clear the attempt counter, because it runs before one is written.
# Once the loop has begun, use abort() — see there for why the distinction is load-bearing.
refuse() {
  echo "borromeanRings generate: $1" >&2
  exit 3
}

raw_project="${1:-${BORROMEANRINGS_PROJECT:-${CLAUDE_PROJECT_DIR:-$PWD}}}"
PROJECT_ROOT="$(cd "$raw_project" 2>/dev/null && pwd)" ||
  refuse "no such project directory: $raw_project"
CONFIG="$PROJECT_ROOT/borromeanrings.toml"
[ -f "$CONFIG" ] ||
  refuse "no borromeanrings.toml in $PROJECT_ROOT — run borromeanRings's init.sh there first."

# CAP and the declared command, in one read. An unreadable CAP falls back to a single
# attempt: the smallest bound still hands control to the human, where guessing an
# unbounded one never would. An absent command is a refusal, never a default to some
# built-in fixer (SPEC-generator.md §3.2).
if ! generator_meta="$(
  PYTHONPATH="$PY" python3 - "$CONFIG" 2>&1 <<'PY'
import sys

from meta_harness.generator import CAP
from meta_harness.spine import load_config

print(CAP)
print(load_config(sys.argv[1]).generator_command)
PY
)"; then
  # Say which failure this is. A malformed borromeanrings.toml, an absent python3 and an
  # undeclared command are three different problems, and reporting all three as "no
  # [generator].command" sends a maintainer to the wrong section of the wrong file.
  refuse "cannot read $CONFIG — $(printf '%s' "$generator_meta" | tail -1)"
fi
CAP="$(printf '%s\n' "$generator_meta" | sed -n 1p)"
GEN_COMMAND="$(printf '%s\n' "$generator_meta" | sed -n 2p)"
case "$CAP" in '' | *[!0-9]* | 0) CAP=1 ;; esac
[ -n "$GEN_COMMAND" ] ||
  refuse "no [generator].command declared in $CONFIG — there is no default generator."

# Unset ⇒ the default key; set-but-empty ⇒ a refusal, not a silent default: a caller that
# meant to pass a key and passed nothing has a bug, and this is an orchestrator's seam.
RUN_KEY="${BORROMEANRINGS_RUN_KEY-headless}"
case "$RUN_KEY" in '' | . | .. | */*) refuse "invalid BORROMEANRINGS_RUN_KEY: '$RUN_KEY'" ;; esac

EVIDENCE="$PROJECT_ROOT/.meta-harness"
COUNTER_DIR="$EVIDENCE/stop_attempts"
LOG_DIR="$EVIDENCE/generator/$RUN_KEY"
COUNTER="$COUNTER_DIR/$RUN_KEY"
mkdir -p "$COUNTER_DIR" "$LOG_DIR" || refuse "cannot write the evidence area under $EVIDENCE"

# Provenance for the verdict: the basename of the program actually executed. A command
# that wraps a script in an interpreter ("bash x.sh") therefore records the interpreter —
# point [generator].command at the script itself to be named by it. Self-declared and
# never consulted by the gate, exactly like a git author line (ADR-0071 §4).
export BORROMEANRINGS_GENERATOR="headless:$(basename "${GEN_COMMAND%% *}")"
export BORROMEANRINGS_CAP="$CAP"

# Wall-clock bound. Duplicated from checks/_lib.sh and .claude/hooks/_lib.sh rather than
# sourced: this driver is substrate-neutral (it must not reach into .claude/) and check
# machinery (RECEIPT_DIR, receipts) is not its business.
TIMEOUT_BIN=""
if command -v timeout >/dev/null 2>&1; then
  TIMEOUT_BIN="timeout"
elif command -v gtimeout >/dev/null 2>&1; then
  TIMEOUT_BIN="gtimeout"
fi
bounded() {
  local secs="$1"
  shift
  if [ -n "$TIMEOUT_BIN" ] && [ "$secs" != "0" ]; then
    "$TIMEOUT_BIN" -k 10 "$secs" "$@"
  else
    "$@"
  fi
}

# The OID of the working tree, dirty included: tracked edits and untracked-not-ignored
# files are in, .gitignore'd paths (.meta-harness/, caches) are out (SPEC-executor.md
# §2.2). Empty ⇒ the caller refuses; a driver that cannot tell whether the project
# changed cannot tell "wrote a change" from "did nothing".
dirty_tree_oid() {
  # A private scratch DIRECTORY, so git creates the index file itself: git rejects a
  # pre-created empty one ("index file smaller than expected").
  local scratch index oid=""
  scratch="$(mktemp -d "${TMPDIR:-/tmp}/borromeanrings-index.XXXXXX")" || return 1
  index="$scratch/index"
  if GIT_INDEX_FILE="$index" git -C "$PROJECT_ROOT" add -A >/dev/null 2>&1; then
    oid="$(GIT_INDEX_FILE="$index" git -C "$PROJECT_ROOT" write-tree 2>/dev/null)"
  fi
  rm -rf "$scratch"
  [ -n "$oid" ] || return 1
  printf '%s' "$oid"
}

# What the gate can see: `(branch, head, dirty tree)` — the executor's snapshot identity
# (SPEC-executor.md §2.2), not the tree alone.
#
# A CORRECTION to SPEC-generator.md N3, which said the driver compares the dirty-tree OID.
# It is not enough. Branch-reading and history-reading checks are part of the required set
# (08_branch, 09_commits, 11_changelog, 13_adr, 34_api_diff), so a generator that amends a
# commit message or renames a branch has changed what the gate sees while leaving the tree
# byte-identical. Under a tree-only comparison that generator is told it did nothing and
# the run escalates — with the fix already in place. See ADR-0078.
snapshot_identity() {
  local tree
  tree="$(dirty_tree_oid)" || return 1
  printf '%s %s %s' \
    "$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null)" \
    "$(git -C "$PROJECT_ROOT" rev-parse HEAD 2>/dev/null)" \
    "$tree"
}

# Fingerprint the gate's evidence area into $1, excluding the log this driver is itself
# writing. Conformance §5: nothing under .meta-harness/ may move while the generator runs.
snapshot_evidence() {
  PYTHONPATH="$PY" python3 - "$EVIDENCE" "$1" "$2" <<'PY'
import json
import sys

from meta_harness.generator import snapshot_evidence

root, out, exclude = sys.argv[1], sys.argv[2], sys.argv[3]
with open(out, "w", encoding="utf-8") as handle:
    json.dump(snapshot_evidence(root, exclude=exclude or None), handle)
PY
}

# Every way the evidence area moved since $1 was taken, one reason per line.
evidence_writes() {
  PYTHONPATH="$PY" python3 - "$EVIDENCE" "$1" "$2" <<'PY'
import json
import sys

from meta_harness.generator import evidence_writes, snapshot_evidence

root, before_path, exclude = sys.argv[1], sys.argv[2], sys.argv[3]
with open(before_path, encoding="utf-8") as handle:
    before = json.load(handle)
after = snapshot_evidence(root, exclude=exclude or None)
for reason in evidence_writes(before, after):
    print(reason)
PY
}

# The failing check ids, read off the verdict's own rows so a change to the printed
# summary cannot silently drop a name (N2, conformance §5.4).
failing_check_ids() {
  PYTHONPATH="$PY" python3 - "$PROJECT_ROOT" 2>/dev/null <<'PY'
import sys

from meta_harness.generator import failing_check_ids
from meta_harness.verdict import read_last_verdict

verdict = read_last_verdict(sys.argv[1])
print(",".join(failing_check_ids(verdict.checks if verdict is not None else ())))
PY
}

# The decision itself — the pure function, nothing more.
decide() {
  PYTHONPATH="$PY" python3 - "$@" 2>/dev/null <<'PY' || true
import sys

from meta_harness.generator import next_action

attempt, cap, gate_ok, tree_changed, exit_code = sys.argv[1:6]
print(next_action(int(attempt), int(cap), gate_ok == "1", tree_changed == "1", int(exit_code)))
PY
}

# A failure once the loop has begun is NOT a refusal. Something was attempted — possibly
# the very thing that broke the repository — so the run must reach a human rather than
# report "nothing to drive" (exit 3) to an orchestrator that would skip it and move on.
# Escalation, with the counter cleared like any other terminal outcome.
abort() {
  echo "borromeanRings generate: $1" >&2
  finish 1 "escalated (the driver could not continue)"
}

finish() {
  local code="$1" action="$2"
  rm -f "$COUNTER"
  echo
  echo "  borromeanRings headless generator  (project: $PROJECT_ROOT, run-key: $RUN_KEY)"
  echo "  generator: $BORROMEANRINGS_GENERATOR   attempts: $attempt of $CAP"
  echo "  GENERATOR-RESULT: $action"
  echo
  if [ "$code" -ne 0 ]; then
    echo "ESCALATION: borromeanRings headless run ended '$action' — handing control to the human." >&2
  fi
  exit "$code"
}

attempt=1
last_verdict=""
export BORROMEANRINGS_FAILING_CHECKS=""

while :; do
  # The attempt counter is the GATE's, written here and never read back: within a run the
  # loop's own counter is authoritative, so editing this file buys a generator nothing
  # (and is caught below anyway). It exists so a human, the ledger, and a second driver
  # invocation on the same run key can see where the run stands. Written BEFORE the
  # snapshot, so the driver's own bookkeeping is never mistaken for the generator's.
  printf '%s' "$attempt" >"$COUNTER"
  log="$LOG_DIR/$attempt.log"
  : >"$log" || abort "cannot write the generator log at $log"
  before="$(mktemp "${TMPDIR:-/tmp}/borromeanrings-evidence.XXXXXX")" ||
    abort "cannot create a scratch file for the evidence snapshot"
  snapshot_evidence "$before" "$log" || abort "cannot fingerprint the evidence area"
  state_before="$(snapshot_identity)" ||
    abort "cannot read the state of $PROJECT_ROOT — a git repository is required."

  echo "borromeanRings headless: attempt $attempt/$CAP — running the generator" >&2
  BORROMEANRINGS_ATTEMPT="$attempt" bounded "${BORROMEANRINGS_GENERATOR_TIMEOUT:-540}" \
    bash -c "cd \"\$1\" && shift && $GEN_COMMAND \"\$@\"" \
    borromeanrings-generator "$PROJECT_ROOT" "$PROJECT_ROOT" "$last_verdict" \
    >"$log" 2>&1 </dev/null
  gen_code=$?

  violations="$(evidence_writes "$before" "$log")" ||
    violations="the evidence area could not be re-read (fail-closed)"
  rm -f "$before"
  if [ -n "$violations" ]; then
    {
      echo "GENERATOR WROTE UNDER .meta-harness/ — the gate's evidence is not the generator's:"
      printf '  %s\n' "$violations"
    } | tee -a "$log" >&2
    gen_code=125 # "could not be trusted to have run honestly", not "it exited 125"
  fi

  state_after="$(snapshot_identity)" ||
    abort "cannot read the state of $PROJECT_ROOT after the generator ran."
  # next_action's `tree_changed` means "did anything the gate can see move?" — branch,
  # head and dirty tree, not the tree alone (see snapshot_identity).
  tree_changed=0
  [ "$state_before" != "$state_after" ] && tree_changed=1

  gate_ok=0
  if [ "$gen_code" -eq 0 ] && [ "$tree_changed" -eq 1 ]; then
    BORROMEANRINGS_PROJECT="$PROJECT_ROOT" bounded "${BORROMEANRINGS_GATE_TIMEOUT:-540}" \
      bash "$BORROMEANRINGS_HOME/verify.sh"
    [ $? -eq 0 ] && gate_ok=1
    last_verdict="$EVIDENCE/last_verdict.json"
    # N2 is a requirement, not a best effort: a retry that cannot name what failed is a
    # retry the generator is guessing at, so failing to read them ends the run.
    failing="$(failing_check_ids)" ||
      abort "cannot read the failing check ids from $last_verdict"
    export BORROMEANRINGS_FAILING_CHECKS="$failing"
  fi

  case "$(decide "$attempt" "$CAP" "$gate_ok" "$tree_changed" "$gen_code")" in
    green) finish 0 "green" ;;
    retry) attempt=$((attempt + 1)) ;;
    escalated) finish 1 "escalated" ;;
    generator-failed) finish 2 "generator-failed" ;;
    *) finish 1 "escalated (the loop could not decide — fail-closed)" ;;
  esac
done
