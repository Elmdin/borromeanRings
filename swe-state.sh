#!/usr/bin/env bash
# borromeanRings — SWE STATE: what THIS project practises, lacks, and should adopt next.
#
# `status.sh` says whether the gate is green; `ledger.sh` says whether it caught anything.
# This says what the project should be doing that it is not — from facts already on disk
# (borromeanrings.toml, the last verdict, the archetype evaluation, adopt.sh's recommended
# set, the governance matrices' "Enforced by" column). Categorical only: no score, no
# percentage, one fixed adoption order. Says `unknown` / `unreadable` / "no matrices on
# disk" where it cannot tell. Advisory, read-only, always exits 0 (#139, ADR-0067).
#
# Usage:
#   ./swe-state.sh                  # plain-text report for THIS project
#   ./swe-state.sh --json           # machine-readable
#   ./swe-state.sh --matrices DIR   # matrices to map (default: $BORROMEANRINGS_HOME/docs/matrices)
set -uo pipefail

BORROMEANRINGS_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${BORROMEANRINGS_PROJECT:-${CLAUDE_PROJECT_DIR:-$PWD}}"
# A hint that does not exist stays the hint (reported as NOT GOVERNED) — never silently
# swapped for $PWD, which would describe a different project than the one asked about.
PROJECT_ROOT="$(cd "$PROJECT_ROOT" 2>/dev/null && pwd)" || true
PROJECT_ROOT="${PROJECT_ROOT:-${BORROMEANRINGS_PROJECT:-${CLAUDE_PROJECT_DIR:-$PWD}}}"
MATRICES_DIR="$BORROMEANRINGS_HOME/docs/matrices"
JSON=0
while [ $# -gt 0 ]; do
  case "$1" in
    --json) JSON=1 ;;
    --matrices) shift; MATRICES_DIR="${1:-}" ;;
    *) echo "swe-state.sh: unknown argument '$1'" >&2 ;;
  esac
  shift
done
export BORROMEANRINGS_HOME PROJECT_ROOT

# The composition root (same shape as every check script): read the facts, hand them to
# the pure core. Every read is fail-soft — an unreadable input is REPORTED as such by the
# core, never guessed around and never a crash. The core's fan-out stays at the coupling
# baseline because the stitching happens here, not in a Python module.
PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_ROOT" "$MATRICES_DIR" "$JSON" <<'PY'
import sys
from pathlib import Path

from meta_harness.adopt import RATCHET_BASELINES
from meta_harness.archetypes import evaluate, required_features
from meta_harness.spine import load_config
from meta_harness.status import find_enclosing_project
from meta_harness.swe_state import FeatureFact, assess, parse_matrices, render, to_json
from meta_harness.verdict import LAST_VERDICT_FILE, read_last_verdict

hint, matrices_dir, as_json = sys.argv[1], Path(sys.argv[2]), sys.argv[3] == "1"
project = find_enclosing_project(hint)
if project is None:
    print(f"NOT GOVERNED — no borromeanrings.toml in {hint} (adopt it: init.sh)")
    sys.exit(0)

unreadable: list[str] = []
required: tuple[str, ...] = ()
archetypes: tuple[str, ...] = ()
try:
    cfg = load_config(project / "borromeanrings.toml")
    required, archetypes = cfg.required_checks + cfg.heavy_checks, cfg.archetypes
except (OSError, ValueError):
    unreadable.append("config")

verdict = read_last_verdict(project)
if verdict is None and (project / LAST_VERDICT_FILE).exists():
    unreadable.append("verdict")

features: list[FeatureFact] = []
if archetypes:
    try:
        why = {f.id: f.why for f in required_features(archetypes)}
        features = [
            FeatureFact(r.feature_id, r.title, r.present, why.get(r.feature_id, ""))
            for r in evaluate(project, archetypes).results
        ]
    except (OSError, ValueError):
        unreadable.append("archetypes")

matrix_rows = None
files = sorted(matrices_dir.glob("0*-*.md")) if matrices_dir.is_dir() else []
if files:
    try:
        matrix_rows = parse_matrices({f.name: f.read_text(encoding="utf-8") for f in files})
    except OSError:
        unreadable.append("matrices")

state = assess(
    project=str(project),
    required=required,
    verdict=verdict,
    archetypes=archetypes,
    features=features,
    has_changelog=(project / "CHANGELOG.md").exists(),
    baseline_files_present=[b for b in RATCHET_BASELINES.values() if (project / b).exists()],
    matrix_rows=matrix_rows,
    unreadable=unreadable,
)
sys.stdout.write(to_json(state) if as_json else render(state))
PY
exit 0
