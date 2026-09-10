#!/usr/bin/env bash
# 27_properties — TIER 1 of the verification ladder: run the property suite a project
# declares, and hold it to a BINARY, THRESHOLD-FREE rule.
#
# Nothing declared ⇒ noop (rule off). Declared but empty ⇒ FAIL: a verification claim
# with no evidence behind it is exactly the vacuity ADR-0049 exists to catch, and
# [verification] has no defaults, so writing the key is an affirmative claim. Runner
# absent ⇒ noop NAMING it (borromeanRings never installs a project's toolchain — the
# rule the TypeScript/Go lanes set, #67/ADR-0068). A falsified property ⇒ FAIL.
#
# The check never counts properties, never ratchets on how many exist, and never
# targets a number of examples (ADR-0022's reasoning, one rung up): the file probe is
# `find -print -quit`, so it cannot see a count even by accident. It also does not
# decide what "a property" is — the project's declaration does.
# See docs/specs/SPEC-verification-ladder.md, ADR-0074.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="27_properties"
log="$RECEIPT_DIR/$id.log"
cmd="property tests (pytest + Hypothesis over [verification].properties)"

# --- 1. What does the project claim? A config that will not load is a FAIL, never a
# silent "nothing declared" (that would switch the rule off by accident). ------------
props="$(
  PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_ROOT/borromeanrings.toml" 2>"$log" <<'PY'
import sys

from meta_harness.spine import load_config

print(load_config(sys.argv[1]).verification_properties)
PY
)"
if [ $? -ne 0 ]; then
  echo "could not read [verification] from borromeanrings.toml (error above) — failing closed." >>"$log"
  emit_receipt "$id" "$cmd" 1 "$log" "fail"
  exit 1
fi

if [ -z "$props" ]; then
  echo "no [verification].properties declared — the property tier is OFF for this project." >"$log"
  echo "Nothing was claimed and nothing was inspected. Declare a directory to opt in." >>"$log"
  emit_noop "$id" "$cmd" "$log"
  exit 0
fi

# --- 2. Everything decidable WITHOUT a runner is decided first, so a missing tool can
# never mask a broken claim. ---------------------------------------------------------
props_dir="$PROJECT_ROOT/$props"
if [ ! -d "$props_dir" ]; then
  {
    echo "VACUOUS VERIFICATION CLAIM: [verification].properties = '$props' is not a directory."
    echo "A declared property suite that does not exist is a claim with no evidence behind it."
    echo "Fix: create it and write the first property, or remove the declaration (opt-out is fine)."
  } >"$log"
  emit_receipt "$id" "$cmd" 1 "$log" "fail"
  exit 1
fi

# -print -quit: stops at the FIRST match. This check is structurally unable to count.
if [ -z "$(find "$props_dir" -type f \( -name 'test_*.py' -o -name '*_test.py' \) -print -quit 2>/dev/null)" ]; then
  {
    echo "VACUOUS VERIFICATION CLAIM: '$props' holds no property tests (test_*.py / *_test.py)."
    echo "A declared-but-empty suite would otherwise report green forever on a promise."
    echo "Fix: write the first property there, or remove the declaration (opt-out is fine)."
  } >"$log"
  emit_receipt "$id" "$cmd" 1 "$log" "fail"
  exit 1
fi

# --- 3. Is the runner here? Never installed; named when absent. ----------------------
absent="$(
  cd "$PROJECT_ROOT" && python3 - <<'PY'
missing = []
for name in ("pytest", "hypothesis"):
    try:
        __import__(name)
    except Exception:  # ImportError, or a broken install that raises on import
        missing.append(name)
print(", ".join(missing))
PY
)"
if [ $? -ne 0 ]; then
  echo "could not probe for the property runner — failing closed." >"$log"
  emit_receipt "$id" "$cmd" 1 "$log" "fail"
  exit 1
fi

if [ -n "$absent" ]; then
  {
    echo "property runner not importable: $absent"
    echo "'$props' was NOT run — borromeanRings does not install a project's toolchain."
    echo "Install the runner (e.g. pip install hypothesis pytest) to make this lane real."
  } >"$log"
  emit_noop "$id" "$cmd" "$log"
  exit 0
fi

# --- 4. Run them. `exec` so pytest is the timeout's direct child (see _lib.sh);
# no cacheprovider so the gate leaves no .pytest_cache in the governed project. -------
borromeanrings_run_bounded "$log" "exec python3 -m pytest -q -p no:cacheprovider \"$props\""
code=$?

# pytest exit 5 = "no tests collected": files that look like tests but hold none. Same
# vacuity as an empty directory, caught one layer later.
if [ "$code" -eq 5 ]; then
  {
    echo ""
    echo "VACUOUS VERIFICATION CLAIM: '$props' has test files but pytest collected no tests."
    echo "Fix: write the first property there, or remove the declaration (opt-out is fine)."
  } >>"$log"
  code=1
fi

status="fail"
if [ "$code" -eq 0 ]; then
  status="pass"
else
  {
    echo ""
    echo "PROPERTY FAILED: a declared property does not hold (counterexample above)."
    echo "Fix the code, or fix the property if the property is what is wrong."
  } >>"$log"
fi

extra="$(python3 -c "import json,sys; print(json.dumps({'properties_dir': sys.argv[1]}))" "$props" 2>/dev/null || echo '')"
emit_receipt "$id" "$cmd" "$code" "$log" "$status" "$extra"
exit "$code"
