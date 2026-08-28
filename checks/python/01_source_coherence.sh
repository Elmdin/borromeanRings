#!/usr/bin/env bash
# 01_source_coherence — is the gate actually looking at this project's code?
#
# Every source-reading check (00_build, 30_typecheck, 32_complexity, 33_coupling,
# 45_docstrings, 50_security) resolves its target from [project].src_dir/package. If that
# path holds no source, each one exits 0 — and the verdict reports a full green while the
# gate is blind to the real code. Greenfield (no source anywhere) is legitimate and stays
# green; a src_dir that points at nothing WHILE tracked source exists elsewhere is a
# misconfiguration and fails closed.
#
# Resolves the configured path with the SAME `find … -name '*.py'` semantics the checks it
# protects use, so the guard and those checks can never disagree. "Elsewhere" means
# git-TRACKED source (an untracked scratch file must never fail a gate), with a bounded
# filesystem walk as the fallback for a non-git project.
# See docs/specs/SPEC-self-status.md and ADR-0049.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="01_source_coherence"
log="$RECEIPT_DIR/$id.log"
cmd="source coherence (declared src_dir resolves to real code)"

src_dir="$(borromeanrings_project_cfg src_dir)"
package="$(borromeanrings_project_cfg package)"
tests_dir="$(borromeanrings_project_cfg tests_dir)"

PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_ROOT" "$src_dir" "$package" "$tests_dir" >"$log" 2>&1 <<'PY'
import subprocess  # nosec B404 — fixed argv, no shell; only queries git
import sys
from pathlib import Path

from meta_harness.source_coherence import assess, implementation_sources, walk_sources

project_root, src_dir, package = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
tests_dir = sys.argv[4] or "tests"
SUFFIX = ".py"

# Fail closed on an unresolvable src_dir. Empty would make `project_root / src_dir` the
# repo ROOT, whose recursive scan finds source in almost any project — so a broken or
# unreadable config would produce a confident PASS from the one check whose entire job is
# to catch a config that doesn't match reality.
if not src_dir.strip():
    print("[project].src_dir is empty or unreadable — cannot verify what the gate inspects")
    sys.exit(1)


def _configured_count() -> int:
    """Source files at the declared path — same recursive semantics as the checks."""
    target = project_root / src_dir
    if not target.is_dir():
        return 0
    return sum(1 for _ in target.rglob(f"*{SUFFIX}"))


def _tracked_sources() -> list[str]:
    """Version-controlled source anywhere in the project; [] when undecidable."""
    try:
        result = subprocess.run(  # nosec B603 B607 — fixed argv, no shell
            ["git", "-C", str(project_root), "ls-files"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        result = None
    if result is not None and result.returncode == 0:
        return [line for line in result.stdout.splitlines() if line.endswith(SUFFIX)]
    # Not a git repo (or git absent): bounded walk, pruning caches/vendored trees.
    return walk_sources(project_root, SUFFIX)


# Only a genuine second SOURCE tree counts as "the gate is blind to real code":
# tests, packaging shims and vendored trees are not implementation, and counting them
# would fail the gate for a project whose only code so far is a failing test (TDD RED).
result = assess(
    configured_count=_configured_count(),
    tracked_sources=implementation_sources(_tracked_sources(), tests_dir=tests_dir),
    configured_path=src_dir,
)
print(result.message)

# The checks this guard protects do NOT all count the same thing: 32_complexity,
# 33_coupling and 45_docstrings additionally require [project].package and report `noop`
# without it. A guard that stayed silent here would certify "the gate sees your code"
# while three checks measured nothing. `package` is legitimately optional (a scripts-only
# project has none), so this reports rather than fails — the `noop` receipts make the
# blindness visible either way.
if result.status == "pass" and not package.strip():
    print(
        "note: [project].package is unset — the package-scoped checks "
        "(32_complexity, 33_coupling, 45_docstrings) will report 'noop' and measure nothing."
    )
sys.exit({"pass": 0, "noop": 3, "fail": 1}[result.status])
PY
code=$?
status="$(borromeanrings_status_for_code "$code")"
[ "$status" = "noop" ] && code=0
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
