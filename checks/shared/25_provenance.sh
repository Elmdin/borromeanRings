#!/usr/bin/env bash
# 25_provenance — re-authored text must not reproduce its declared source.
#
# ADR-0020 lets this repo port IDEAS from a CC-licensed sibling, never its EXPRESSION.
# On a branch, every file changed since the merge-base under [provenance].paths is
# shingled (six consecutive normalized words) and compared with every file under
# [provenance].sources (config, then the colon-separated BORROMEANRINGS_PROVENANCE_SOURCES
# environment variable — the way a machine-local sibling path stays out of the config).
# Any overlapping shingle not covered by [provenance].allow fails, with both locations.
# Binary, no score: the gate never guesses which overlaps are "generic" — the human
# classifies once, in the allowlist, and the diff reviews it. Off (noop, "rule off") with
# no [provenance] table; noop with no sources or no changed file under paths; fails closed
# on an absent/unreadable/empty source or a git error inside a repo. See
# docs/specs/SPEC-provenance.md and ADR-0070.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="25_provenance"
log="$RECEIPT_DIR/$id.log"
cmd="provenance (changed docs share no unlisted 6-word shingle with declared sources)"

# Gather from git here; decide in Python. "Cannot list changes" is passed through as an
# error string so the decision step fails closed on it only when the rule is actually on.
git_error=""
merge_base=""
changed=""
git_prefix=""
if ! git -C "$PROJECT_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git_error="not a git repository"
else
  base=""
  for candidate in origin/dev dev origin/main main; do
    if git -C "$PROJECT_ROOT" rev-parse --verify --quiet "$candidate" >/dev/null 2>&1; then
      base="$candidate"
      break
    fi
  done
  if [ -n "$base" ]; then
    if ! merge_base="$(git -C "$PROJECT_ROOT" merge-base HEAD "$base" 2>/dev/null)"; then
      git_error="git merge-base HEAD $base failed"
    elif ! changed="$(git -C "$PROJECT_ROOT" diff --relative --name-only "$merge_base"...HEAD 2>/dev/null)"; then
      git_error="git diff $merge_base...HEAD failed"
    fi
    git_prefix="$(git -C "$PROJECT_ROOT" rev-parse --show-prefix 2>/dev/null || true)"
  fi
fi

PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - \
  "$PROJECT_ROOT" "$PROJECT_ROOT/borromeanrings.toml" "$merge_base" "$git_prefix" \
  "$git_error" "$changed" "${BORROMEANRINGS_PROVENANCE_SOURCES:-}" >"$log" 2>&1 <<'PY'
import os
import subprocess  # nosec B404 — fixed argv, no shell; only reads git objects
import sys
from pathlib import Path

from meta_harness.provenance import DEFAULT_N, compare, render
from meta_harness.spine import load_config

root, cfg_path, merge_base, prefix, git_error, changed_blob, env_sources = sys.argv[1:8]
NOOP = 3
SKIP_DIRS = {
    ".git",
    ".meta-harness",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "mutants",
    "node_modules",
    ".venv",
    "venv",
}
project = Path(root).resolve()

cfg = load_config(cfg_path)
env_list = [p for p in env_sources.split(":") if p.strip()]
if not cfg.provenance_declared and not env_list:
    print("no [provenance] section — rule off")
    sys.exit(NOOP)
declared = [str(project / p) if not os.path.isabs(p) else p for p in cfg.provenance_sources]
sources = declared + env_list
if not sources:
    print("no provenance sources declared — nothing to compare against")
    print("(declare [provenance].sources, or set BORROMEANRINGS_PROVENANCE_SOURCES=/path:/path)")
    sys.exit(NOOP)

if git_error:
    print(f"cannot list changed files ({git_error}) — failing closed")
    sys.exit(1)
if not merge_base:
    print("no base branch to diff against — nothing to check")
    sys.exit(NOOP)

prefixes = tuple(p.rstrip("/") + "/" for p in cfg.provenance_paths)
exact = set(cfg.provenance_paths)
candidates = [
    p for p in changed_blob.splitlines() if p.strip() and (p in exact or p.startswith(prefixes))
]


def show(path: str) -> str | None:
    """Text of ``path`` at HEAD; None if deleted on this branch or not UTF-8 text."""
    result = subprocess.run(  # nosec B603 B607 — fixed argv, no shell
        ["git", "-C", root, "show", f"HEAD:{prefix}{path}"], capture_output=True, check=False
    )
    if result.returncode != 0 or b"\0" in result.stdout[:8192]:
        return None
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return None


changed = {p: text for p in candidates if (text := show(p)) is not None}
if not changed:
    print(f"no changed files under {list(cfg.provenance_paths)} since merge-base — nothing to check")
    sys.exit(NOOP)


def read_text(path: Path) -> str | None:
    """Strictly decoded text, or None for a binary (NUL in the first block / not UTF-8)."""
    try:
        with path.open("rb") as fh:
            if b"\0" in fh.read(8192):
                return None
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def walk(top: Path) -> list[Path]:
    if top.is_file():
        return [top]
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(top):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        found.extend(Path(dirpath) / name for name in sorted(filenames))
    return found


source_texts: dict[str, str] = {}
for entry in sources:
    top = Path(entry)
    if not top.exists():
        print(f"provenance source '{entry}' does not exist — failing closed")
        sys.exit(1)
    try:
        files = walk(top)
        texts = {str(f): t for f in files if (t := read_text(f)) is not None}
    except OSError as exc:
        print(f"provenance source '{entry}' is unreadable ({exc}) — failing closed")
        sys.exit(1)
    inside = {p for p in texts if Path(p).resolve().is_relative_to(project)}
    for p in inside:
        print(f"skipping source '{p}': inside this project (a self-quote is not a finding)")
        del texts[p]
    if not texts:
        print(f"provenance source '{entry}' yields zero readable text files — failing closed")
        sys.exit(1)
    source_texts.update(texts)

try:
    result = compare(changed, source_texts, cfg.provenance_allow)
except ValueError as exc:
    print(str(exc))
    sys.exit(1)

scope = f"{len(changed)} changed file(s) against {len(source_texts)} source file(s)"
if result.allowed:
    seen = sorted({o.shingle for o in result.allowed})
    print(f"allowed overlaps seen ({len(seen)} distinct shingle(s), per [provenance].allow):")
    for shingle in seen:
        print(f'  "{shingle}"')
if result.findings:
    print(
        f"PROVENANCE: {len(result.findings)} unlisted {DEFAULT_N}-word overlap(s) in {scope} — "
        "re-author the passage, or add it to [provenance].allow with a reason:"
    )
    print(render(result.findings))
    sys.exit(1)
print(f"no unlisted {DEFAULT_N}-word overlap in {scope}")
PY
code=$?
status="$(borromeanrings_status_for_code "$code")"
[ "$status" = "noop" ] && code=0
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
