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
    sys.exit(0)

# The walk is the fallback for a project that is genuinely NOT a repo, where "tracked"
# has no meaning. It must not also absorb a git *failure* inside a real repo: the walk
# includes UNTRACKED files, and this check fails builds, so a scratch script could then
# fail someone's gate. Same split 01_source_coherence makes (ADR-0049).
try:
    is_repo = subprocess.run(  # nosec B603 B607 — fixed argv, no shell
        ["git", "-C", str(root), "rev-parse", "--git-dir"],
        capture_output=True,
        check=False,
    )
except OSError:
    is_repo = None
if is_repo is not None and is_repo.returncode == 0:
    sys.stderr.write(
        "git is present and this is a repository, but `git ls-files` failed — "
        "cannot distinguish tracked shell from scratch files; failing closed.\n"
    )
    sys.exit(1)

print("\n".join(walk_sources(root, ".sh")))
PY
)"
list_code=$?
if [ "$list_code" -ne 0 ]; then
  echo "cannot enumerate this project's shell scripts — failing closed" >"$log"
  emit_receipt "$id" "$cmd" "$list_code" "$log" "fail"
  exit "$list_code"
fi

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

# A failing config read must be loud. Swallowing it emptied `flags`, which dropped
# `-P SCRIPTDIR` and resurrected 33 stale SC1091 findings — a confusing failure that
# hides its own cause.
if ! source_paths="$(cfg_lines shell_source_paths)"; then
  echo "cannot read [shell].source_paths from borromeanrings.toml — failing closed" >"$log"
  emit_receipt "$id" "$cmd" 1 "$log" "fail"
  exit 1
fi
if ! excludes="$(cfg_lines shell_exclude)"; then
  echo "cannot read [shell].exclude from borromeanrings.toml — failing closed" >"$log"
  emit_receipt "$id" "$cmd" 1 "$log" "fail"
  exit 1
fi

flags=()
while IFS= read -r value; do
  [ -n "$value" ] && flags+=("-P" "$value")
done <<<"$source_paths"
while IFS= read -r value; do
  [ -n "$value" ] && flags+=("-e" "$value")
done <<<"$excludes"

# Deliberately NOT xargs: on a long file list xargs splits into several invocations and
# reports only the LAST exit code, silently dropping findings from earlier batches — a
# fail-open hole in gate plumbing. One invocation, one exit code.
mapfile -t filelist <<<"$files"
count="${#filelist[@]}"

# Through the shared bounded runner (like every other tool-wrapping check) so a hung
# tool fails closed instead of hanging the gate. printf %q quotes every argument, so
# paths containing spaces survive the command-string round trip.
# (Careful: a comment line starting with the linter's own name parses as a directive.)
argv="$(printf '%q ' "${flags[@]}" "${filelist[@]}")"
borromeanrings_run_bounded "$log" "shellcheck -x -f gcc $argv"
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
