#!/usr/bin/env bash
# Repository-layout gate: specs live under [layout].specs_dir, repo-root .md files
# are an allowlist, and large flat test suites must be grouped by type. Each rule is
# opt-in (off when its config is empty/zero) ⇒ pass. Fail-closed on any violation.
# See docs/specs/SPEC-layout.md and ADR-0018.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="07_layout"
log="$RECEIPT_DIR/$id.log"
cmd="repository layout (specs dir, root-doc allowlist, test grouping)"

# Repo-relative SPEC*.md paths (exclude VCS/build dirs). NUL-safe via -print + sort.
specs="$(cd "$PROJECT_ROOT" && find . \
  \( -path ./.git -o -path './*/.git' -o -name node_modules -o -name .meta-harness \) -prune -o \
  -type f -name 'SPEC*.md' -print 2>/dev/null | sed 's#^\./##' | sort || true)"
# Repo-root *.md filenames only (maxdepth 1).
root_md="$(cd "$PROJECT_ROOT" && find . -maxdepth 1 -type f -name '*.md' -print 2>/dev/null | sed 's#^\./##' | sort || true)"

PYTHONPATH="$BORROMEANRINGS_HOME/src" \
  BORROMEANRINGS_SPECS="$specs" BORROMEANRINGS_ROOT_MD="$root_md" \
  python3 - "$PROJECT_ROOT" "$PROJECT_ROOT/borromeanrings.toml" >"$log" 2>&1 <<'PY'
import os
import sys
from pathlib import Path

from meta_harness.layout import disallowed_root_docs, excess_flat_tests, misplaced_specs
from meta_harness.spine import load_config

project_root, config_path = Path(sys.argv[1]), sys.argv[2]
cfg = load_config(config_path)

specs = [p for p in os.environ.get("BORROMEANRINGS_SPECS", "").splitlines() if p.strip()]
root_md = [p for p in os.environ.get("BORROMEANRINGS_ROOT_MD", "").splitlines() if p.strip()]

# Count test files DIRECTLY under tests_dir (ungrouped/flat), if it exists.
tests_dir = project_root / cfg.tests_dir
flat_tests = 0
if tests_dir.is_dir():
    flat_tests = sum(
        1
        for p in tests_dir.iterdir()
        if p.is_file() and (p.name.startswith("test_") or p.name.endswith("_test.py")) and p.suffix == ".py"
    )

problems: list[str] = []

bad_specs = misplaced_specs(specs, cfg.specs_dir)
if bad_specs:
    problems.append(f"SPEC files not under '{cfg.specs_dir}/':")
    problems += [f"  - {p}" for p in bad_specs]

bad_root = disallowed_root_docs(root_md, cfg.root_doc_allowlist)
if bad_root:
    allowed = ", ".join(cfg.root_doc_allowlist)
    problems.append(f"root .md files not in the allowlist ({allowed}):")
    problems += [f"  - {p}" for p in bad_root]

if excess_flat_tests(flat_tests, cfg.test_grouping_threshold):
    groups = "/".join(cfg.test_groups) or "type subdirectories"
    problems.append(
        f"{flat_tests} flat test files in '{cfg.tests_dir}/' exceed "
        f"threshold {cfg.test_grouping_threshold} — group them by type ({groups})"
    )

if problems:
    print("LAYOUT VIOLATIONS:")
    for line in problems:
        print(line)
    sys.exit(1)
print("layout OK — specs placed, root docs allowed, tests within grouping threshold")
PY
code=$?
status="fail"
[ "$code" -eq 0 ] && status="pass"
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
