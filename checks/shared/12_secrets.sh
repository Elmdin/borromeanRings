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

PYTHONPATH="$BORROMEANRINGS_HOME/src" borromeanrings_py - "$PROJECT_ROOT" "$list_file" >"$log" 2>&1 <<'PY'
import sys
from pathlib import Path

from meta_harness.secrets import scan_files

root = Path(sys.argv[1])
names = [n for n in Path(sys.argv[2]).read_bytes().decode("utf-8", "replace").split("\0") if n]
findings = scan_files([root / n for n in names])
if findings:
    print(f"SECRETS DETECTED — {len(findings)} high-confidence match(es):")
    for f in findings:
        print(f"  - [{f.kind}] {f.path}:{f.line} ({f.snippet})")
    print("Remove the secret and rotate it. False positive? add "
          "'borromeanrings: allow-secret' on the line.")
    sys.exit(1)
print("no high-confidence secrets in tracked files")
PY
code=$?
status="fail"
[ "$code" -eq 0 ] && status="pass"
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
