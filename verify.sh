#!/usr/bin/env bash
# borromeanRings — THE GATE.
#
# Governs the project at PROJECT_ROOT (the repo/folder you're working in) using
# borromeanRings's own code at BORROMEANRINGS_HOME (where this script lives). They are the same
# when borromeanRings governs itself; they differ when borromeanRings is *referenced* from
# another project — set BORROMEANRINGS_PROJECT (or CLAUDE_PROJECT_DIR), or run from that
# project's directory. Fail-closed: exits 0 only if every required check (declared
# in the project's borromeanrings.toml) produced a pass receipt. Identical verdict for any
# author (human / CI / agent hook).
set -uo pipefail

# Heavy (CI-tier) lane: `--heavy` (or BORROMEANRINGS_HEAVY=1) additionally runs +
# requires the checks/ci/ set — expensive checks (mutation, CVE audit, secret-scan
# tools) that must NOT run on the fast inner Stop gate. Off by default. See ADR-0033.
HEAVY="${BORROMEANRINGS_HEAVY:-0}"
for _arg in "$@"; do
  [ "$_arg" = "--heavy" ] && HEAVY=1
done

BORROMEANRINGS_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${BORROMEANRINGS_PROJECT:-${CLAUDE_PROJECT_DIR:-$PWD}}"
PROJECT_ROOT="$(cd "$PROJECT_ROOT" && pwd)"
export BORROMEANRINGS_HOME PROJECT_ROOT

# borromeanrings_py: the gate's trusted Python must run from a neutral directory,
# never with the governed project on sys.path (a planted json.py / meta_harness/
# would otherwise shadow stdlib and forge the verdict — #222).
source "$BORROMEANRINGS_HOME/checks/_py.sh"
CONFIG="$PROJECT_ROOT/borromeanrings.toml"

# Which borromeanRings version is governing this run. `git describe` on borromeanRings's own
# repo reflects the exact code state (tag when clean, `-N-g<sha>-dirty` when ahead/modified,
# short SHA before the first tag); the VERSION file is the human-declared release fallback.
# Stamped into the gate output and the persisted Verdict so each governed project's evidence
# records what verified it — not just pass/fail. See ADR-0048.
HARNESS_VERSION="$(git -C "$BORROMEANRINGS_HOME" describe --tags --always --dirty 2>/dev/null || true)"
[ -n "$HARNESS_VERSION" ] || HARNESS_VERSION="$(cat "$BORROMEANRINGS_HOME/VERSION" 2>/dev/null || echo unknown)"
export HARNESS_VERSION

if [ ! -f "$CONFIG" ]; then
  if [ -f "$PROJECT_ROOT/borromeo.toml" ]; then
    # Pre-rename config name (issue #62): still honored (meta_harness.spine falls back to
    # it), but deprecated — say so on every run until the project renames the file.
    echo "borromeanRings: DEPRECATED config name borromeo.toml in $PROJECT_ROOT — still honored; rename it: git mv borromeo.toml borromeanrings.toml (see docs/RENAME.md)." >&2
  else
    echo "borromeanRings: no borromeanrings.toml in $PROJECT_ROOT — run borromeanRings's init.sh there first." >&2
    exit 1
  fi
fi

# borromeanRings adjusts to the project: run the language-agnostic 'shared' checks plus the
# per-language set selected by [project].language (default python).
language="$(PYTHONPATH="$BORROMEANRINGS_HOME/src" borromeanrings_py -c \
  "from meta_harness.spine import load_config; print(load_config('$CONFIG').language)" 2>/dev/null || echo python)"
case "$language" in
  "" | *[!a-z0-9_-]*)
    echo "borromeanRings: invalid [project].language: '$language' (use [a-z0-9_-])." >&2
    exit 1
    ;;
esac

# Per-run, append-only evidence — stored with the GOVERNED project, not borromeanRings.
run_id="$(date -u +%Y%m%dT%H%M%SZ)-$$"
RECEIPT_DIR="$PROJECT_ROOT/.meta-harness/receipts/$run_id"
export RECEIPT_DIR
mkdir -p "$RECEIPT_DIR"

# Run shared (language-agnostic) checks + the selected language's checks. Each writes
# its own receipt; the verdict is computed from receipts, never a check's exit alone.
scan_dirs=("$BORROMEANRINGS_HOME/checks/shared" "$BORROMEANRINGS_HOME/checks/$language")
# CI-tier heavy checks run ONLY under --heavy (never on the fast inner Stop gate).
[ "$HEAVY" = "1" ] && scan_dirs+=("$BORROMEANRINGS_HOME/checks/ci")
for dir in "${scan_dirs[@]}"; do
  [ -d "$dir" ] || continue
  for check in "$dir"/[0-9]*.sh; do
    [ -e "$check" ] || continue
    bash "$check" || true
  done
done

# Fail-closed verdict + summary. Single source of the expected check set is the
# project's borromeanrings.toml (the policy spine). meta_harness is borromeanRings's own code.
PYTHONPATH="$BORROMEANRINGS_HOME/src" borromeanrings_py - "$CONFIG" "$RECEIPT_DIR" "$PROJECT_ROOT" "$HEAVY" "$HARNESS_VERSION" <<'PY'
import json
import os
import sys
from pathlib import Path

from meta_harness.change_detect import record_green
from meta_harness.receipts import run_digest, verify_receipt
from meta_harness.spine import load_config
from meta_harness.verdict import Verdict, append_history, is_failing, write_last_verdict

config_path, receipt_dir, project_root, heavy, harness_version = sys.argv[1:6]
config = load_config(config_path)
# Under --heavy the CI-tier heavy checks are also required; otherwise only the
# fast required set gates (the heavy set never blocks the inner Stop gate).
expected = config.required_checks + (config.heavy_checks if heavy == "1" else ())

rows = []
ok = True
intact_hashes = []
for cid in expected:
    rpath = os.path.join(receipt_dir, f"{cid}.json")
    if not os.path.exists(rpath):
        rows.append((cid, "MISSING"))
        ok = False
        continue
    with open(rpath) as fh:
        receipt = json.load(fh)
    status = receipt.get("status", "?")
    # Tamper-evidence: a required receipt must match its own content hash (fields +
    # log). A fresh run always does; a mismatch means the evidence was edited after
    # the fact — fail closed, never trust a forged/corrupt pass. See ADR-0026.
    log_path = receipt.get("log", "")
    log_text = ""
    if log_path and os.path.exists(log_path):
        with open(log_path, encoding="utf-8", errors="replace") as fh:
            log_text = fh.read()
    if not verify_receipt(receipt, log_text):
        ok = False
        rows.append((cid, f"{status.upper()} !TAMPERED"))
        continue
    intact_hashes.append(receipt.get("content_sha256", ""))
    # Fail-closed by ALLOWLIST, never by negation: only statuses meta_harness.verdict
    # declares non-failing (pass, noop) survive, so an unknown/typo'd/forged status
    # still fails. See ADR-0049.
    if is_failing(status):
        ok = False
    rows.append((cid, status.upper()))

width = max(len(c) for c, _ in rows)
print()
print(f"  borromeanRings gate  (project: {project_root})")
print(f"  harness-version: {harness_version}")
print("  " + "-" * (width + 14))
for cid, status in rows:
    print(f"  {cid.ljust(width)}   {status}")
print("  " + "-" * (width + 14))
print(f"  RESULT: {'PASS' if ok else 'FAIL'}")
# A green built partly on checks that inspected NOTHING is not the same green as one
# where every check did real work. Say so here, or the verdict over-claims (ADR-0049).
hollow = [cid for cid, status in rows if status == "NOOP"]
if hollow:
    print(f"  inspected NOTHING: {len(hollow)} of {len(rows)} — {', '.join(hollow)}")
digest = run_digest(intact_hashes) if intact_hashes else ""
if digest:
    print(f"  run-digest: {digest}")
if not ok:
    print("  One or more checks failed or produced no receipt; see logs in the run dir.")
print()

# Persist a compact last-known verdict for the portfolio status view, and append it to
# the effectiveness-ledger history (best-effort: a write failure must never turn a real
# PASS into a FAIL). See ADR-0046 (status) and ADR-0047 (ledger).
try:
    _verdict = Verdict(
        ok=ok,
        checks=tuple((cid, status.lower()) for cid, status in rows),
        run_id=os.path.basename(receipt_dir),
        digest=digest,
        harness_version=harness_version,
    )
    write_last_verdict(Path(project_root), _verdict)
    append_history(Path(project_root), _verdict)
    # Make each receipt bundle self-describing: which borromeanRings produced it.
    Path(receipt_dir, "harness_version.txt").write_text(harness_version + "\n", encoding="utf-8")
except OSError:
    pass

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
