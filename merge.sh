#!/usr/bin/env bash
# borromeo merge — gate-gated, explicitly-invoked merge of the current branch
# into a base branch (default: main).
#
# It executes a human's merge decision; it never originates one. A merge happens
# only if (a) you ran this command AND (b) ./verify.sh exits 0 (fail-closed).
# There is no standing auto-merge mode — that would be self-rewriting, which
# borromeo forbids. Policy is in meta_harness.merge_policy; this is the plumbing.
# See docs/SPEC-merge.md and docs/adr/0007-gated-explicit-merge.md.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
BASE="${1:-main}"
branch="$(git rev-parse --abbrev-ref HEAD)"

# --- Preconditions ----------------------------------------------------------
if [ "$branch" = "$BASE" ]; then
  echo "borromeo merge: already on '$BASE'; nothing to merge." >&2
  exit 1
fi
if [ -n "$(git status --porcelain)" ]; then
  echo "borromeo merge: working tree is dirty; commit or stash before merging." >&2
  exit 1
fi

# --- Gate is the precondition (fail-closed) ---------------------------------
echo "borromeo merge: running the gate on '$branch'…"
if ! ./verify.sh; then
  echo "borromeo merge: REFUSED — gate did not pass. Nothing merged." >&2
  exit 1
fi

# --- Policy: explicit request (we are one) + gate passed --------------------
decision="$(PYTHONPATH=src python3 -c "from meta_harness.merge_policy import decide_merge; d=decide_merge(gate_passed=True, explicitly_requested=True); print('ALLOW' if d.allowed else 'DENY', d.reason)")"
if [ "${decision%% *}" != "ALLOW" ]; then
  echo "borromeo merge: REFUSED by policy: ${decision#* }" >&2
  exit 1
fi

# --- Merge (prefer the PR trail; else local merge + push) -------------------
echo "borromeo merge: gate green — merging '$branch' into '$BASE'."
if command -v gh >/dev/null 2>&1 && gh pr view "$branch" >/dev/null 2>&1; then
  gh pr merge "$branch" --merge --delete-branch || {
    echo "borromeo merge: 'gh pr merge' failed; nothing merged." >&2
    exit 1
  }
else
  git checkout "$BASE" || exit 1
  if ! git merge --no-ff "$branch" -m "merge: $branch into $BASE (gated by borromeo)"; then
    git merge --abort 2>/dev/null || true
    echo "borromeo merge: merge conflict — aborted, nothing changed." >&2
    exit 1
  fi
  git push origin "$BASE" || exit 1
fi

# --- Audit receipt ----------------------------------------------------------
ts="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p .meta-harness/merges
PYTHONPATH=src python3 - "$branch" "$BASE" "$ts" <<'PY'
import json
import subprocess
import sys

branch, base, ts = sys.argv[1:4]
sha = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
receipt = {
    "action": "merge",
    "branch": branch,
    "base": base,
    "gate": "pass",
    "timestamp": ts,
    "merged_sha": sha,
}
path = f".meta-harness/merges/{ts}.json"
with open(path, "w") as fh:
    json.dump(receipt, fh, indent=2)
    fh.write("\n")
print(f"  audit receipt: {path}")
PY

echo "borromeo merge: done."
