#!/usr/bin/env bash
# borromeo — THE GATE.
#
# Runs every declared check in checks/, captures one receipt per check, and
# exits 0 only if EVERY expected check produced a receipt with status "pass".
# Fail-closed: a missing receipt (crashed/skipped check) is a failure, never a
# pass-on-trust. Identical behavior whether invoked by a human, CI, or the
# Claude Code Stop hook (the verifier is external to the generator).
set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_ROOT
CHECKS_DIR="$PROJECT_ROOT/checks"
CONFIG="$PROJECT_ROOT/borromeo.toml"

# Per-run, append-only evidence directory (monotonic run id; no shared state).
run_id="$(date -u +%Y%m%dT%H%M%SZ)-$$"
RECEIPT_DIR="$PROJECT_ROOT/.meta-harness/receipts/$run_id"
export RECEIPT_DIR
mkdir -p "$RECEIPT_DIR"

# Run every check in filename order. Each writes its own receipt; a check's
# exit code is NOT trusted on its own — the verdict is computed from receipts.
for check in "$CHECKS_DIR"/[0-9]*.sh; do
  [ -e "$check" ] || continue
  bash "$check" || true
done

# Fail-closed verdict + human-readable summary. Single source of the expected
# check set is the policy spine, borromeo.toml (Single Choice Principle).
PYTHONPATH="$PROJECT_ROOT/src" python3 - "$CONFIG" "$RECEIPT_DIR" <<'PY'
import json
import os
import sys

from meta_harness.spine import load_config

config_path, receipt_dir = sys.argv[1], sys.argv[2]
expected = load_config(config_path).required_checks

rows = []
ok = True
for cid in expected:
    rpath = os.path.join(receipt_dir, f"{cid}.json")
    if not os.path.exists(rpath):
        rows.append((cid, "MISSING"))
        ok = False
        continue
    with open(rpath) as fh:
        receipt = json.load(fh)
    status = receipt.get("status", "?")
    if status != "pass":
        ok = False
    rows.append((cid, status.upper()))

width = max(len(c) for c, _ in rows)
print()
print(f"  borromeo gate  ({receipt_dir})")
print("  " + "-" * (width + 14))
for cid, status in rows:
    print(f"  {cid.ljust(width)}   {status}")
print("  " + "-" * (width + 14))
print(f"  RESULT: {'PASS' if ok else 'FAIL'}")
if not ok:
    print("  One or more checks failed or produced no receipt; see logs in the run dir.")
print()
sys.exit(0 if ok else 1)
PY
