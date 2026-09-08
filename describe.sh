#!/usr/bin/env bash
# borromeanRings — DESCRIBE: what this harness is, generated from what is on disk.
#
# Every AI summary of this project used to list six to eight gates. This prints the real
# surface -- every check in the registry, which are required here, the ratchets, the
# governance matrices, the commands, the skills -- with every fact traceable to a file.
# Nothing here is hand-written prose (ADR-0052). Advisory, read-only, always exits 0.
#
# Usage:
#   ./describe.sh            # Markdown report for THIS project
#   ./describe.sh --json     # machine-readable
#   ./describe.sh --readme   # regenerate the README's describe block in place
set -uo pipefail

BORROMEANRINGS_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${BORROMEANRINGS_PROJECT:-${CLAUDE_PROJECT_DIR:-$PWD}}"
PROJECT_ROOT="$(cd "$PROJECT_ROOT" 2>/dev/null && pwd)" || PROJECT_ROOT="$BORROMEANRINGS_HOME"
export BORROMEANRINGS_HOME PROJECT_ROOT
PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 -c \
  'import sys; from meta_harness.describe import main; sys.exit(main(sys.argv[1:]))' "$@"
