#!/usr/bin/env bash
# borromeanRings — the ONLY way the gate starts Python. Sourced, never executed.
#
# The gate runs each check with the GOVERNED project as its working directory, and
# `python3 -c` / `python3 -` put the working directory FIRST on sys.path. A json.py
# (or a meta_harness/ package) planted at the project root would then be imported in
# place of the real module. #222 reproduced exactly this against the CI command: a
# root-level json.py that prints "  RESULT: PASS" when invoked as verify.sh's verdict
# step makes `bash verify.sh` exit 0 on a genuinely failing tree — forging the `gate`
# check CI requires. The same shadowing lets any receipt-writing / config-reading
# step be replaced by attacker code.
#
# borromeanrings_py [python3 args...] is therefore the only way the gate starts
# Python for a TRUSTED (verdict-deciding) step: it changes to `/` first (root-owned,
# so nothing can be planted there) and sets PYTHONPATH to borromeanRings's own src,
# which is how the gate finds meta_harness. Callers pass every project path as an
# absolute argument (they already do), so the `cd /` never loses a path.
#
# `cd /` closes the working-directory (project-root) shadow completely, on every
# supported Python. It does NOT by itself isolate the interpreter from *site startup
# hooks*: a usercustomize.py in the gate-running user's site-packages runs at startup
# and is on sys.path even after `cd /` (#224 review S1 forged a verdict that way). So
# also set PYTHONNOUSERSITE=1, which suppresses user-site (and usercustomize) WITHOUT
# dropping PYTHONPATH — the reason -I is unacceptable here. meta_harness resolves from
# PYTHONPATH, never user-site, so this loses nothing the gate needs.
#
# Do NOT "simplify" this with the interpreter's -P or -I flag. -P exists only from
# Python 3.11, and requires-python is 3.10 (#223), where it is an unknown option; CI
# runs 3.12 only, so the break would be invisible. -I also discards PYTHONPATH, which
# is how meta_harness is found. This mirrors .claude/hooks/_lib.sh's borromeanrings_py,
# added by #221 for the substrate hooks; #222 applies the same technique to the gate.
#
# Tool runs that execute the project's OWN code by design (pytest, mypy, mutmut,
# pip-audit, pip-licenses; and the `import <package>` half of 00_build) are NOT routed
# through this: they must run from the project and are already-untrusted (a conftest.py
# can forge their output regardless of cwd — see #218 and the M7 milestone). The
# stdlib-only compileall step of 00_build IS routed — it takes a path argument and
# never imports project code, so it closes cleanly here.
: "${BORROMEANRINGS_HOME:?_py.sh: BORROMEANRINGS_HOME must be exported before sourcing}"

borromeanrings_py() {
  (cd / && PYTHONNOUSERSITE=1 PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 "$@")
}
