#!/usr/bin/env bash
# borromeanRings — the `worktree` executor: run the gate against a SNAPSHOT of this
# project, in a throwaway git worktree, and bring the receipts back.
#
# Why a separate entry point and not a flag on verify.sh: verify.sh is the gate every
# hook, CI job and governed project already invokes; a new code path inside it can
# regress the default path, and the default path's job is to be boring. This script
# is a caller OF verify.sh — it prepares a tree, runs the unmodified gate there, and
# copies the bundle back. `local` (plain ./verify.sh) is untouched by construction.
# See docs/adr/0076-worktree-executor.md and SPEC-executor.md (lands with #203).
#
# What it gives you (the SPEC's guarantees, in this script's terms):
#   * snapshot   — HEAD + the dirty tree (tracked edits AND untracked-not-ignored
#                  files); ignored paths (.meta-harness/, mutants/, caches, venvs)
#                  are NOT materialised;
#   * G8         — `git rev-parse HEAD` and `git rev-parse --abbrev-ref HEAD` inside
#                  the worktree equal the primary's (asserted at runtime, fail-closed);
#   * isolation  — its own working tree, index, .meta-harness/, mutants/ and tool
#                  caches; it shares only the object store, and never commits, never
#                  moves a ref, never writes anything into the primary except the
#                  copied receipt bundle;
#   * cleanup    — the worktree and its temp dir go away on every exit path (success,
#                  failure, interrupt), and the removal is bounded to the directory
#                  this run created.
#
# Usage: ./run-in-worktree.sh [--project DIR] [--heavy] [--keep]
set -uo pipefail

BORROMEANRINGS_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'USAGE'
Usage: run-in-worktree.sh [--project DIR] [--heavy] [--keep]

  --project DIR  the governed project (default: $BORROMEANRINGS_PROJECT,
                 $CLAUDE_PROJECT_DIR, then $PWD — the same resolution verify.sh uses)
  --heavy        pass --heavy through to the gate (CI-tier lane)
  --keep         do NOT remove the worktree; print its path for inspection

Prints `RECEIPTS: <dir>` (the bundle copied back into the project) and, with --keep,
`WORKTREE: <dir>`. Exits with the gate's own exit code.
USAGE
}

die() {
  printf 'run-in-worktree.sh: %s\n' "$1" >&2
  exit 1
}

KEEP=0
PROJECT_ARG=""
GATE_ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --keep) KEEP=1 ;;
    --heavy) GATE_ARGS+=("--heavy") ;;
    --project)
      [ $# -ge 2 ] || die "--project needs a directory"
      PROJECT_ARG="$2"
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      die "unknown argument '$1'"
      ;;
  esac
  shift
done

PROJECT_ROOT="${PROJECT_ARG:-${BORROMEANRINGS_PROJECT:-${CLAUDE_PROJECT_DIR:-$PWD}}}"
PROJECT_ROOT="$(cd "$PROJECT_ROOT" 2>/dev/null && pwd)" || die "no such project directory"
[ -f "$PROJECT_ROOT/borromeanrings.toml" ] ||
  die "no borromeanrings.toml in $PROJECT_ROOT — run borromeanRings's init.sh there first."

# --- Snapshot identity (head, tree, branch) --------------------------------------
# The worktree executor needs a repository: there is no worktree without one. Fail
# closed and say so, rather than silently degrading to a local run.
TOP="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel 2>/dev/null)" ||
  die "$PROJECT_ROOT is not inside a git repository — the worktree executor needs one."
HEAD_SHA="$(git -C "$PROJECT_ROOT" rev-parse HEAD 2>/dev/null)" ||
  die "no commit yet in $TOP — the worktree executor needs at least one."
BRANCH="$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null)"
# "" for a repo-root project, "sub/dir/" when the governed project is a subdirectory.
PREFIX="$(git -C "$PROJECT_ROOT" rev-parse --show-prefix 2>/dev/null)"
PREFIX="${PREFIX%/}"
PRIMARY_INDEX="$(git -C "$PROJECT_ROOT" rev-parse --absolute-git-dir)/index"

WT_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/borromeanrings-worktree.XXXXXX")" ||
  die "could not create a temp directory"
WT_ROOT_RESOLVED="$(cd "$WT_ROOT" && pwd -P)"
WT_DIR="$WT_ROOT/tree"
SNAPSHOT_INDEX="$WT_ROOT/index-snapshot"

# Cleanup on EVERY exit path — success, failure, and interrupt (the INT/TERM/HUP
# traps exit, which runs this one). The rm is bounded to the directory this run
# created: re-resolve it and refuse if it is anything else (a symlink swapped under
# us, a $TMPDIR that moved). Never a bare rm -rf on a computed path.
cleanup() {
  local resolved
  if [ "$KEEP" = "1" ] && [ -d "$WT_DIR" ]; then
    printf 'WORKTREE: %s\n' "$WT_DIR"
    printf 'kept for inspection — remove with: git -C %s worktree remove --force %s && rm -rf %s\n' \
      "$TOP" "$WT_DIR" "$WT_ROOT"
    return
  fi
  # `worktree remove` deregisters exactly this worktree. Deliberately NOT
  # `worktree prune`: that is repo-wide, and this executor touches nothing that
  # belongs to another run.
  if [ -d "$WT_DIR" ] && ! git -C "$TOP" worktree remove --force "$WT_DIR" >/dev/null 2>&1; then
    printf 'run-in-worktree.sh: could not deregister %s — `git -C %s worktree prune` clears its metadata\n' \
      "$WT_DIR" "$TOP" >&2
  fi
  resolved="$(cd "$WT_ROOT" 2>/dev/null && pwd -P || true)"
  if [ -z "$resolved" ]; then
    return
  elif [ "$resolved" = "$WT_ROOT_RESOLVED" ]; then
    rm -rf "$WT_ROOT"
  else
    printf 'run-in-worktree.sh: refusing to remove %s — it resolves to %s, not the directory this run created (%s)\n' \
      "$WT_ROOT" "$resolved" "$WT_ROOT_RESOLVED" >&2
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

# Only now — with cleanup armed, so this refusal does not leak the temp dir it is
# refusing to use. A $TMPDIR inside the repository would put the worktree in the
# snapshot of the next run.
TOP_RESOLVED="$(cd "$TOP" && pwd -P)"
case "$WT_ROOT_RESOLVED/" in
  "$TOP_RESOLVED"/*) die "refusing to build the worktree inside the repository ($WT_ROOT)" ;;
esac

# The dirty tree as a git object: start from the primary's index (so its staged state
# is preserved), stage everything git can see, and write the tree. `git add -A`
# respects .gitignore, so ignored paths — .meta-harness/, mutants/, caches, venvs —
# are excluded by construction, and untracked-not-ignored files are included.
if [ -f "$PRIMARY_INDEX" ]; then
  cp "$PRIMARY_INDEX" "$SNAPSHOT_INDEX" || die "could not copy the index"
fi
GIT_INDEX_FILE="$SNAPSHOT_INDEX" git -C "$TOP" add -A ||
  die "could not stage the working tree into the snapshot index"
TREE="$(GIT_INDEX_FILE="$SNAPSHOT_INDEX" git -C "$TOP" write-tree)" ||
  die "could not write the snapshot tree"

# --- Materialise -----------------------------------------------------------------
# Detach at the primary's HEAD (this never trips git's "already checked out"
# safeguard and never touches the branch ref), then point the worktree's HEAD at the
# same branch so branch-reading checks (08_branch, 13_adr, …) see what the primary
# sees. A detached worktree would report its branch as "HEAD" and quietly change
# those receipts — that is G8, and it is asserted below rather than assumed.
git -C "$TOP" worktree add --detach --quiet "$WT_DIR" "$HEAD_SHA" ||
  die "could not create the worktree at $WT_DIR"
if [ "$BRANCH" != "HEAD" ]; then
  git -C "$WT_DIR" symbolic-ref HEAD "refs/heads/$BRANCH" ||
    die "could not point the worktree's HEAD at refs/heads/$BRANCH"
fi
git -C "$WT_DIR" read-tree --reset -u "$TREE" ||
  die "could not materialise the snapshot tree in the worktree"
# read-tree left the worktree's index EQUAL TO THE SNAPSHOT, which would make every
# untracked file look tracked — and checks that read the tracked set (12_secrets,
# 01_source_coherence) would then see a different project than `local` does. Restore
# the primary's index so `git status` and `git ls-files` match it exactly.
if [ -f "$PRIMARY_INDEX" ]; then
  cp "$PRIMARY_INDEX" "$(git -C "$WT_DIR" rev-parse --absolute-git-dir)/index" ||
    die "could not restore the primary's index in the worktree"
fi

WT_HEAD="$(git -C "$WT_DIR" rev-parse HEAD)"
WT_BRANCH="$(git -C "$WT_DIR" rev-parse --abbrev-ref HEAD)"
[ "$WT_HEAD" = "$HEAD_SHA" ] && [ "$WT_BRANCH" = "$BRANCH" ] ||
  die "branch identity (G8) not met: worktree is $WT_BRANCH@$WT_HEAD, primary is $BRANCH@$HEAD_SHA"

WT_PROJECT="$WT_DIR${PREFIX:+/$PREFIX}"

# --- Toolchain: the checks must resolve THIS tree's source ------------------------
project_cfg() {
  PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_ROOT/borromeanrings.toml" "$1" <<'PY'
import sys

from meta_harness.spine import load_config

print(getattr(load_config(sys.argv[1]), sys.argv[2]))
PY
}
LANGUAGE="$(project_cfg language 2>/dev/null || echo python)"
PACKAGE="$(project_cfg package 2>/dev/null || echo '')"
SRC_DIR="$(project_cfg src_dir 2>/dev/null || echo '')"

if [ "$LANGUAGE" = "python" ] && [ -n "$PACKAGE" ]; then
  # Put the worktree's source first, so an uninstalled or path-installed package
  # resolves here. This is a mitigation, not a guarantee: a modern editable install
  # hooks sys.meta_path, which runs BEFORE sys.path — so ASK where the package
  # actually resolves, and refuse to run if the answer is outside the worktree. A
  # valid receipt describing the primary's code is exactly the false green the gate
  # exists to prevent. See ADR-0076.
  export PYTHONPATH="$WT_PROJECT/$SRC_DIR${PYTHONPATH:+:$PYTHONPATH}"
  ORIGIN="$(cd "$WT_PROJECT" && python3 - "$PACKAGE" 2>/dev/null <<'PY'
import importlib.util
import sys

try:
    spec = importlib.util.find_spec(sys.argv[1])
except (ImportError, ValueError):
    spec = None
print((spec.origin or "") if spec is not None else "")
PY
  )"
  SHADOW="$(PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$ORIGIN" "$WT_DIR" <<'PY'
import sys

from meta_harness.executor import import_shadow_violation

print(import_shadow_violation(sys.argv[1], sys.argv[2]) or "")
PY
  )"
  [ -z "$SHADOW" ] || die "$SHADOW"
fi

# --- Run the unmodified gate in the worktree --------------------------------------
printf 'borromeanRings worktree executor\n  primary:  %s\n  worktree: %s\n  snapshot: head=%s tree=%s branch=%s\n\n' \
  "$PROJECT_ROOT" "$WT_PROJECT" "$HEAD_SHA" "$TREE" "$BRANCH"
BORROMEANRINGS_PROJECT="$WT_PROJECT" bash "$BORROMEANRINGS_HOME/verify.sh" \
  ${GATE_ARGS[@]+"${GATE_ARGS[@]}"}
GATE_CODE=$?

# --- Bring the bundle back --------------------------------------------------------
# The worktree run wrote its receipts into its OWN .meta-harness/ (that is the
# isolation). Copy the run directory byte-exact into the primary's evidence area —
# the executor never re-hashes or edits a receipt (G6). The verdict was already
# computed in the worktree, where the recorded log paths still existed; the copied
# bundle stays verifiable in the primary through reader-side log resolution
# (meta_harness.receipts.resolve_log_path).
BUNDLE=""
if [ -d "$WT_PROJECT/.meta-harness/receipts" ]; then
  BUNDLE="$(find "$WT_PROJECT/.meta-harness/receipts" -mindepth 1 -maxdepth 1 -type d | sort | tail -1)"
fi
if [ -z "$BUNDLE" ]; then
  printf 'run-in-worktree.sh: the gate produced no receipt bundle in the worktree (exit %s)\n' \
    "$GATE_CODE" >&2
  exit "${GATE_CODE:-1}"
fi

RUN_ID="$(basename "$BUNDLE")"
DEST="$PROJECT_ROOT/.meta-harness/receipts/$RUN_ID"
{
  printf 'kind: worktree\n'
  printf 'head: %s\n' "$HEAD_SHA"
  printf 'tree: %s\n' "$TREE"
  printf 'branch: %s\n' "$BRANCH"
  printf 'run_id: %s\n' "$RUN_ID"
  printf 'primary: %s\n' "$PROJECT_ROOT"
  printf 'worktree: %s\n' "$WT_PROJECT"
  printf 'harness_home: %s\n' "$BORROMEANRINGS_HOME"
} >"$BUNDLE/executor.txt"
mkdir -p "$DEST" && cp -R "$BUNDLE/." "$DEST/" ||
  die "could not copy the receipt bundle to $DEST"

printf 'RECEIPTS: %s\n' "$DEST"
exit "$GATE_CODE"
