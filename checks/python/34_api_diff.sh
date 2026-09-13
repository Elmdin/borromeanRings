#!/usr/bin/env bash
# 34_api_diff — public-API breaking-change detection.
#
# Compares the public surface (function/method/class signatures) of src against
# the merge-base with the integration branch. A removed symbol, a removed/renamed
# parameter, or a new REQUIRED parameter FAILS (semver protection) — unless
# [api].allow_breaking=true (a deliberate major-version release). Adding an optional
# param or a new symbol is not breaking. Justified for LIBRARIES whose API others
# depend on (see ADR-0039/0040). Native ast + git; no external tool. No base to
# diff (first commit / detached) ⇒ pass.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="34_api_diff"
log="$RECEIPT_DIR/$id.log"
cmd="public-API breaking-change detection (vs merge-base)"

src_dir="$(borromeanrings_project_cfg src_dir)"

base=""
for candidate in origin/dev dev origin/main main; do
  if git -C "$PROJECT_ROOT" rev-parse --verify --quiet "$candidate" >/dev/null 2>&1; then
    base="$candidate"
    break
  fi
done
merge_base=""
[ -n "$base" ] && merge_base="$(git -C "$PROJECT_ROOT" merge-base HEAD "$base" 2>/dev/null || true)"
if [ -z "$merge_base" ]; then
  echo "no base branch to diff against — nothing to check" >"$log"
  emit_noop "$id" "$cmd" "$log"
  exit 0
fi

PYTHONPATH="$BORROMEANRINGS_HOME/src" borromeanrings_py - "$PROJECT_ROOT" "$src_dir" "$merge_base" "$PROJECT_ROOT/borromeanrings.toml" >"$log" 2>&1 <<'PY'
import subprocess
import sys
from pathlib import Path

from meta_harness.api_diff import breaking_changes, public_api
from meta_harness.spine import load_config

root, src_dir, base, config_path = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
allow_breaking = load_config(config_path).api_allow_breaking

found: list[str] = []
for path in sorted((root / src_dir).rglob("*.py")):
    rel = path.relative_to(root).as_posix()
    # The `<rev>:./<rel>` form resolves relative to root, so this works whether the
    # governed project is a git root or a subdirectory of one.
    old_src = subprocess.run(  # noqa: git read of a prior version, trusted repo
        ["git", "-C", str(root), "show", f"{base}:./{rel}"],
        capture_output=True,
        text=True,
    ).stdout
    if not old_src.strip():
        continue  # new file — no prior API to break
    breaks = breaking_changes(public_api(old_src), public_api(path.read_text(encoding="utf-8")))
    found += [f"{rel}: {b}" for b in breaks]

if found:
    print(f"PUBLIC-API BREAKING CHANGES ({len(found)}):")
    for item in found:
        print(f"  - {item}")
    if allow_breaking:
        print("[api].allow_breaking=true — accepted (deliberate major-version release).")
        sys.exit(0)
    print("Restore compatibility, or set [api].allow_breaking=true for a breaking release.")
    sys.exit(1)
print("no public-API breaking changes vs the merge-base")
PY
code=$?
status="fail"
[ "$code" -eq 0 ] && status="pass"
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
