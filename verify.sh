#!/usr/bin/env bash
# borromeo — THE GATE.
#
# Governs the project at PROJECT_ROOT (the repo/folder you're working in) using
# borromeo's own code at BORROMEO_HOME (where this script lives). They are the same
# when borromeo governs itself; they differ when borromeo is *referenced* from
# another project — set BORROMEO_PROJECT (or CLAUDE_PROJECT_DIR), or run from that
# project's directory. Fail-closed: exits 0 only if every required check (declared
# in the project's borromeo.toml) produced a pass receipt. Identical verdict for any
# author (human / CI / agent hook).
set -uo pipefail

BORROMEO_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${BORROMEO_PROJECT:-${CLAUDE_PROJECT_DIR:-$PWD}}"
PROJECT_ROOT="$(cd "$PROJECT_ROOT" && pwd)"
export BORROMEO_HOME PROJECT_ROOT
CONFIG="$PROJECT_ROOT/borromeo.toml"

if [ ! -f "$CONFIG" ]; then
  echo "borromeo: no borromeo.toml in $PROJECT_ROOT — run borromeo's init.sh there first." >&2
  exit 1
fi

# borromeo adjusts to the project: run the language-agnostic 'shared' checks plus the
# per-language set selected by [project].language (default python).
language="$(PYTHONPATH="$BORROMEO_HOME/src" python3 -c \
  "from meta_harness.spine import load_config; print(load_config('$CONFIG').language)" 2>/dev/null || echo python)"
case "$language" in
  "" | *[!a-z0-9_-]*)
    echo "borromeo: invalid [project].language: '$language' (use [a-z0-9_-])." >&2
    exit 1
    ;;
esac

# Per-run, append-only evidence — stored with the GOVERNED project, not borromeo.
run_id="$(date -u +%Y%m%dT%H%M%SZ)-$$"
RECEIPT_DIR="$PROJECT_ROOT/.meta-harness/receipts/$run_id"
export RECEIPT_DIR
mkdir -p "$RECEIPT_DIR"

# Run shared (language-agnostic) checks + the selected language's checks. Each writes
# its own receipt; the verdict is computed from receipts, never a check's exit alone.
for dir in "$BORROMEO_HOME/checks/shared" "$BORROMEO_HOME/checks/$language"; do
  [ -d "$dir" ] || continue
  for check in "$dir"/[0-9]*.sh; do
    [ -e "$check" ] || continue
    bash "$check" || true
  done
done

# Fail-closed verdict + summary. Single source of the expected check set is the
# project's borromeo.toml (the policy spine). meta_harness is borromeo's own code.
PYTHONPATH="$BORROMEO_HOME/src" python3 - "$CONFIG" "$RECEIPT_DIR" "$PROJECT_ROOT" <<'PY'
import json
import os
import sys
from pathlib import Path

from meta_harness.change_detect import record_green
from meta_harness.spine import load_config

config_path, receipt_dir, project_root = sys.argv[1], sys.argv[2], sys.argv[3]
config = load_config(config_path)
expected = config.required_checks

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
print(f"  borromeo gate  (project: {project_root})")
print("  " + "-" * (width + 14))
for cid, status in rows:
    print(f"  {cid.ljust(width)}   {status}")
print("  " + "-" * (width + 14))
print(f"  RESULT: {'PASS' if ok else 'FAIL'}")
if not ok:
    print("  One or more checks failed or produced no receipt; see logs in the run dir.")
print()
if ok:
    # Record this exact gated-input state as proven-green so a no-op Stop (a
    # question, a doc edit) can skip a redundant full gate. Best-effort: a
    # recording failure must never turn a real PASS into a FAIL.
    try:
        record_green(Path(project_root), config)
    except OSError:
        pass
sys.exit(0 if ok else 1)
PY
