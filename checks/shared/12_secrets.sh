#!/usr/bin/env bash
# Secret scanning (high-confidence): no provider tokens or private-key blocks in
# tracked files. Native stdlib re; no external tool. Deliberately low-false-positive
# (provider shapes + private keys only) — noisy entropy heuristics belong to a tool
# (gitleaks) on the CI heavy lane. A line may carry `borromeanrings: allow-secret`
# to whitelist a documented example. See docs/specs/SPEC-secrets.md and ADR-0032.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="12_secrets"
log="$RECEIPT_DIR/$id.log"
cmd="secret scan (high-confidence provider tokens + private keys, tracked files)"

# Fail-closed on a non-git project: without git there is no tracked-file set to scan,
# so an empty list would PASS VACUOUSLY ("can't scan" silently reading as "nothing to
# find"). Refuse instead — that vacuity is exactly what a secret gate must not do.
if ! git -C "$PROJECT_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "NOT A GIT REPOSITORY — cannot enumerate tracked files, so secrets cannot be scanned." >"$log"
  echo "Fail-closed: run 'git init' (and commit) so tracked files exist, or drop 12_secrets from [checks].required for this project." >>"$log"
  emit_receipt "$id" "$cmd" 1 "$log" "fail"
  exit 1
fi

# Write the NUL-delimited tracked-file list to a file (a bash variable would strip
# the NULs, and stdin is taken by the heredoc). Paths with spaces/newlines stay safe.
list_file="$RECEIPT_DIR/$id.files"
# A FAILED enumeration is not an empty one. Swallowing the error scanned an empty list
# and reported `pass`: a secret gate green over a tree it never read (#186). Fail closed.
if ! (cd "$PROJECT_ROOT" && git ls-files -z) >"$list_file" 2>"$list_file.err"; then
  {
    echo "could not list tracked files (git ls-files failed), so secrets cannot be scanned:"
    cat "$list_file.err"
  } >"$log"
  emit_receipt "$id" "$cmd" 1 "$log" "fail"
  exit 1
fi
# Nothing tracked yet (a freshly initialised project) is legitimate, and it is `noop`:
# nothing was inspected, so the verdict must not say `pass` (ADR-0049, ADR-0084).
if [ ! -s "$list_file" ]; then
  echo "no tracked files: nothing to scan yet (12_secrets scans what git tracks)" >"$log"
  emit_noop "$id" "$cmd" "$log"
  exit 0
fi

PYTHONPATH="$BORROMEANRINGS_HOME/src" borromeanrings_py - "$PROJECT_ROOT" "$list_file" "$BORROMEANRINGS_NOOP_EXIT" >"$log" 2>&1 <<'PY'
import sys
from pathlib import Path

from meta_harness.secrets import scan_paths

root = Path(sys.argv[1])
names = [n for n in Path(sys.argv[2]).read_bytes().decode("utf-8", "replace").split("\0") if n]
report = scan_paths([root / n for n in names])
if report.unreadable:
    # A tracked file that exists and cannot be read cannot be declared clean (#250 review).
    print(f"could not read {len(report.unreadable)} tracked file(s), so they cannot be scanned:")
    for path in report.unreadable:
        print(f"  - {path}")
    sys.exit(1)
if names and len(report.absent) == len(names):
    # Some tracked files missing is a deletion in progress. ALL of them missing means git's
    # index does not describe this directory: a broken checkout, or a .git pointing at
    # another repository. Neither can be declared clean (second review of #250).
    print(f"none of the {len(names)} tracked file(s) exist in {root}: git's index does not")
    print("describe this directory (a broken checkout, or a .git that points elsewhere).")
    sys.exit(1)
if report.findings:
    print(f"SECRETS DETECTED — {len(report.findings)} high-confidence match(es):")
    for f in report.findings:
        print(f"  - [{f.kind}] {f.path}:{f.line} ({f.snippet})")
    print("Remove the secret and rotate it. False positive? add "
          "'borromeanrings: allow-secret' on the line.")
    sys.exit(1)
for label, paths in (("not in the working tree", report.absent),
                     ("binary or a directory (submodule), not scanned as text", report.skipped)):
    if paths:
        print(f"{len(paths)} tracked path(s) {label}:")
        for path in paths:
            print(f"  - {path}")
if report.scanned == 0:
    print("no tracked text file was readable to scan: nothing was inspected")
    sys.exit(int(sys.argv[3]))
print(f"no high-confidence secrets in {report.scanned} tracked file(s)")
PY
code=$?
if [ "$code" -eq "$BORROMEANRINGS_NOOP_EXIT" ]; then
  emit_noop "$id" "$cmd" "$log"
  exit 0
fi
status="fail"
[ "$code" -eq 0 ] && status="pass"
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
