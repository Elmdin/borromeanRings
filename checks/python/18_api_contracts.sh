#!/usr/bin/env bash
# 18_api_contracts — the project's own API-usage rules, enforced on every call site.
#
# [api_contracts] declares rules (banned / forbidden_in / must_check / required_arg /
# paired / requires_before) or references rule packs under contracts/. Native stdlib-ast
# analysis, binary per rule, no LLM, no thresholds. Off when nothing is declared; noop
# (exit 3) when the declared rules matched no call site at all — a green that inspected
# nothing must say so (ADR-0049). Fail closed on unreadable config or source.
# See docs/specs/SPEC-api-contracts.md, ADR-0054 (#130).
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="18_api_contracts"
log="$RECEIPT_DIR/$id.log"
cmd="API-usage contracts (declared [api_contracts] rules over every call site)"

PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - \
  "$PROJECT_ROOT" "$PROJECT_ROOT/borromeanrings.toml" "$BORROMEANRINGS_HOME/contracts" >"$log" 2>&1 <<'PY'
import sys
from pathlib import Path

from meta_harness.api_contracts import check_tree, load_pack, parse_rules
from meta_harness.source_coherence import walk_sources
from meta_harness.spine import load_config

root, config_path, packs_dir = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
cfg = load_config(config_path)

if not cfg.api_contracts_rules and not cfg.api_contracts_packs:
    print("no [api_contracts] rules or packs declared — rule off")
    sys.exit(0)

rules = list(parse_rules(cfg.api_contracts_rules))
for pack in cfg.api_contracts_packs:
    rules.extend(load_pack(pack, packs_dir))

src_root = root / cfg.src_dir
files = sorted(src_root / rel for rel in walk_sources(src_root))
report = check_tree(files, rules)
if report.violations:
    print(f"API-CONTRACT VIOLATIONS ({len(report.violations)}):")
    for v in report.violations:
        where = f"{Path(v.path).relative_to(root) if v.path else '?'}:{v.line}"
        cite = f"  ({v.rule.source})" if v.rule.source else ""
        print(f"  - {where} {v.rule.describe()} — {v.message}{cite}")
    sys.exit(1)
if report.references == 0:
    print(
        f"{len(rules)} rule(s) declared but no call site in {len(files)} file(s) matched any "
        "rule symbol — the contracts inspected nothing"
    )
    sys.exit(3)
print(f"API contracts OK — {report.references} matching call site(s) in {len(files)} file(s) obey {len(rules)} rule(s)")
PY
code=$?
status="$(borromeanrings_status_for_code "$code")"
[ "$status" = "noop" ] && code=0
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
