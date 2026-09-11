#!/usr/bin/env bash
# 74_secret_history — git-history secret scan (heavy lane, CI-tier).
#
# 12_secrets scans the CURRENT tracked files; this scans every blob reachable from
# any ref (git rev-list --all) — a committed-then-deleted secret still lives in the
# shared history and is compromised. Reachable objects ONLY: dangling/unreferenced
# blobs never get pushed and would only surface local test artifacts (false
# positives). Fail-closed. History is immutable, so a finding requires ROTATION;
# acknowledge rotated/benign ones by fingerprint in [secrets].history_allow. Native
# (reuses meta_harness.secrets); no external tool. Not a git repo ⇒ no history ⇒ pass.
# See docs/specs/SPEC-secret-history.md and ADR-0042.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="74_secret_history"
log="$RECEIPT_DIR/$id.log"
cmd="git-history secret scan (reachable blobs; high-confidence)"

if ! git -C "$PROJECT_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "not a git repository — no history to scan" >"$log"
  emit_receipt "$id" "$cmd" 0 "$log" "pass"
  exit 0
fi

PYTHONPATH="$BORROMEANRINGS_HOME/src" borromeanrings_py - "$PROJECT_ROOT" "$PROJECT_ROOT/borromeanrings.toml" >"$log" 2>&1 <<'PY'
import subprocess
import sys

from meta_harness.secret_history import scan_blobs
from meta_harness.spine import load_config

root = sys.argv[1]
allow = load_config(sys.argv[2]).secrets_history_allow
MAX = 524288  # skip blobs > 512KB — secrets are small; big blobs only waste time


def git(*args: str) -> bytes:
    return subprocess.run(["git", "-C", root, *args], capture_output=True).stdout


revlist = git("rev-list", "--all", "--objects").decode("utf-8", "replace")
shas = [line.split()[0] for line in revlist.splitlines() if line.strip()]
if not shas:
    print("empty history — nothing to scan")
    sys.exit(0)

batch_check = subprocess.run(
    ["git", "-C", root, "cat-file", "--batch-check"],
    input="\n".join(shas),
    capture_output=True,
    text=True,
).stdout
blob_shas = sorted({ln.split()[0] for ln in batch_check.splitlines() if " blob " in ln})


def blobs():
    for sha in blob_shas:
        content = git("cat-file", "blob", sha)
        if len(content) > MAX:
            continue
        yield sha, content.decode("utf-8", "replace")


findings = scan_blobs(blobs(), allow=allow)
if findings:
    print(f"SECRETS IN HISTORY — {len(findings)} unique high-confidence match(es):")
    for f in findings:
        print(f"  - [{f.kind}] first seen in blob {f.blob[:12]} — fingerprint {f.fingerprint}")
    print("History is immutable: ROTATE each secret (it is compromised). Once rotated,")
    print('acknowledge it in borromeanrings.toml:  [secrets]  history_allow = ["<fingerprint>", ...]')
    sys.exit(1)
print(f"scanned {len(blob_shas)} reachable blobs — no high-confidence secrets in history")
PY
code=$?
status="fail"
[ "$code" -eq 0 ] && status="pass"
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
