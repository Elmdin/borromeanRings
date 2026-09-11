#!/usr/bin/env bash
# borromeanRings generate — the `headless` GENERATOR ADAPTER (SPEC-generator.md §3.2).
#
# Drives the same generate -> gate -> retry -> escalate loop the Stop hook drives, but
# with a scripted generator instead of an agent and with no substrate underneath: it
# runs `[generator].command` from the governed project's borromeanrings.toml, decides
# what happens next, and runs the gate itself. That makes the loop testable end to end
# (#202) and drivable without a Stop hook (#144).
#
# Usage:  ./generate.sh [--heavy] [project_path]
#   project_path defaults to $BORROMEANRINGS_PROJECT / $CLAUDE_PROJECT_DIR / $PWD.
#   --heavy gates each attempt with the CI-tier lane (same as BORROMEANRINGS_HEAVY=1).
#
# Environment:
#   BORROMEANRINGS_RUN_KEY            attempt-counter key (default "headless"); two keys
#                                     in one project keep independent counters.
#   BORROMEANRINGS_GENERATOR_TIMEOUT  wall-clock bound per generator invocation (540 s).
#   BORROMEANRINGS_GATE_TIMEOUT       wall-clock bound per gate run (540 s).
#                                     Both bounds need coreutils `timeout` (or `gtimeout`)
#                                     on PATH; without it the driver says so and runs
#                                     UNBOUNDED, because refusing to run at all would be
#                                     worse on a host that simply lacks it.
#
# Exit codes:  0 green · 1 escalated (the human takes over) · 2 generator-failed
#              3 refused (nothing to drive: no borromeanrings.toml, no [generator].command)
#              4 misconfigured (a config IS here and it is broken — a governed project
#                that would otherwise go ungated and unnoticed; deliberately NOT 3, which
#                an orchestrator may reasonably read as "skip this worktree").
# Refusal is pre-flight only: once an attempt is under way, any failure that stops the
# driver escalates instead (ADR-0078).
#
# The command is invoked as `<command> <project_path> <last_verdict_path|"">` with
# BORROMEANRINGS_{FAILING_CHECKS,ATTEMPT,CAP,GENERATOR} in the environment, cwd at the
# project, stdin closed and output captured. What it may NOT do is the point: it must
# not run the gate itself (a self-run gate is a self-report — ADR-0049), must not write
# under .meta-harness/ (enforced here, not requested), must not push, and cannot reset or
# raise the retry bound — the counter is one anchor for it, the gate's append-only verdict
# history is the other, and the higher of the two wins. CAP and the decision live in meta_harness.generator, shared with
# .claude/hooks/stop_gate.sh so the two adapters cannot drift.
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
  exit "${2:-3}"
}

warn() {
  echo "borromeanRings generate: $1" >&2
}

positional=""
for arg in "$@"; do
  case "$arg" in
    --heavy) export BORROMEANRINGS_HEAVY=1 ;;
    *) positional="$arg" ;;
  esac
done

raw_project="${positional:-${BORROMEANRINGS_PROJECT:-${CLAUDE_PROJECT_DIR:-$PWD}}}"
PROJECT_ROOT="$(cd "$raw_project" 2>/dev/null && pwd)" ||
  refuse "no such project directory: $raw_project"
CONFIG="$PROJECT_ROOT/borromeanrings.toml"
[ -f "$CONFIG" ] ||
  refuse "no borromeanrings.toml in $PROJECT_ROOT — run borromeanRings's init.sh there first."

# CAP and the declared command, in one read.
if ! generator_meta="$(
  PYTHONPATH="$PY" python3 - "$CONFIG" 2>&1 <<'PY'
import sys

from meta_harness.generator import CAP
from meta_harness.spine import load_config

print(CAP)
print(load_config(sys.argv[1]).generator_command)
PY
)"; then
  # "There is no config here" and "the config is present and broken" are different facts,
  # and the second is a governed project about to go ungated. Different exit code, so an
  # orchestrator branching on the number sees the difference, not only a reader of the text.
  refuse "cannot read $CONFIG — $(printf '%s' "$generator_meta" | tail -1)" 4
fi
CAP="$(printf '%s\n' "$generator_meta" | sed -n 1p)"
GEN_COMMAND="$(printf '%s\n' "$generator_meta" | sed -n 2p)"
case "$CAP" in
  '' | *[!0-9]* | 0)
    # Never silently: a collapsed bound turns the retry loop into zero retries, and the
    # operator would see only "attempt 1/1" with no reason given.
    warn "could not read the retry cap from meta_harness.generator (got '$CAP') — failing closed to a single attempt."
    CAP=1
    ;;
esac
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

LANE="fast"
[ "${BORROMEANRINGS_HEAVY:-0}" = "1" ] && LANE="heavy"

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
else
  warn "no coreutils 'timeout' (or 'gtimeout') on PATH — the generator and the gate will run UNBOUNDED."
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
# files are in (SPEC-executor.md §2.2), and `.meta-harness/` is out WHETHER OR NOT the
# project gitignores it. That exclusion is not a nicety. The gate's evidence area is the
# driver's own workspace — it writes the attempt counter, the generator's log and every
# receipt there — so counting it would make "the tree changed" true after any run at all,
# including a run in which the generator wrote nothing, and report that run as green.
dirty_tree_oid() {
  # A private scratch DIRECTORY, so git creates the index file itself: git rejects a
  # pre-created empty one ("index file smaller than expected").
  local scratch index oid=""
  scratch="$(mktemp -d "${TMPDIR:-/tmp}/borromeanrings-index.XXXXXX")" || return 1
  index="$scratch/index"
  if GIT_INDEX_FILE="$index" git -C "$PROJECT_ROOT" add -A >/dev/null 2>&1; then
    GIT_INDEX_FILE="$index" git -C "$PROJECT_ROOT" \
      rm -r --cached -q --ignore-unmatch -- .meta-harness >/dev/null 2>&1
    oid="$(GIT_INDEX_FILE="$index" git -C "$PROJECT_ROOT" write-tree 2>/dev/null)"
  fi
  rm -rf "$scratch"
  [ -n "$oid" ] || return 1
  printf '%s' "$oid"
}

# Everything the gate can see, as one comparable string.
#
# A CORRECTION to SPEC-generator.md N3 — twice over. N3 said the driver compares the
# dirty-tree OID; the tree is not enough, and neither is `(branch, head, tree)`:
#
#   * HEAD is not the only ref a check reads. 06_git_identity, 09_commits, 11_changelog,
#     13_adr and 34_api_diff each resolve a base by trying `origin/dev dev origin/main
#     main`, so `git update-ref refs/heads/main HEAD` — or a fetch — moves what five
#     checks diff against while HEAD, the branch and the tree stay byte-identical.
#   * The index is not the working tree. 01_source_coherence, 12_secrets and 15_a11y
#     enumerate files with `git ls-files`, so `git rm --cached f` changes what three
#     checks look at while the file sits unchanged on disk and `add -A` re-adds it.
#
# Under a narrower comparison a generator that fixes any of those is told it did nothing
# and the run escalates with the fix already in place. See ADR-0078.
snapshot_identity() {
  local tree refs index
  tree="$(dirty_tree_oid)" || return 1
  refs="$(git -C "$PROJECT_ROOT" for-each-ref --format='%(refname) %(objectname)' 2>/dev/null |
    git -C "$PROJECT_ROOT" hash-object --stdin 2>/dev/null)"
  index="$(git -C "$PROJECT_ROOT" ls-files --stage 2>/dev/null |
    git -C "$PROJECT_ROOT" hash-object --stdin 2>/dev/null)"
  printf '%s %s %s %s %s' \
    "$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null)" \
    "$(git -C "$PROJECT_ROOT" rev-parse HEAD 2>/dev/null)" \
    "$tree" "$refs" "$index"
}

# Fingerprint the gate's evidence area into $1. Conformance §5: nothing under
# .meta-harness/ may move while the generator runs — nothing at all, with no exception
# for the driver's own log, which is written outside this directory until the comparison
# is done. An exception the generator can compute is not an exception, it is a door.
snapshot_evidence() {
  PYTHONPATH="$PY" python3 - "$EVIDENCE" "$1" <<'PY'
import json
import sys

from meta_harness.generator import snapshot_evidence

root, out = sys.argv[1], sys.argv[2]
with open(out, "w", encoding="utf-8") as handle:
    json.dump(snapshot_evidence(root), handle)
PY
}

# Every way the evidence area moved since $1 was taken, one reason per line.
evidence_writes() {
  PYTHONPATH="$PY" python3 - "$EVIDENCE" "$1" <<'PY'
import json
import sys

from meta_harness.generator import evidence_writes, snapshot_evidence

root, before_path = sys.argv[1], sys.argv[2]
with open(before_path, encoding="utf-8") as handle:
    before = json.load(handle)
for reason in evidence_writes(before, snapshot_evidence(root)):
    print(reason)
PY
}

# The failing check ids for the run just gated, or a non-zero exit and a reason on stderr
# if the persisted verdict is not that run's. N1/N2 are requirements, not best efforts: a
# retry that cannot name what failed — or that names an older run's failures — is a retry
# the generator would be guessing at (conformance §5.4).
failing_check_ids() {
  PYTHONPATH="$PY" python3 - "$PROJECT_ROOT" "$1" "$2" <<'PY'
import sys

from meta_harness.generator import failing_check_ids, verdict_mismatch
from meta_harness.verdict import read_last_verdict

project, run_id, gate_ok = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
verdict = read_last_verdict(project)
reason = verdict_mismatch(verdict, run_id, gate_ok)
if reason or verdict is None:
    print(reason or "no verdict", file=sys.stderr)
    sys.exit(1)
print(",".join(failing_check_ids(verdict.checks)))
PY
}

# How many attempts this key has already spent, anchored to the gate's append-only
# verdict history as well as to the counter file (see meta_harness.generator).
attempts_spent() {
  PYTHONPATH="$PY" python3 - "$PROJECT_ROOT" "$1" 2>/dev/null <<'PY' || echo 0
import sys

from meta_harness.generator import attempts_from_history
from meta_harness.verdict import read_history

rows = [(v.generator, v.ok) for v in read_history(sys.argv[1])]
print(attempts_from_history(rows, sys.argv[2]))
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
  echo "  generator: $BORROMEANRINGS_GENERATOR   lane: $LANE"
  echo "  attempts: $attempts_run run here, $((attempt - 1)) of $CAP spent on this key"
  echo "  GENERATOR-RESULT: $action"
  echo
  if [ "$code" -ne 0 ]; then
    echo "ESCALATION: borromeanRings headless run ended '$action' — handing control to the human." >&2
  fi
  exit "$code"
}

# `.meta-harness/` is the gate's own workspace; a project that tracks it makes every gate
# run part of its own gated input. The driver no longer depends on the ignore (the tree
# OID excludes the directory outright), but the project still wants to know.
git -C "$PROJECT_ROOT" check-ignore -q .meta-harness 2>/dev/null ||
  warn "$PROJECT_ROOT does not gitignore .meta-harness/ — the gate's own receipts are part of what it gates. Add '.meta-harness/' to .gitignore."

# Resume rather than restart: a counter left behind by a killed run means this key has
# already spent attempts, and N5 bounds the key, not the invocation.
resumed="$(cat "$COUNTER" 2>/dev/null || true)"
case "$resumed" in '' | *[!0-9]*) resumed=0 ;; esac
attempts_run=0
attempt=$((resumed + 1))
last_verdict=""
export BORROMEANRINGS_FAILING_CHECKS=""

if [ "$attempt" -gt "$CAP" ]; then
  echo "borromeanRings headless: run key '$RUN_KEY' has already spent $resumed of $CAP attempts." >&2
  finish 1 "escalated"
fi

while :; do
  # The attempt counter is the GATE's. It is written here and never read back inside a
  # run (the loop's own count is authoritative), so editing it buys a generator nothing;
  # it is read at startup to resume a killed run, and it is one of two anchors for the
  # bound — the other being the append-only verdict history, which is what makes deleting
  # this file useless. Written BEFORE the snapshot, so the driver's own bookkeeping is
  # never mistaken for the generator's, and checked, because every other write here is.
  printf '%s' "$attempt" >"$COUNTER" || abort "cannot write the attempt counter at $COUNTER"

  scratch="$(mktemp -d "${TMPDIR:-/tmp}/borromeanrings-generator.XXXXXX")" ||
    abort "cannot create a scratch directory for this attempt"
  # OUTSIDE .meta-harness/ until the comparison is over: the driver's own capture must not
  # need an exception in the guard, because BORROMEANRINGS_ATTEMPT and the run key are both
  # handed to the generator, which makes any excepted path one the generator can compute.
  capture="$scratch/attempt.log"
  log="$LOG_DIR/$attempt.log"
  before="$scratch/evidence.json"
  snapshot_evidence "$before" || abort "cannot fingerprint the evidence area"
  state_before="$(snapshot_identity)" ||
    abort "cannot read the state of $PROJECT_ROOT — a git repository is required."

  echo "borromeanRings headless: attempt $attempt/$CAP — running the generator" >&2
  BORROMEANRINGS_ATTEMPT="$attempt" bounded "${BORROMEANRINGS_GENERATOR_TIMEOUT:-540}" \
    bash -c "cd \"\$1\" && shift && $GEN_COMMAND \"\$@\"" \
    borromeanrings-generator "$PROJECT_ROOT" "$PROJECT_ROOT" "$last_verdict" \
    >"$capture" 2>&1 </dev/null
  gen_code=$?
  attempts_run=$((attempts_run + 1))

  violations="$(evidence_writes "$before")" ||
    violations="the evidence area could not be re-read (fail-closed)"
  mv -f "$capture" "$log" 2>/dev/null || cp -f "$capture" "$log" 2>/dev/null
  rm -rf "$scratch"
  if [ -n "$violations" ]; then
    {
      echo "GENERATOR WROTE UNDER .meta-harness/ — the gate's evidence is not the generator's:"
      printf '  %s\n' "$violations"
    } | tee -a "$log" >&2
    gen_code=125 # "could not be trusted to have run honestly", not "it exited 125"
  fi

  state_after="$(snapshot_identity)" ||
    abort "cannot read the state of $PROJECT_ROOT after the generator ran."
  # next_action's `tree_changed` means "did anything the gate can see move?" — see
  # snapshot_identity for why that is five things and not one.
  tree_changed=0
  [ "$state_before" != "$state_after" ] && tree_changed=1

  gate_ok=0
  if [ "$gen_code" -eq 0 ] && [ "$tree_changed" -eq 1 ]; then
    bundles_before="$(ls -1 "$EVIDENCE/receipts" 2>/dev/null | sort)"
    BORROMEANRINGS_PROJECT="$PROJECT_ROOT" bounded "${BORROMEANRINGS_GATE_TIMEOUT:-540}" \
      bash "$BORROMEANRINGS_HOME/verify.sh"
    [ $? -eq 0 ] && gate_ok=1
    run_id="$(comm -13 <(printf '%s\n' "$bundles_before" | grep -v '^$') \
      <(ls -1 "$EVIDENCE/receipts" 2>/dev/null | sort))"
    case "$run_id" in
      '' | *"
"*) abort "the gate produced $(printf '%s' "$run_id" | grep -c .) new receipt bundles; expected exactly one" ;;
    esac
    last_verdict="$EVIDENCE/last_verdict.json"
    failing="$(failing_check_ids "$run_id" "$gate_ok")" ||
      abort "the verdict at $last_verdict is not the one run $run_id produced"
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
