#!/usr/bin/env bash
# borromeanRings — ADVISE: the right approaches and the right questions, before building.
#
# The gate says whether a change was built right; this says, from facts already on disk,
# which engineering approach fits THIS change and which questions the agent should ask
# the human before proceeding. Every line is a deterministic rule keyed on the declared
# archetypes, the last verdict's failing/hollow checks, the SWE-state lacks, the branch
# and its diff, and whether enforcement is on — each citing the check, SPEC or ADR it
# comes from. No model, no score, no ranking beyond one fixed order (questions, then
# approaches, each in catalog order). Advisory, read-only, always exits 0 (#32, ADR-0072).
#
# Usage:
#   ./advise.sh          # plain-text advice for THIS project
#   ./advise.sh --json   # machine-readable
set -uo pipefail

BORROMEANRINGS_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${BORROMEANRINGS_PROJECT:-${CLAUDE_PROJECT_DIR:-$PWD}}"
# A hint that does not exist stays the hint (reported as NOT GOVERNED) — never silently
# swapped for $PWD, which would describe a different project than the one asked about.
PROJECT_ROOT="$(cd "$PROJECT_ROOT" 2>/dev/null && pwd)" || true
PROJECT_ROOT="${PROJECT_ROOT:-${BORROMEANRINGS_PROJECT:-${CLAUDE_PROJECT_DIR:-$PWD}}}"
JSON=0
while [ $# -gt 0 ]; do
  case "$1" in
    --json) JSON=1 ;;
    *) echo "advise.sh: unknown argument '$1'" >&2 ;;
  esac
  shift
done
export BORROMEANRINGS_HOME PROJECT_ROOT


# The composition root (same shape as swe-state.sh): read the facts, hand them to the pure
# core. Every read is fail-soft — an unreadable input becomes a QUESTION from the core,
# never a guess and never a crash. The core's fan-out stays at the coupling baseline
# because the stitching happens here, not in a Python module.
PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_ROOT" "$JSON" <<'PY'
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

#: Directories whose churn is never "the change": borromeanRings's own evidence area.
SKIP_PREFIXES = (".meta-harness/",)


def git(project, *argv):
    """``git`` stdout, or ``""`` on any failure (not a repo, no base, git absent)."""
    try:
        done = subprocess.run(
            ["git", "-C", str(project), *argv], capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def git_facts(project):
    """``(branch, changed)`` for the governed project — the branch and what it changed.

    The diff base is resolved the way 13_adr resolves it (origin/dev → dev → origin/main
    → main); the changed set is the tree against that merge-base plus untracked files, so
    uncommitted work counts. Not a repo ⇒ ``("", ())``.
    """
    branch = git(project, "rev-parse", "--abbrev-ref", "HEAD")
    if not branch:
        return "", ()
    merge_base = ""
    for candidate in ("origin/dev", "dev", "origin/main", "main"):
        if git(project, "rev-parse", "--verify", "-q", candidate):
            merge_base = git(project, "merge-base", "HEAD", candidate)
            break
    diff_from = [merge_base] if merge_base else ["HEAD"]
    changed = set(git(project, "diff", "--relative", "--name-only", *diff_from).splitlines())
    changed |= set(git(project, "ls-files", "--others", "--exclude-standard").splitlines())
    return branch, tuple(
        sorted(p for p in changed if p and not p.startswith(SKIP_PREFIXES))
    )

from meta_harness.adopt import RATCHET_BASELINES
from meta_harness.advisor import FeatureGap, advise, gather_facts, render, to_json
from meta_harness.archetypes import evaluate, required_features
from meta_harness.spine import load_config
from meta_harness.status import find_enclosing_project
from meta_harness.status_assess import classify_enforcement
from meta_harness.verdict import LAST_VERDICT_FILE, read_last_verdict

hint, as_json = sys.argv[1], sys.argv[2] == "1"
project = find_enclosing_project(hint)
if project is None:
    print(f"NOT GOVERNED — no borromeanrings.toml in {hint} (adopt it: init.sh)")
    sys.exit(0)

unreadable: list[str] = []
required: tuple[str, ...] = ()
archetypes: tuple[str, ...] = ()
src_dir, tests_dir = "src", "tests"
branch_patterns_declared = changelog_entry_on_src = False
adr_prefixes: tuple[str, ...] = ()
try:
    cfg = load_config(project / "borromeanrings.toml")
    required, archetypes = cfg.required_checks + cfg.heavy_checks, cfg.archetypes
    src_dir, tests_dir = cfg.src_dir, cfg.tests_dir
    # What is actually in force here, from the same spine the checks themselves read: a
    # rule may only claim a check will fail when that check's own rule is switched on.
    branch_patterns_declared = bool(cfg.collaboration_branch_patterns)
    changelog_entry_on_src = cfg.changelog_enabled and cfg.changelog_require_entry_on_src_change
    adr_prefixes = cfg.adr_require_prefixes
except (OSError, ValueError):
    unreadable.append("config")

# [charter] is read raw because the spine does not model it on this base ("when present").
stakes = reviewer = ""
try:
    charter = tomllib.loads((project / "borromeanrings.toml").read_text(encoding="utf-8")).get(
        "charter", {}
    )
    stakes, reviewer = str(charter.get("stakes", "")), str(charter.get("reviewer", ""))
except (OSError, ValueError):
    pass

verdict = read_last_verdict(project)
if verdict is None and (project / LAST_VERDICT_FILE).exists():
    unreadable.append("verdict")

features: list[FeatureGap] = []
if archetypes:
    try:
        why = {f.id: f.why for f in required_features(archetypes)}
        features = [
            FeatureGap(r.feature_id, r.title, why.get(r.feature_id, ""))
            for r in evaluate(project, archetypes).results
            if not r.present
        ]
    except (OSError, ValueError):
        unreadable.append("archetypes")

settings = None
settings_path = project / ".claude" / "settings.json"
if settings_path.exists():
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        settings = None
enforcement = classify_enforcement(settings, os.environ["BORROMEANRINGS_HOME"]).mode
branch, changed = git_facts(project)

facts = gather_facts(
    project=str(project),
    required=required,
    verdict=verdict,
    archetypes=archetypes,
    features_absent=features,
    has_changelog=(project / "CHANGELOG.md").exists(),
    baseline_files_present=[b for b in RATCHET_BASELINES.values() if (project / b).exists()],
    branch=branch,
    changed=changed,
    src_dir=src_dir,
    tests_dir=tests_dir,
    branch_patterns_declared=branch_patterns_declared,
    changelog_entry_on_src=changelog_entry_on_src,
    adr_prefixes=adr_prefixes,
    enforcement=enforcement,
    stakes=stakes,
    reviewer=reviewer,
    unreadable=unreadable,
)
advice = advise(facts)
sys.stdout.write(to_json(advice) if as_json else render(advice))
PY
exit 0
