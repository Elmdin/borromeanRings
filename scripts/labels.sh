#!/usr/bin/env bash
# labels.sh — bring GitHub's labels in line with docs/LABELS.md.
#
# RUN BY A HUMAN, ON PURPOSE. Labels are outward-facing repository state; no hook,
# check, or workflow invokes this. It is idempotent: `gh label create --force` creates
# a missing label and updates the colour/description of an existing one. It never
# deletes — retiring a label is a deliberate manual act.
#
# Usage:
#   scripts/labels.sh            apply (needs `gh auth status` to be logged in)
#   scripts/labels.sh --dry-run  print what would run; change nothing
#   REPO=owner/name scripts/labels.sh   target a different repository
#
# Keep the LABELS array below and the tables in docs/LABELS.md in step — same PR.
set -euo pipefail

REPO="${REPO:-3MagicLabs/borromeanRings}"
DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h | --help)
      sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "labels.sh: unknown argument '$arg' (try --dry-run or --help)" >&2
      exit 2
      ;;
  esac
done

# name|colour (no #)|description — one line per label, mirrors docs/LABELS.md.
LABELS=(
  # Type
  'harness-feature|5319E7|A borromeanRings meta-harness capability (usually a new check or command)'
  'bug|d73a4a|Does not do what it says it does — incl. a check that passes without inspecting anything'
  'quality|1d76db|Engineering rigor: tests, lint, verification'
  'security|b60205|Security hardening and vulnerability work (report vulnerabilities privately first)'
  'efficiency|fbca04|Token/compute cost reduction without losing output quality'
  'research|d4c5f9|Investigation and prior-art synthesis, producing a written decision'
  'evaluation|c5def5|Assess how the platform works and what to improve'
  'documentation|0075ca|Docs, specs, contributor material'
  'repo-setup|bfdadc|GitHub settings, repo hygiene, scaffolding'
  'deep-research|0E8A16|The deep-research enhancement (a harness feature, not the separate product)'
  'epic|3e4b9e|Tracking issue spanning multiple work items'
  # Priority
  'priority:high|d93f0b|Blocks a milestone, or a gate that can be trusted when it should not be'
  'priority:med|fbca04|Normal priority: real value, no one is blocked'
  'priority:low|c2e0c6|Nice to have: nothing breaks if it never happens'
  # Status
  'needs-triage|ededed|Filed via a form; not yet typed, prioritised, or milestoned'
  'needs-spec|fef2c0|Touches 3+ files: spec under docs/specs/ required before code'
  'needs-adr|fef2c0|Adds/removes a gate or changes the trust model: ADR required'
  'blocked|000000|Cannot proceed until a named issue/PR lands'
  # Scope and resolution
  'separate-product|BFD4F2|Belongs to a product built WITH borromeanRings, not the harness core'
  'duplicate|cfd3d7|This issue or pull request already exists'
  'wontfix|ffffff|This will not be worked on'
  'invalid|e4e669|Not actionable as written'
  # Community
  'good first issue|7057ff|Self-contained, gate-checkable, no trust-root code'
  'help wanted|008672|Maintainer would welcome an outside PR'
  'question|d876e3|Needs an answer, not a change'
  # Retained GitHub default (do not apply to new issues)
  'enhancement|a2eeef|GitHub default — prefer harness-feature; kept for existing issues'
)

if [ "$DRY_RUN" -eq 0 ] && ! command -v gh >/dev/null 2>&1; then
  echo "labels.sh: gh CLI not found on PATH" >&2
  exit 1
fi

applied=0
for entry in "${LABELS[@]}"; do
  IFS='|' read -r name colour description <<<"$entry"
  if [ -z "$name" ] || [ -z "$colour" ] || [ -z "$description" ]; then
    echo "labels.sh: malformed entry: $entry" >&2
    exit 1
  fi
  if ! [[ "$colour" =~ ^[0-9A-Fa-f]{6}$ ]]; then
    echo "labels.sh: bad colour '$colour' for '$name' (want 6 hex digits, no #)" >&2
    exit 1
  fi
  if [ "$DRY_RUN" -eq 1 ]; then
    printf 'gh label create %q --repo %q --force --color %q --description %q\n' \
      "$name" "$REPO" "$colour" "$description"
  else
    gh label create "$name" --repo "$REPO" --force --color "$colour" --description "$description"
  fi
  applied=$((applied + 1))
done

if [ "$DRY_RUN" -eq 1 ]; then
  echo "labels.sh: dry run — $applied label(s) would be created/updated on $REPO; nothing changed."
else
  echo "labels.sh: $applied label(s) created/updated on $REPO."
fi
