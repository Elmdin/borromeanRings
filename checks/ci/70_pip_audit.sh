#!/usr/bin/env bash
# 70_pip_audit — HEAVY (CI-tier) dependency CVE audit.
#
# pip-audit hits the network and audits the installed environment; the parser
# exactly the project's declared deps (a clean env). It must NOT run on the fast
# Stop gate. Base packaging tooling and accepted advisories are dropped via
# [audit].ignore_packages / ignore_vulns. See docs/specs/SPEC-audit.md, ADR-0034.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="70_pip_audit"
log="$RECEIPT_DIR/$id.log"
cmd="dependency CVE audit (pip-audit; heavy/CI)"

if ! python3 -m pip_audit --version >/dev/null 2>&1; then
  printf "required tool 'pip-audit' (python3 -m pip_audit) not found\n" >"$log"
  emit_receipt "$id" "$cmd" 127 "$log" "error"
  exit 127
fi

raw="$RECEIPT_DIR/$id.report.json"
# pip-audit exits nonzero when it finds vulns; the parser (with ignores) decides,
# so don't let its exit fail the check here. Bounded so a network hang fails closed.
borromeanrings_run_bounded "$RECEIPT_DIR/$id.tool.log" \
  "python3 -m pip_audit --format json --progress-spinner off > '$raw'" || true

PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_ROOT/borromeanrings.toml" "$raw" "$PROJECT_ROOT/pyproject.toml" >"$log" 2>&1 <<'PY'
import sys
from pathlib import Path

from meta_harness.audit import parse_pip_audit
from meta_harness.closure import ClosureUnavailable, project_closure
from meta_harness.spine import load_config

cfg = load_config(sys.argv[1])
report = Path(sys.argv[2])
if not report.exists() or not report.read_text().strip():
    print("pip-audit produced no report (tool/network failure) — fail closed")
    sys.exit(1)

# pip-audit reads the INSTALLED environment, which is the project's dependencies
# only by luck (a clean CI runner). Narrow it to what the project declares plus
# everything that pulls in, so the verdict is about the commit and not about the
# machine (#228). Fail closed rather than widening back to everything: silently
# auditing the whole machine is how this went unnoticed.
try:
    scope = frozenset(project_closure(Path(sys.argv[3])))
except ClosureUnavailable as exc:
    print(f"cannot determine the project's dependency closure ({exc}) — fail closed")
    sys.exit(1)
print(f"scope: {len(scope)} distribution(s) — declared in {sys.argv[3]}, plus their closure")

findings = parse_pip_audit(
    report.read_text(encoding="utf-8"),
    ignore_packages=cfg.audit_ignore_packages,
    ignore_vulns=cfg.audit_ignore_vulns,
    scope=scope,
)
if findings:
    print(f"KNOWN CVEs in {len(findings)} dependency(ies):")
    for f in findings:
        print(f"  - {f.name} {f.version}: {', '.join(f.vuln_ids)}")
    print("Upgrade the dependency, or add an accepted CVE to [audit].ignore_vulns.")
    sys.exit(1)
print("no known CVEs in declared dependencies")
PY
code=$?
status="fail"
[ "$code" -eq 0 ] && status="pass"
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
