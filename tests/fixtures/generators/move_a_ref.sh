#!/usr/bin/env bash
# DISCRIMINATING fixture: changes what the gate reads without touching a file, HEAD, the
# branch or the index. Six checks resolve their diff base by trying `origin/dev dev
# origin/main main` in turn, so creating or moving any of those refs moves what they read.
set -uo pipefail
project="${1:-$PWD}"
git -C "$project" update-ref refs/heads/main HEAD
