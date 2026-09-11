#!/usr/bin/env bash
# DISCRIMINATING fixture: a generator that changes what git RECORDS but not what the
# working tree CONTAINS — it commits. The dirty-tree OID is identical afterwards; the
# branch-, head- and history-reading checks in the required set (08_branch, 09_commits,
# 11_changelog, 13_adr) are not looking at the same thing at all.
#
# It exists because SPEC-generator.md N3 said the driver compares the dirty-tree OID, and
# under that rule this generator is told it did nothing. See ADR-0078.
set -uo pipefail

project="${1:-$PWD}"
git -C "$project" -c user.name=fixture -c user.email=f@x \
  commit -q --allow-empty -m "chore: a commit that changes no file"
