#!/usr/bin/env bash
# Wave-2 critic rubrics (T2, ADVISORY): a model judge external to the generator
# judges functions/tests against declared rubrics (error-handling, naming,
# security, boundary-value, test-smell). Opt-in via [critic].judge_command +
# [critic].rubrics; a no-op when either is unset. ADVISORY — reports, never gates
# (not in [checks].required) until the judge is trusted. Same posture + machinery
# as 55_doc_drift. See docs/specs/SPEC-critic-rubrics.md and ADR-0036.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="56_critics"
log="$RECEIPT_DIR/$id.log"
cmd="Wave-2 critic rubrics (advisory; model judge external to the generator)"

judge_command="$(borromeanrings_project_cfg critic_judge_command)"
rubrics="$(borromeanrings_project_cfg critic_rubrics)"
if [ -z "$judge_command" ] || [ "$rubrics" = "()" ]; then
  echo "critic rubrics off (need [critic].judge_command and [critic].rubrics) — advisory" >"$log"
  emit_noop "$id" "$cmd" "$log"
  exit 0
fi

PYTHONPATH="$BORROMEANRINGS_HOME/src" BORROMEANRINGS_JUDGE_CMD="$judge_command" \
  borromeanrings_py - "$PROJECT_ROOT" "$PROJECT_ROOT/borromeanrings.toml" >"$log" 2>&1 <<'PY'
import os
import sys
from pathlib import Path

from meta_harness.critic import make_rubric_judge
from meta_harness.critic_rubrics import RUBRICS, run_rubric
from meta_harness.doc_drift import command_ask
from meta_harness.spine import load_config

root = Path(sys.argv[1])
cfg = load_config(sys.argv[2])
judge = make_rubric_judge(command_ask(os.environ["BORROMEANRINGS_JUDGE_CMD"]))

findings = []
for rubric_id in cfg.critic_rubrics:
    rubric = RUBRICS.get(rubric_id)
    if rubric is None:
        print(f"unknown rubric '{rubric_id}' — skipped")
        continue
    scope_dir = root / (cfg.tests_dir if rubric.scope == "tests" else cfg.src_dir)
    for path in sorted(scope_dir.rglob("*.py")):
        report = run_rubric(path.read_text(encoding="utf-8"), rubric, judge)  # advisory
        findings += [f"{path}::{v.criterion_id}: {v.rationale}" for v in report.verdicts if not v.passed]

if findings:
    print(f"CRITIC (advisory) — {len(findings)} flagged:")
    for line in findings:
        print(f"  - {line}")
else:
    print("critic rubrics: nothing flagged")
PY
# Advisory: always pass (does not gate); findings live in the log for a human.
emit_receipt "$id" "$cmd" 0 "$log" "pass"
exit 0
