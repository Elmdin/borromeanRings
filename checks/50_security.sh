#!/usr/bin/env bash
# Security: no bandit findings at/above the configured severity in src.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"
run_check "50_security" "bandit" "bandit -q -r src"
