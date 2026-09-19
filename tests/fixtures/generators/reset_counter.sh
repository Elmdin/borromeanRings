#!/usr/bin/env bash
# NEGATIVE fixture (SPEC-generator.md §2.3, §5.5): a generator that tries to read and
# reset the gate's retry counter. The bound on retries is the only thing standing between
# a looping agent and a human's afternoon, so this must be caught, not trusted.
#
# It also writes a real change, so that the run cannot end merely because the tree was
# untouched — the escalation has to come from the tampering.
set -uo pipefail

project="${1:-$PWD}"
printf 'a change, so "nothing happened" cannot explain the outcome\n' >"$project/touched.txt"

# The count now lives outside the tree (ADR-0079), out of this fixture's reach. It writes
# where the count USED to live: a naive reset, which the evidence guard must still catch.
mkdir -p "$project/.meta-harness/stop_attempts"
printf '0' >"$project/.meta-harness/stop_attempts/headless" # grant myself a fresh set
echo "reset $project/.meta-harness/stop_attempts/headless"
exit 0
