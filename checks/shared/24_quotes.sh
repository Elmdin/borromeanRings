#!/usr/bin/env bash
# Quote fidelity: every quotation a Markdown document marks with a source
# (`> ...` then `— source: path#L<a>-L<b>`, or `<!-- quote: path#L<a>-L<b> -->`) must be
# verbatim against the saved source span — the mechanism behind the research skill's
# fail-closed citation promise. Off unless [quotes].enabled; no marked quotation under
# [quotes].paths ⇒ noop; drifted / missing / out-of-range / orphan ⇒ fail, each listed
# with file:line; an unreadable document or source fails CLOSED. Language-agnostic,
# native, no network. See docs/specs/SPEC-quotes.md and ADR-0065.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="24_quotes"
log="$RECEIPT_DIR/$id.log"
cmd="quote fidelity (marked quotations verbatim vs saved sources)"

# Exit 3 ⇒ nothing to inspect (BORROMEANRINGS_NOOP_EXIT); 0 ⇒ all verbatim; 1 ⇒ a
# non-verbatim quotation, or a file that exists but cannot be read (fail closed).
PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - "$PROJECT_ROOT" "$BORROMEANRINGS_NOOP_EXIT" >"$log" 2>&1 <<'PY'
import sys
from pathlib import Path

from meta_harness.quotes import QuoteReport, QuoteResult, render, verify
from meta_harness.spine import load_config

root = Path(sys.argv[1])
noop_exit = int(sys.argv[2])
config = load_config(root / "borromeanrings.toml")

if not config.quotes_enabled:
    print("quote fidelity not enabled ([quotes].enabled=false) — rule off")
    sys.exit(0)


def resolve(rel: str) -> str | None:
    """The saved source's text, None when absent; a present-but-unreadable file raises."""
    file = root / rel
    if not file.is_file():
        return None
    return file.read_text(encoding="utf-8")


documents: list[Path] = []
for declared in config.quotes_paths:
    target = root / declared
    if target.is_file():
        documents.append(target)
    elif target.is_dir():
        documents.extend(sorted(p for p in target.rglob("*.md") if p.is_file()))
if not documents:
    print(f"no Markdown under [quotes].paths {list(config.quotes_paths)} — nothing to inspect")
    sys.exit(noop_exit)

results: list[QuoteResult] = []
for doc in documents:
    rel = doc.relative_to(root).as_posix()
    try:
        text = doc.read_text(encoding="utf-8")
        results.extend(verify(text, resolve, document=rel).results)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"UNREADABLE: {rel}: {exc} (failing closed)")
        sys.exit(1)

report = QuoteReport(results=tuple(results))
if report.is_empty:
    print(f"no marked quotations in {len(documents)} Markdown file(s) — nothing to inspect")
    sys.exit(noop_exit)
print(render(report))
if not report.ok:
    print("QUOTE FIDELITY: a marked quotation is not verbatim against its saved source")
    sys.exit(1)
PY
code=$?
if [ "$code" -eq "$BORROMEANRINGS_NOOP_EXIT" ]; then
  emit_noop "$id" "$cmd" "$log"
  exit 0
fi
status="$(borromeanrings_status_for_code "$code")"
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
