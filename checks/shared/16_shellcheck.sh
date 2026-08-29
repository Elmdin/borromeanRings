#!/usr/bin/env bash
# 16_shellcheck — lint the project's own shell.
#
# borromeanRings is roughly half bash, and that bash IS the trust root: the gate itself
# (verify.sh), every check, and the four Claude hooks. Until this check existed, all of
# it was ungated while the Python beside it faced eighteen gates — a governance hole in
# exactly the code that does the governing.
#
# Source resolution over suppression: scripts here `source` a sibling library through a
# runtime-computed path (`$(dirname "${BASH_SOURCE[0]}")/../_lib.sh`), which shellcheck
# cannot follow statically and reports as SC1091 — 31 times in this repo. Rather than
# blanket-excluding that code (which would also hide real unreadable-source bugs), the
# check passes `-x` plus `[shell].source_paths` (`SCRIPTDIR` = the checked script's own
# directory), which resolves every one of them properly. `[shell].exclude` remains as a
# per-code escape hatch and should stay empty.
#
# Fail-closed: any finding at any severity fails. No threshold, no ratchet — a lint
# finding is binary, and the suite is small enough to hold at zero.
# See docs/specs/SPEC-shellcheck.md and ADR-0050.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="16_shellcheck"
log="$RECEIPT_DIR/$id.log"
cmd="shell lint (shellcheck)"

if ! command -v shellcheck >/dev/null 2>&1; then
  printf "required tool 'shellcheck' not found on PATH\n" >"$log"
  printf "install it with: pip install shellcheck-py   (or your system package manager)\n" >>"$log"
  emit_receipt "$id" "$cmd" 127 "$log" "error"
  exit 127
fi

# The file list comes from git when the project is a repo (tracked shell only, so a
# scratch script never fails someone's gate) and from a bounded filesystem walk when it
# is not — the same tracked-vs-walk split 01_source_coherence uses, reusing its helper.
files="$(PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_ROOT" <<'PY'
import subprocess  # nosec B404 — fixed argv, no shell; only queries git
import sys
from pathlib import Path

from meta_harness.source_coherence import walk_sources

root = Path(sys.argv[1])
try:
    listed = subprocess.run(  # nosec B603 B607 — fixed argv, no shell
        ["git", "-C", str(root), "ls-files", "*.sh"],
        capture_output=True,
        text=True,
        check=False,
    )
except OSError:
    listed = None

if listed is not None and listed.returncode == 0:
    print("\n".join(line for line in listed.stdout.splitlines() if line.strip()))
else:
    print("\n".join(walk_sources(root, ".sh")))
PY
)"

if [ -z "$files" ]; then
  echo "no shell scripts in this project — nothing to lint" >"$log"
  emit_noop "$id" "$cmd" "$log"
  exit 0
fi

# Build -P/-e flags from the spine so source resolution and any per-code exclusion are
# declared policy rather than hardcoded here. Python emits one value per line, so nothing
# has to parse a tuple repr out of a string.
cfg_lines() {
  PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_ROOT/borromeanrings.toml" "$1" <<'CFG'
import sys

from meta_harness.spine import load_config

print("\n".join(getattr(load_config(sys.argv[1]), sys.argv[2])))
CFG
}

flags=()
while IFS= read -r value; do
  [ -n "$value" ] && flags+=("-P" "$value")
done < <(cfg_lines shell_source_paths)
while IFS= read -r value; do
  [ -n "$value" ] && flags+=("-e" "$value")
done < <(cfg_lines shell_exclude)

# Deliberately NOT xargs: on a long file list xargs splits into several invocations and
# reports only the LAST exit code, silently dropping findings from earlier batches — a
# fail-open hole in gate plumbing. One invocation, one exit code.
mapfile -t filelist <<<"$files"
count="${#filelist[@]}"

# Run from PROJECT_ROOT so relative paths and SCRIPTDIR resolution are correct.
(
  cd "$PROJECT_ROOT" || exit 1
  shellcheck -x -f gcc "${flags[@]}" "${filelist[@]}"
) >"$log" 2>&1
code=$?

if [ "$code" -eq 0 ]; then
  echo "shellcheck clean — $count shell script(s), 0 findings" >>"$log"
  emit_receipt "$id" "$cmd" 0 "$log" "pass"
  exit 0
fi
{
  echo ""
  echo "shellcheck reported findings in $count scanned script(s) — fix them, or add a"
  echo "justified code to [shell].exclude if the rule genuinely does not apply here."
} >>"$log"
emit_receipt "$id" "$cmd" "$code" "$log" "fail"
exit "$code"
