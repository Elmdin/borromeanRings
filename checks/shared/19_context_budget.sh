#!/usr/bin/env bash
# Context-budget RATCHET (not an absolute cap): the bytes borromeanRings itself puts
# into the agent's context — the prompt-rewrite directive, root instruction files,
# installed SKILL.md files, hook message templates — may not regress above the
# recorded baseline (.borromeanrings-context-baseline; absent ⇒ vacuous until seeded
# by adopt.sh or by hand). Governance must not become the biggest line in the token
# bill (issue #135). Language-agnostic, native, no tokenizer (tokens ≈ bytes/4).
# Nothing measurable ⇒ noop; an unreadable baseline fails CLOSED.
# See docs/specs/SPEC-context-budget.md and ADR-0055.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="19_context_budget"
log="$RECEIPT_DIR/$id.log"
baseline_file="$PROJECT_ROOT/.borromeanrings-context-baseline"
cmd="context budget (ratchet vs baseline)"

# The python step prints the report, then the total on the LAST line. Exit 3 ⇒ nothing
# measurable (BORROMEANRINGS_NOOP_EXIT); the directive is built from the project's
# [context] only when [prompt_rewriting].enabled, exactly as the hook would inject it.
report="$(PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_ROOT" "$BORROMEANRINGS_NOOP_EXIT" <<'PY'
import sys
from pathlib import Path

from meta_harness.context_budget import format_report, measure_context_budget
from meta_harness.prompt_rewrite import build_directive
from meta_harness.spine import load_config

root = Path(sys.argv[1])
config = load_config(root / "borromeanrings.toml")
directive = build_directive(config.context) if config.prompt_rewriting_enabled else ""
budget = measure_context_budget(root, directive)
if budget.is_empty:
    print("no skills, hooks, instruction files or directive here — nothing borromeanRings puts in context")
    sys.exit(int(sys.argv[2]))
print(format_report(budget))
print(budget.total_bytes)
PY
)"
code=$?
if [ "$code" -eq "$BORROMEANRINGS_NOOP_EXIT" ]; then
  printf '%s\n' "$report" >"$log"
  emit_noop "$id" "$cmd" "$log"
  exit 0
fi
if [ "$code" -ne 0 ]; then
  printf '%s\n' "$report" >"$log"
  emit_receipt "$id" "$cmd" "$code" "$log" "fail"
  exit "$code"
fi

current="${report##*$'\n'}"
printf '%s\n' "${report%$'\n'*}" >"$log"

status="pass"
code=0
if [ ! -e "$baseline_file" ]; then
  echo "context total: $current bytes (no baseline recorded — seed .borromeanrings-context-baseline to ratchet it)" >>"$log"
else
  baseline="$(cat "$baseline_file" 2>/dev/null | tr -d '[:space:]')"
  if ! printf '%s' "$baseline" | grep -Eq '^[0-9]+$'; then
    echo "unreadable baseline: $baseline_file must hold one non-negative integer (failing closed)" >>"$log"
    status="fail"
    code=1
  else
    echo "context total: $current bytes (baseline $baseline)" >>"$log"
    if [ "$current" -gt "$baseline" ]; then
      echo "CONTEXT-BUDGET REGRESSION: $current is above baseline $baseline — trim what borromeanRings injects, or accept the new baseline deliberately" >>"$log"
      status="fail"
      code=1
    fi
  fi
fi

extra="$(python3 -c "import json,sys; print(json.dumps({'context_bytes': int(sys.argv[1]), 'context_baseline': (int(sys.argv[2]) if sys.argv[2].isdigit() else None)}))" "$current" "${baseline:-}" 2>/dev/null || echo '')"
emit_receipt "$id" "$cmd" "$code" "$log" "$status" "$extra"
exit "$code"
