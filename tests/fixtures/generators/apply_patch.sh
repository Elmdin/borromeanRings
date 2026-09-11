#!/usr/bin/env bash
# Reference headless generator (SPEC-generator.md §3.2): on attempt N it applies
# patches/N.diff, and that is the whole of it. NO MODEL CALL, no key, no network — the
# point is a generator whose behaviour is fully determined by the fixture's patch files,
# so the generate -> gate -> retry -> escalate loop can be tested end to end.
#
# Invoked by generate.sh as:  apply_patch.sh <project_path> <last_verdict_path|"">
# with BORROMEANRINGS_{ATTEMPT,CAP,FAILING_CHECKS,GENERATOR} in the environment.
#
# What it deliberately does NOT do, because a generator may not (§4): run verify.sh,
# write under .meta-harness/, push, or count its own attempts. It reports what it was
# handed on stdout — the driver captures that, so a test can assert the loop delivered
# the verdict and the failing check ids (N1, N2) without the generator touching the tree
# to say so.
#
# Exit 0 + a changed tree  => "gate me".
# Exit 0 + unchanged tree  => "I have nothing to add" (a missing patch file).
# Non-zero                 => "I could not" (a malformed patch: git apply refuses).
set -uo pipefail

project="${1:-$PWD}"
last_verdict="${2:-}"
attempt="${BORROMEANRINGS_ATTEMPT:-1}"

echo "handed: attempt=$attempt cap=${BORROMEANRINGS_CAP:-} failing=[${BORROMEANRINGS_FAILING_CHECKS:-}]"
echo "handed: project=$project verdict=[$last_verdict] generator=${BORROMEANRINGS_GENERATOR:-}"
echo "handed: cwd=$PWD stdin=$( [ -t 0 ] && echo tty || echo not-a-tty )"

patch="$project/patches/$attempt.diff"
if [ ! -f "$patch" ]; then
  echo "no patch for attempt $attempt at $patch — nothing to write"
  exit 0
fi

# -c apply.whitespace=nowarn: the outcome must not depend on the machine's git config
# any more than it depends on the machine's git version.
git -C "$project" -c apply.whitespace=nowarn apply --verbose "$patch"
code=$?
if [ "$code" -ne 0 ]; then
  # OUR marker, on stderr, in OUR words. A test that asserts git's phrasing here
  # ("error: unrecognized input" on git 2.34, "error: No valid patches in input" on 2.55)
  # is asserting a git release, not the property it means — that the driver captures what
  # the generator wrote, on both streams. See ADR-0078.
  echo "apply_patch: git apply refused $patch (exit $code)" >&2
  exit "$code"
fi
echo "applied $patch"
