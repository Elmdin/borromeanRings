#!/usr/bin/env bash
# DISCRIMINATING fixture: changes what the gate reads without touching a file, HEAD, the
# branch or the index. Six checks resolve their diff base by trying `origin/dev dev
# origin/main main` in turn, so creating or moving any of those refs changes what they read.
#
# It moves `refs/remotes/origin/dev` — the FIRST candidate in that list, and a ref no
# `git init` ever creates. It deliberately does not touch `refs/heads/main`: on a machine
# whose `init.defaultBranch` is `main` (increasingly the default) that ref already points
# at HEAD, so setting it to HEAD is a no-op and the fixture would silently prove nothing.
# Depending on another tool's default configuration is the same defect as depending on its
# error prose. See ADR-0078.
set -uo pipefail

project="${1:-$PWD}"
git -C "$project" update-ref refs/remotes/origin/dev HEAD
