#!/usr/bin/env bash
# Build / installable: the project's source compiles and (if a package is declared) imports cleanly.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

src_dir="$(borromeo_project_cfg src_dir)"
package="$(borromeo_project_cfg package)"
cmd="python3 -m compileall -q $src_dir"
if [ -n "$package" ]; then
  cmd="$cmd && PYTHONPATH=$src_dir python3 -c \"import $package\""
fi
run_check "00_build" "python3" "$cmd"
