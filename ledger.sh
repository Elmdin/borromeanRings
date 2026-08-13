#!/usr/bin/env bash
# borromeanRings — EFFECTIVENESS LEDGER.
#
# `status.sh` shows whether each governed project is green *now*; this shows whether the
# gate has actually *done anything* over time — per project: how many times it ran, how
# many of those runs caught a failure (the gate is load-bearing, not decorative), and
# the current pass/fail streak. Reads the append-only verdict history verify.sh records
# in each project's .meta-harness/. Read-only; always exits 0. Threshold-free (counts +
# a streak, no score). See SPEC-ledger.md, ADR-0047.
#
# Usage: ./ledger.sh [PATH ...]     # roots to scan (default: $HOME)
set -uo pipefail

BORROMEANRINGS_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export BORROMEANRINGS_HOME
PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 -c \
  'import sys; from meta_harness.ledger import main; sys.exit(main(sys.argv[1:]))' "$@"
