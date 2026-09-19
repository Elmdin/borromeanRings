#!/usr/bin/env bash
# 21_archetype — application-archetype required features: what an app OF ITS KIND must
# have, beyond code quality. [project].archetypes (library, cli, web-api, web-app, ml,
# embedded, data-pipeline) selects a catalog of binary, deterministic features — a health
# route declared, structured logging configured, a MODEL_CARD.md present, a rollback
# command declared, an i18n catalog present, … — each decided from files/config only
# (presence or a content regex; no model, no network, no build). Fails closed listing
# every absent feature with its evidence hint. The archetypes' `must_be_non_noop` checks
# are enforced separately, in verify.sh's verdict. No archetypes declared ⇒ noop (rule
# off). Off unless 21_archetype is in [checks].required. See SPEC-archetypes.md, ADR-0062.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="21_archetype"
log="$RECEIPT_DIR/$id.log"
cmd="archetype required features (per [project].archetypes; catalog in meta_harness.archetypes)"

PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_ROOT/borromeanrings.toml" "$PROJECT_ROOT" >"$log" 2>&1 <<'PY'
import sys

from meta_harness.archetypes import evaluate, render_report
from meta_harness.spine import load_config

cfg = load_config(sys.argv[1])
if not cfg.archetypes:
    print("no [project].archetypes declared — archetype rule off, nothing to check")
    sys.exit(3)  # BORROMEANRINGS_NOOP_EXIT: inspected nothing (ADR-0049)

report = evaluate(sys.argv[2], cfg.archetypes)
print(render_report(report), end="")
missing = [r for r in report.results if not r.present]
if missing:
    print("\nARCHETYPE FEATURES MISSING — add each, or drop the archetype from [project].archetypes:")
    for r in missing:
        print(f"  - {r.feature_id}: {r.title}")
    sys.exit(1)
PY
code=$?
status="$(borromeanrings_status_for_code "$code")"
[ "$status" = "noop" ] && code=0
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
