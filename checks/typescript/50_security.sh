#!/usr/bin/env bash
# Security: no high-confidence dangerous sink (eval, new Function, document.write) in the
# source, found structurally by ast-grep with the rules shipped next to this check. Offline,
# static; `npm audit` contacts a registry and is EXCLUDED from the fast lane (SPEC §2.6).
# Lane contract: docs/specs/SPEC-multi-language.md (ADR-0068). Missing tool ⇒ noop naming
# it (never installed, never fails the project); tool ran and failed ⇒ fail (closed).
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="50_security"
src_dir="$(borromeanrings_project_cfg src_dir)"
if [ "$(borromeanrings_source_count "$src_dir" .ts .tsx)" -eq 0 ]; then
  borromeanrings_noop_greenfield "$id" "ast-grep scan --json (shipped rules)" "TypeScript" "$src_dir"
  exit 0
fi

tool="$(borromeanrings_lane_tool ast-grep)" || {
  borromeanrings_noop_missing_tool "$id" "ast-grep scan --json (shipped rules)" "ast-grep"
  exit 0
}
log="$RECEIPT_DIR/$id.log"
rules="$(dirname "${BASH_SOURCE[0]}")/rules/security.yml"
out="$RECEIPT_DIR/$id.ast-grep.json"
err="$RECEIPT_DIR/$id.ast-grep.stderr"
# ast-grep prints its JSON on stdout and a human banner ("Error: N error(s) found") on
# stderr when error-severity rules match; the two must not share a stream or the JSON
# is unparseable exactly when there are findings to show.
borromeanrings_run_bounded "$out" "\"$tool\" scan --rule \"$rules\" --json \"$src_dir\" 2>\"$err\""
tool_code=$?
PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$out" "$err" "$tool_code" >"$log" 2>&1 <<'PY'
import sys

from meta_harness.lang_security import parse_ast_grep_json, render_findings


def read(path: str) -> str:
    try:
        return open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


text = read(sys.argv[1])
try:
    findings = parse_ast_grep_json(text)
except ValueError as exc:
    print(f"ast-grep exited {sys.argv[3]} with unreadable output ({exc}) — failing closed:")
    print(text)
    print(read(sys.argv[2]))
    sys.exit(1)
print(render_findings(findings))
sys.exit(1 if findings else 0)
PY
code=$?
status="fail"
[ "$code" -eq 0 ] && status="pass"
emit_receipt "$id" "ast-grep scan --json (shipped rules)" "$code" "$log" "$status"
exit "$code"
