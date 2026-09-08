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
import subprocess  # nosec B404 — fixed argv, no shell; only queries git
import sys
from pathlib import Path

from meta_harness.accessibility import a11y_findings
from meta_harness.source_coherence import walk_sources
from meta_harness.spine import load_config

cfg = load_config(sys.argv[1])
root = Path(sys.argv[2])


SUFFIXES = (".html", ".htm", ".xhtml")
EXCLUDE = tuple(cfg.a11y_exclude)


def _excluded(rel: str) -> bool:
    """Configured build-output / vendored dirs ([a11y].exclude), any path segment."""
    return any(seg in EXCLUDE for seg in rel.split("/"))


def _git(*argv: str) -> "subprocess.CompletedProcess[str] | None":
    """Run a fixed git query; None when git itself is unavailable."""
    try:
        return subprocess.run(  # nosec B603 B607 — fixed argv, no shell
            ["git", "-C", str(root), *argv],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None


def _html_files() -> tuple[list[str], str]:
    """The project's HTML plus a one-line description of HOW it was found.

    Mirrors 01_source_coherence's `_tracked_sources`: git-tracked files when this is a
    repo; a bounded filesystem walk only when it genuinely is NOT one. A git *failure*
    inside a real repo must not collapse into "no HTML" — that would turn violating HTML
    into a green `noop` — so it fails closed and says so (ADR-0042, ADR-0049).
    """
    listed = _git("ls-files", *[f"*{s}" for s in SUFFIXES])
    if listed is not None and listed.returncode == 0:
        files = [rel for rel in listed.stdout.splitlines() if not _excluded(rel)]
        return sorted(files), "git-tracked"

    is_repo = _git("rev-parse", "--git-dir")
    if is_repo is not None and is_repo.returncode == 0:
        print("git is present and this is a repository, but `git ls-files` failed —")
        print("cannot tell 'no HTML' from 'could not list HTML'; failing closed.")
        sys.exit(1)

    # Genuinely not a git repo (or git absent): bounded walk, pruning vendored trees.
    found: list[str] = []
    for suffix in SUFFIXES:
        found.extend(rel for rel in walk_sources(root, suffix) if not _excluded(rel))
    return sorted(found), "filesystem walk (not a git repository)"


files, how = _html_files()
if not files:
    # Inspected nothing: say so (exit 3 → `noop`), and say what was searched and where,
    # so a reader can tell "not a UI project" from "the HTML lives in an excluded dir".
    print(f"no HTML found — searched {how} *.html/*.htm/*.xhtml under {root}")
    print(f"(excluding directories: {', '.join(EXCLUDE) or 'none'})")
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
