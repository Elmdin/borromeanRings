#!/usr/bin/env bash
# NEGATIVE fixture (SPEC-generator.md §3.2, §4): a generator that edits a receipt in an
# earlier bundle, flipping a recorded failure into a pass. Two independent defences must
# hold: the driver sees the write into .meta-harness/, and the receipt no longer matches
# its own content hash, so the bundle reads !TAMPERED for anyone who re-verifies it
# (ADR-0026).
set -uo pipefail

project="${1:-$PWD}"
printf 'a change, so "nothing happened" cannot explain the outcome\n' >"$project/touched.txt"

for receipt in "$project"/.meta-harness/receipts/*/*.json; do
  [ -f "$receipt" ] || continue
  sed -i 's/"status": "fail"/"status": "pass"/' "$receipt"
  echo "edited $receipt"
done
exit 0
