#!/usr/bin/env bash
# adopt.sh — migrate an EXISTING borromeanRings-governed project onto the newer
# quality/security checks. Adds the curated recommended set to [checks].required
# and seeds each ratchet's baseline from the project's CURRENT state, so the
# first gate run is green (a ratchet without a baseline is vacuous; seeded from
# current, it holds the line going forward). Idempotent, native, no installs.
#
#   ./adopt.sh <project-dir>     # defaults to the current directory
#
# Complements init.sh (which bootstraps a NEW project). Planning + the scoped
# TOML rewrite live in src/meta_harness/adopt.py. See SPEC-adopt.md, ADR-0041.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BORROMEANRINGS_HOME="$HERE"
PROJECT_DIR="${1:-$PWD}"
PROJECT_DIR="$(cd "$PROJECT_DIR" 2>/dev/null && pwd)" || {
  echo "adopt: no such directory: ${1:-$PWD}" >&2
  exit 1
}

if [ ! -f "$PROJECT_DIR/borromeanrings.toml" ]; then
  echo "adopt: $PROJECT_DIR is not borromeanRings-governed (no borromeanrings.toml)" >&2
  [ -f "$PROJECT_DIR/borromeo.toml" ] && echo "adopt: found legacy borromeo.toml — rename it first: git mv borromeo.toml borromeanrings.toml (docs/RENAME.md)" >&2
  echo "       run ./init.sh \"$PROJECT_DIR\" first to bootstrap it." >&2
  exit 1
fi

PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_DIR" "$BORROMEANRINGS_HOME" <<'PY'
import sys
from pathlib import Path

from meta_harness.adopt import RATCHET_BASELINES, plan_adoption, rewrite_required
from meta_harness.complexity import worst_complexity
from meta_harness.coupling import worst_fan_out
from meta_harness.docstrings import measure_package
from meta_harness.spine import load_config

CHANGELOG_TEMPLATE = """\
# Changelog

All notable changes to this project are documented here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- borromeanRings governance adopted: secret scanning, changelog discipline, and
  docstring / complexity / coupling ratchets (baselines seeded from current state).
"""

project = Path(sys.argv[1])
home = Path(sys.argv[2])
toml_path = project / "borromeanrings.toml"
config = load_config(toml_path)

changelog = project / (config.changelog_path or "CHANGELOG.md")
plan = plan_adoption(tuple(config.required_checks), has_changelog=changelog.exists())

if not plan.add_checks:
    print(f"adopt: {project.name} already has all recommended checks — nothing to do.")
    sys.exit(0)

src_root = project / config.src_dir
package = config.package

# Seed each newly-added ratchet's baseline from the project's current value. With
# no package to measure, the ratchet is greenfield-pass, so seeding is skipped.
seeders = {
    "32_complexity": lambda: str(worst_complexity(src_root, package)[0]),
    "33_coupling": lambda: str(worst_fan_out(src_root, package)[0]),
    "45_docstrings": lambda: f"{measure_package(src_root, package).coverage:.6f}",
}
seeded: list[str] = []
for check in plan.seed_baselines:
    if not package:
        continue
    value = seeders[check]()
    (project / RATCHET_BASELINES[check]).write_text(value + "\n", encoding="utf-8")
    seeded.append(f"{RATCHET_BASELINES[check]} = {value}")

if plan.needs_changelog:
    changelog.write_text(CHANGELOG_TEMPLATE, encoding="utf-8")

toml_path.write_text(
    rewrite_required(toml_path.read_text(encoding="utf-8"), plan.new_required),
    encoding="utf-8",
)

print(f"adopt: {project.name}: added {list(plan.add_checks)}")
for line in seeded:
    print(f"  seeded {line}")
if plan.needs_changelog:
    print(f"  created {changelog.name}")
print(f"  [checks].required is now {len(plan.new_required)} checks.")
print("  next: run the gate to confirm green:")
print(f'    BORROMEANRINGS_PROJECT="{project}" bash "{home}/verify.sh"')
PY

# Refresh borromeanRings's skills in the adopted project. init.sh installs these for NEW
# projects; without the same step here, an already-governed project would never receive a
# newly-added skill (e.g. borromeanrings-status) and could not self-report. Copy-only —
# it never edits the project's settings/hooks, which stay the owner's decision.
if [ -d "$BORROMEANRINGS_HOME/.claude/skills" ]; then
  mkdir -p "$PROJECT_DIR/.claude/skills"
  cp -R "$BORROMEANRINGS_HOME/.claude/skills/." "$PROJECT_DIR/.claude/skills/"
  echo "  refreshed borromeanRings skills in $PROJECT_DIR/.claude/skills/"
fi
