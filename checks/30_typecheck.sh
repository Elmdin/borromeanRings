#!/usr/bin/env bash
# Typecheck: no type errors (mypy strict, per pyproject.toml).
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"
run_check "30_typecheck" "mypy" "mypy src"
