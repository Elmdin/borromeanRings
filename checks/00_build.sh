#!/usr/bin/env bash
# Build / installable: the package compiles and imports cleanly.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"
run_check "00_build" "python3" \
  'python3 -m compileall -q src && PYTHONPATH=src python3 -c "import meta_harness"'
