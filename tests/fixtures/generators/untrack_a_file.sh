#!/usr/bin/env bash
# DISCRIMINATING fixture: changes the INDEX only. 01_source_coherence, 12_secrets and
# 15_a11y enumerate files with `git ls-files`, not from the working tree, so untracking a
# file changes what they inspect while the file sits unchanged on disk — and a dirty-tree
# OID built with `git add -A` puts it straight back.
set -uo pipefail
project="${1:-$PWD}"
git -C "$project" rm --cached -q -- README.md
