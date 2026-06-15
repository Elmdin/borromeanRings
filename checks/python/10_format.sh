#!/usr/bin/env bash
# Format: no unformatted files.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"
run_check "10_format" "ruff" "ruff format --check ."
