#!/usr/bin/env bash
# 17_prior_art — did anyone look before building this?
#
# On a feature branch, a change that ADDS PUBLIC SURFACE (a new top-level function or
# class not starting with `_`, compared with the merge-base) must also add or modify a
# survey record under [prior_art].dir (default docs/surveys/): a short note of what
# already existed and why building was still right. The 13_adr pattern applied to reuse
# (ADR-0043 -> ADR-0051). The gate demands that the question was asked on the record; it
# does not judge the answer.
#
# Honest limits: the ecosystem half ("is there a library?") is NOT gated -- no key-free
# package API supports free-text search, so a gate could not answer its own question
# (docs/research/AGENT-TOOLING-SURVEY.md). In-repo reimplementation signals come from
# Ruff's reimplemented-* rules in 20_lint, not from here. No new public surface => noop.
# See docs/specs/SPEC-prior-art.md.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="17_prior_art"
log="$RECEIPT_DIR/$id.log"
cmd="prior-art discipline (new public surface needs a recorded survey)"

branch="$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo HEAD)"

base=""
for candidate in origin/dev dev origin/main main; do
  if git -C "$PROJECT_ROOT" rev-parse --verify --quiet "$candidate" >/dev/null 2>&1; then
    base="$candidate"; break
  fi
done
merge_base=""
[ -n "$base" ] && merge_base="$(git -C "$PROJECT_ROOT" merge-base HEAD "$base" 2>/dev/null || true)"
if [ -z "$merge_base" ]; then
  echo "no base branch to diff against — nothing to check" >"$log"
  emit_noop "$id" "$cmd" "$log"
  exit 0
fi

# --relative keeps paths correct for a git-root OR subdirectory project; the prefix is
# what `git show <rev>:<path>` needs to reach the same files from the repo root.
changed="$(git -C "$PROJECT_ROOT" diff --relative --name-only "$merge_base"...HEAD 2>/dev/null || true)"
git_prefix="$(git -C "$PROJECT_ROOT" rev-parse --show-prefix 2>/dev/null || true)"
src_dir="$(borromeanrings_project_cfg src_dir)"

PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - \
  "$PROJECT_ROOT" "$PROJECT_ROOT/borromeanrings.toml" "$branch" "$merge_base" "$git_prefix" "$src_dir" "$changed" >"$log" 2>&1 <<'PY'
import subprocess  # nosec B404 — fixed argv, no shell; only reads git objects
import sys

from meta_harness.prior_art import new_public_symbols, survey_violation
from meta_harness.spine import load_config

root, cfg_path, branch, merge_base, prefix, src_dir, changed_blob = sys.argv[1:8]
cfg = load_config(cfg_path)
changed = [p for p in changed_blob.splitlines() if p.strip()]
src_prefix = src_dir.rstrip("/") + "/"
py_changed = [p for p in changed if p.endswith(".py") and p.startswith(src_prefix)]


def show(rev: str, path: str) -> str:
    """Source of ``path`` at ``rev``; "" if it did not exist there."""
    result = subprocess.run(  # nosec B603 B607 — fixed argv, no shell
        ["git", "-C", root, "show", f"{rev}:{prefix}{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else ""


old = {p: show(merge_base, p) for p in py_changed}
new = {p: show("HEAD", p) for p in py_changed}
added = new_public_symbols(old, new)

if not added:
    print(f"no new public surface in {src_dir}/ on this branch — nothing to survey")
    sys.exit(3)

violation = survey_violation(
    branch,
    added,
    changed,
    survey_dir=cfg.prior_art_dir,
    require_prefixes=cfg.prior_art_require_prefixes,
)
if violation:
    print("PRIOR-ART VIOLATION:")
    print("  " + violation)
    sys.exit(1)
total = sum(len(v) for v in added.values())
print(f"new public surface ({total} symbol(s)) is accompanied by a survey record — OK")
PY
code=$?
status="$(borromeanrings_status_for_code "$code")"
[ "$status" = "noop" ] && code=0
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
