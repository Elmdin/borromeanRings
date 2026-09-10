#!/usr/bin/env bash
# 60_mutation — HEAVY (CI-tier) mutation-score RATCHET.
#
# NOT run by the fast inner Stop gate: mutation testing runs the whole suite once
# per mutant. It lives in checks/ci/ (which verify.sh scans ONLY under --heavy /
# BORROMEANRINGS_HEAVY=1) and runs in CI. It measures oracle/assertion strength —
# coverage proves a line executed; mutation proves a test would CATCH a change to
# it — closing the coverage-Goodhart gap. Ratchets vs
# .borromeanrings-mutation-baseline (non-regression; no arbitrary target). See
# ADR-0022 and docs/ENFORCEMENT-COVERAGE.md.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="60_mutation"
log="$RECEIPT_DIR/$id.log"
baseline_file="$PROJECT_ROOT/.borromeanrings-mutation-baseline"
cmd="mutmut run (mutation-score ratchet vs baseline)"

if ! command -v mutmut >/dev/null 2>&1; then
  printf "required tool 'mutmut' not found on PATH\n" >"$log"
  emit_receipt "$id" "$cmd" 127 "$log" "error"
  exit 127
fi

# Clear the previous run's sandbox first. mutmut 3.6.0's copy_src_dir skips any
# target that already exists and never deletes, so a test removed from tests/
# (e.g. one that read outside src/ and broke the clean run) lingers in mutants/
# and keeps failing the lane. Bounded to exactly $PROJECT_ROOT/mutants; refuse to
# delete anything that resolves elsewhere (a symlink out of the project).
mutants_dir="$PROJECT_ROOT/mutants"
if [ -e "$mutants_dir" ]; then
  resolved="$(cd "$mutants_dir" 2>/dev/null && pwd -P || true)"
  if [ -n "$resolved" ] && [ "$resolved" = "$(cd "$PROJECT_ROOT" && pwd -P)/mutants" ]; then
    rm -rf "$mutants_dir"
  else
    printf "refusing to clear '%s': it resolves outside the project (%s)\n" "$mutants_dir" "${resolved:-unresolvable}" >"$log"
    emit_receipt "$id" "$cmd" 1 "$log" "fail"
    exit 1
  fi
fi

# mutmut's OWN exit is nonzero when mutants survive — that is NOT a check failure
# here: the ratchet decides pass/fail on the SCORE, not on mutmut's exit. Capture
# output (the emoji summary line) to the log regardless. Mutation over the whole
# package runs many minutes, so give it a generous, configurable wall-clock bound —
# the 300s default would kill it mid-run and (correctly) fail closed on 0 evaluated.
BORROMEANRINGS_CHECK_TIMEOUT="${BORROMEANRINGS_MUTATION_TIMEOUT:-1800}" \
  borromeanrings_run_bounded "$log" "mutmut run" || true

baseline="$(cat "$baseline_file" 2>/dev/null || echo 0)"

# Parse the score from the captured output and ratchet it — both in borromeanRings's
# own tested code (meta_harness.mutation + meta_harness.ratchet), so the shell
# only orchestrates. The 4th field is the receipt `summary` ("evaluated N, score S"),
# which the gate prints on this check's verdict row (issue #187); `read` gives the
# LAST variable the rest of the line, so its spaces are safe.
read -r score regressed evaluated summary <<EOF
$(PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$log" "$baseline" <<'PY'
import sys

from meta_harness.mutation import mutation_score, parse_mutmut_summary, summary_line, total_evaluated
from meta_harness.ratchet import decide_ratchet

text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
counts = parse_mutmut_summary(text)
score = mutation_score(counts)
decision = decide_ratchet(score, float(sys.argv[2]), higher_is_better=True)
print(f"{score:.4f} {1 if decision.regressed else 0} {total_evaluated(counts)} {summary_line(counts, decision)}")
PY
)
EOF

status="pass"
code=0
# Fail CLOSED if mutmut evaluated no mutants: that is a setup/clean-tests failure
# (the vacuous 1.0 score), NOT a perfect suite. Never let it pass silently.
if [ -z "${score:-}" ] || [ "${evaluated:-0}" = "0" ]; then
  printf "\nMUTATION CHECK DID NOT RUN: mutmut evaluated 0 mutants (setup/clean-test failure — see above). Failing closed.\n" >>"$log"
  status="fail"
  code=1
elif [ "${regressed:-1}" = "1" ]; then
  printf "\nMUTATION-SCORE REGRESSION: %s is below baseline %s\n" "$score" "$baseline" >>"$log"
  status="fail"
  code=1
fi

# `summary` rides in the receipt (hash-covered like every field) so the gate row reads
# "PASS (evaluated N, score S)" / "FAIL (evaluated 0)" — the count is what makes the
# score readable (a vacuous run scores 1.0). Empty if the parse step itself died.
extra="$(python3 -c "import json,sys; print(json.dumps({'mutation_score': float(sys.argv[1]), 'mutation_baseline': float(sys.argv[2]), 'summary': sys.argv[3]}))" "${score:-0}" "$baseline" "${summary:-}" 2>/dev/null || echo '')"
emit_receipt "$id" "$cmd" "$code" "$log" "$status" "$extra"
exit "$code"
