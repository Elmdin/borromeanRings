#!/usr/bin/env bash
# 23_predicates — predicate lint: hedge words + graph integrity in acceptance predicates.
#
# "The HEALTHCHECK command is meaningful" has no yes/no answer; "the HEALTHCHECK command
# probes the service" does. This check extracts the predicates this project's documents make (SPEC
# Contract/Guarantees/Acceptance bullets, ADR Consequences bullets phrased must/never/shall,
# issue-form task-list items), fails on any hedge word (`file:line — predicate — hedge`),
# and — with [predicates].require_reference — fails on any SPEC that names no shipped
# check id, no existing test file and no issue (an orphan: a contract no gate, test run
# or ticket can reach). Deterministic, native (stdlib regex), threshold-free. Off unless
# [predicates].enabled; noop when no predicate was found; fail on an unreadable file.
# See docs/specs/SPEC-predicates.md, ADR-0064.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="23_predicates"
log="$RECEIPT_DIR/$id.log"
cmd="predicate lint (hedge words + SPEC graph integrity per [predicates])"

enabled="$(borromeanrings_project_cfg predicates_enabled 2>/dev/null || echo False)"
if [ "$enabled" != "True" ]; then
  echo "predicate lint not enabled ([predicates].enabled=false) — rule off" >"$log"
  emit_noop "$id" "$cmd" "$log"
  exit 0
fi

# The shipped check ids come from the governing borromeanRings, not the project.
known_checks="$(
  for f in "$BORROMEANRINGS_HOME"/checks/*/[0-9]*.sh; do
    [ -e "$f" ] && basename "$f" .sh
  done
)"

PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_ROOT" "$known_checks" >"$log" 2>&1 <<'PY'
import sys
from pathlib import Path

from meta_harness.predicates import Document, lint, render
from meta_harness.spine import load_config

root = Path(sys.argv[1])
known_checks = frozenset(line.strip() for line in sys.argv[2].splitlines() if line.strip())
cfg = load_config(root / "borromeanrings.toml")
known_tests = frozenset(p.name for p in (root / cfg.tests_dir).rglob("test_*.py"))

documents = []
unreadable = []
for rel in cfg.predicates_paths:
    base = root / rel
    if not base.is_dir():
        continue
    for path in sorted(p for p in base.rglob("*") if p.is_file()):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            unreadable.append(f"{path.relative_to(root)}: {exc}")
            continue
        documents.append(Document(str(path.relative_to(root)), text))

if unreadable:
    print(f"PREDICATE LINT — {len(unreadable)} file(s) could not be read (failing closed):")
    for line in unreadable:
        print(f"  {line}")
    sys.exit(1)

report = lint(
    documents,
    known_checks=known_checks,
    known_tests=known_tests,
    extra_hedges=cfg.predicates_hedges,
    require_reference=cfg.predicates_require_reference,
)
if not report.predicates and not report.orphans:
    print(
        f"no predicates found under {', '.join(cfg.predicates_paths)} "
        f"({len(documents)} document(s) read) — nothing to lint"
    )
    sys.exit(3)
print(render(report))
sys.exit(0 if report.ok else 1)
PY
code=$?
status="$(borromeanrings_status_for_code "$code")"
[ "$status" = "noop" ] && code=0
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
