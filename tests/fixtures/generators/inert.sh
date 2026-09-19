#!/usr/bin/env bash
# DISCRIMINATING fixture: a generator that runs cleanly and writes nothing at all.
#
# It exists because the driver's own bookkeeping used to leak into the change detection:
# the capture of this script's stdout lived inside the gated tree, so on a project that
# does not gitignore .meta-harness/ the tree "changed" on every attempt and an inert
# generator was reported GREEN. See ADR-0078 and SPEC-generator.md N4.
set -uo pipefail
echo "I did nothing at all"
exit 0
