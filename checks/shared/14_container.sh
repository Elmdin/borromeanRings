#!/usr/bin/env bash
# 14_container — container (Dockerfile) hygiene: the operational invariants no code
# check covers. Enforces (per [container].require) that the image runs non-root
# (least privilege), pins its base (reproducible builds, not `:latest`), and — for a
# service — declares a HEALTHCHECK. The buildable, threshold-free slice of matrix #4
# (SRE). Native (stdlib Dockerfile parse; no docker/hadolint). No Dockerfile at the
# declared path ⇒ pass (not a container project). Off unless 14_container is in
# [checks].required. See SPEC-container.md, ADR-0044.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="14_container"
log="$RECEIPT_DIR/$id.log"
cmd="container hygiene (non-root, pinned base, healthcheck per [container].require)"

# Resolve the Dockerfile path from config (default "Dockerfile"), relative to root.
dockerfile_rel="$(
  PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_ROOT/borromeanrings.toml" 2>/dev/null <<'PY'
import sys
from meta_harness.spine import load_config
print(load_config(sys.argv[1]).container_dockerfile)
PY
)"
[ -n "$dockerfile_rel" ] || dockerfile_rel="Dockerfile"
dockerfile_path="$PROJECT_ROOT/$dockerfile_rel"

if [ ! -f "$dockerfile_path" ]; then
  echo "no Dockerfile at '$dockerfile_rel' — not a container project, nothing to check" >"$log"
  emit_receipt "$id" "$cmd" 0 "$log" "pass"
  exit 0
fi

PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_ROOT/borromeanrings.toml" "$dockerfile_path" >"$log" 2>&1 <<'PY'
import sys

from meta_harness.container import hygiene_findings
from meta_harness.spine import load_config

cfg = load_config(sys.argv[1])
with open(sys.argv[2], encoding="utf-8") as fh:
    text = fh.read()

findings = hygiene_findings(text, require=cfg.container_require)
if findings:
    print(f"CONTAINER HYGIENE — {len(findings)} issue(s) in the Dockerfile:")
    for f in findings:
        print(f"  - [{f.rule}] {f.message}")
    print("Fix the Dockerfile, or narrow [container].require for this project's role.")
    sys.exit(1)
print(f"container hygiene satisfied ({', '.join(cfg.container_require)})")
PY
code=$?
status="fail"
[ "$code" -eq 0 ] && status="pass"
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
