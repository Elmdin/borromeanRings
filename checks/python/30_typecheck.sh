#!/usr/bin/env bash
# Typecheck: no type errors in the project's source (mypy; configured in its pyproject.toml).
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"
run_check "30_typecheck" "mypy" "mypy $(borromeo_project_cfg src_dir)"
