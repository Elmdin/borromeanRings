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
# Do NOT "simplify" this with the interpreter's -P or -I flag. -P exists only from
# Python 3.11, and requires-python is 3.10 (#223), where it is an unknown option; CI
# runs 3.12 only, so the break would be invisible. -I also discards PYTHONPATH, which
# is how meta_harness is found. This mirrors .claude/hooks/_lib.sh's borromeanrings_py,
# added by #221 for the substrate hooks; #222 applies the same technique to the gate.
#
# Tool runs that execute the project's OWN code by design (pytest, mypy, compileall,
# mutmut, pip-audit, pip-licenses) are deliberately NOT routed through this: they must
# run from the project and are already-untrusted (a conftest.py can forge their output
# regardless of cwd — see #218 and the M7 executor-isolation milestone).
: "${BORROMEANRINGS_HOME:?_py.sh: BORROMEANRINGS_HOME must be exported before sourcing}"

borromeanrings_py() {
  (cd / && PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 "$@")
}
