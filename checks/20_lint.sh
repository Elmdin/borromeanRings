#!/usr/bin/env bash
# Lint: no lint violations.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"
run_check "20_lint" "ruff" "ruff check ."
