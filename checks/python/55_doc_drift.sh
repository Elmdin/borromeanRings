#!/usr/bin/env bash
# Doc-drift (T2 critic, ADVISORY): a model judge EXTERNAL to the generator checks
# whether each public function's docstring still matches its code — a semantic
# question no mechanical check can answer. Opt-in via [critic].judge_command; a no-op
# when unset. ADVISORY: it reports drift but never gates (deliberately NOT in
# [checks].required) until the model judge is trusted, and belongs on the CI heavy
# lane once available. See docs/specs/SPEC-doc-drift.md and ADR-0030.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="55_doc_drift"
log="$RECEIPT_DIR/$id.log"
cmd="doc-drift critic (advisory; model judge external to the generator)"

judge_command="$(borromeanrings_project_cfg critic_judge_command)"
if [ -z "$judge_command" ]; then
  echo "no [critic].judge_command configured — doc-drift critic off (advisory)" >"$log"
  emit_receipt "$id" "$cmd" 0 "$log" "pass"
  exit 0
fi

src_dir="$(borromeanrings_project_cfg src_dir)"
PYTHONPATH="$BORROMEANRINGS_HOME/src" BORROMEANRINGS_JUDGE_CMD="$judge_command" \
  borromeanrings_py - "$PROJECT_ROOT/$src_dir" >"$log" 2>&1 <<'PY'
import os
import sys
from pathlib import Path

from meta_harness.critic import make_rubric_judge
from meta_harness.doc_drift import command_ask, evaluate_doc_drift

judge = make_rubric_judge(command_ask(os.environ["BORROMEANRINGS_JUDGE_CMD"]))
drift = []
for path in sorted(Path(sys.argv[1]).rglob("*.py")):
    report = evaluate_doc_drift(path.read_text(encoding="utf-8"), judge)  # advisory
    drift += [f"{path}::{v.criterion_id}: {v.rationale}" for v in report.verdicts if not v.passed]

if drift:
    print(f"DOC-DRIFT (advisory) — {len(drift)} possible docstring mismatch(es):")
    for line in drift:
        print(f"  - {line}")
else:
    print("doc-drift critic: no drift reported")
PY
# Advisory: always pass (does not gate); findings live in the log for a human.
emit_receipt "$id" "$cmd" 0 "$log" "pass"
exit 0
