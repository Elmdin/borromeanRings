#!/usr/bin/env bash
# borromeo merge — gate-gated, explicitly-invoked merge of the current branch
# into a base branch (default: main).
#
# It executes a human's merge decision; it never originates one. A merge happens
# only if (a) you ran this command AND (b) ./verify.sh exits 0 (fail-closed).
#
# Usage:  ./merge.sh [--auto] [base]      (base defaults to main)
#   default : run the local gate, then merge immediately.
#   --auto  : run the local gate, then WAIT for the PR's CI checks to pass, then
#             merge. Still explicitly invoked per-merge — there is no standing,
#             unattended auto-merge mode (that would be self-rewriting, forbidden).
#             Used because server-side required checks need a paid plan on a
#             private repo; borromeo orchestrates the wait itself. See ADR-0009.
#
# Policy is in meta_harness.merge_policy; this is the plumbing.
# See docs/specs/SPEC-merge.md and docs/adr/{0007,0009}-*.md.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

AUTO=0
positional=()
for arg in "$@"; do
  case "$arg" in
    --auto) AUTO=1 ;;
    *) positional+=("$arg") ;;
  esac
done
BASE="${positional[0]:-main}"
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

# --- Merge --------------------------------------------------------------------
if [ "$AUTO" = "1" ]; then
  # Command-orchestrated auto-merge: wait for the PR's CI to pass, then merge.
  if ! command -v gh >/dev/null 2>&1 || ! gh pr view "$branch" >/dev/null 2>&1; then
    echo "borromeo merge --auto: needs an open PR for '$branch' (and gh)." >&2
    exit 1
  fi
  # Wait for CI to REGISTER at least one check before watching — otherwise a
  # freshly-created PR reports "no checks" and we'd refuse by mistake (a race).
  echo "borromeo merge: local gate green — waiting for the PR's CI checks to register…"
  registered=0
  for _ in $(seq 1 24); do
    n="$(gh pr view "$branch" --json statusCheckRollup -q '.statusCheckRollup | length' 2>/dev/null || echo 0)"
    if [ "${n:-0}" -gt 0 ]; then registered=1; break; fi
    sleep 5
  done
  if [ "$registered" -ne 1 ]; then
    echo "borromeo merge: REFUSED — no CI checks registered after waiting. Nothing merged." >&2
    exit 1
  fi
  echo "borromeo merge: checks registered — waiting for them to pass…"
  if ! gh pr checks "$branch" --watch --fail-fast; then
    echo "borromeo merge: REFUSED — CI checks did not pass. Nothing merged." >&2
    exit 1
  fi
  gh pr merge "$branch" --merge --delete-branch || {
    echo "borromeo merge: 'gh pr merge' failed after CI passed; nothing merged." >&2
    exit 1
  }
  mode="auto (local gate + CI)"
else
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
  mode="immediate (local gate)"
fi

# --- Audit receipt ----------------------------------------------------------
ts="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p .meta-harness/merges
PYTHONPATH=src python3 - "$branch" "$BASE" "$ts" "$mode" <<'PY'
import json
import subprocess
import sys

branch, base, ts, mode = sys.argv[1:5]
sha = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
receipt = {
    "action": "merge",
    "mode": mode,
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
