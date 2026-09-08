#!/usr/bin/env bash
# 15_a11y — static accessibility (a11y) invariants for the project's HTML: the
# Product/UX slice of the SWE matrix (#6). Enforces (per [a11y].require) the
# high-confidence, deterministic facts a screen-reader user is blocked by and that
# need no rendered DOM: a full document declares <html lang>, every <img> carries an
# alt, and a full document has a non-empty <title>. Native (stdlib html.parser; no
# axe-core/node). Threshold-free — presence facts only, no score target. No tracked
# HTML ⇒ `noop` (not a UI project: legitimate, but never a green that claims a11y was
# inspected — ADR-0049). Off unless 15_a11y is in [checks].required.
# See SPEC-accessibility.md, ADR-0045, ADR-0049.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="15_a11y"
log="$RECEIPT_DIR/$id.log"
cmd="static a11y invariants (html lang, img alt, page title per [a11y].require)"

PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_ROOT/borromeanrings.toml" "$PROJECT_ROOT" >"$log" 2>&1 <<'PY'
import subprocess
import sys
from pathlib import Path

from meta_harness.accessibility import a11y_findings
from meta_harness.spine import load_config

cfg = load_config(sys.argv[1])
root = Path(sys.argv[2])


def _tracked_html() -> list[str]:
    """Tracked *.html/*.htm, minus configured build-output / vendored dirs."""
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", "*.html", "*.htm", "*.xhtml"],
        capture_output=True,
        text=True,
        check=False,
    )
    excl = tuple(cfg.a11y_exclude)
    files = []
    for rel in out.stdout.splitlines():
        parts = rel.split("/")
        if any(seg in excl for seg in parts):
            continue
        files.append(rel)
    return sorted(files)


files = _tracked_html()
if not files:
    # Inspected nothing: say so (exit 3 → `noop`), and say what was searched and where,
    # so a reader can tell "not a UI project" from "the HTML lives in an excluded dir".
    print(f"no tracked HTML — searched git-tracked *.html/*.htm/*.xhtml under {root}")
    print(f"(excluding directories: {', '.join(cfg.a11y_exclude) or 'none'})")
    print("not a UI project, nothing to check — reporting noop, not pass")
    sys.exit(3)

total = 0
for rel in files:
    try:
        html = (root / rel).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:  # pragma: no cover - defensive
        print(f"  ! could not read {rel}: {exc}")
        continue
    findings = a11y_findings(html, require=cfg.a11y_require)
    for f in findings:
        total += 1
        print(f"  - {rel}: [{f.rule}] {f.message}")

if total:
    print(f"\nACCESSIBILITY — {total} issue(s) across {len(files)} HTML file(s).")
    print("Fix the markup, or narrow [a11y].require for this project.")
    sys.exit(1)
print(f"a11y invariants satisfied ({', '.join(cfg.a11y_require)}) across {len(files)} HTML file(s)")
PY
code=$?
status="$(borromeanrings_status_for_code "$code")"
[ "$status" = "noop" ] && code=0
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
