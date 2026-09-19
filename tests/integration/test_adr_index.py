"""docs/adr/README.md must list every ADR (and nothing that is not one).

The index stopped being updated after ADR-0021: by 2026-09-19 it listed 24 of 84, so the
place a reader is told to start was missing most of the decisions. A registry mirror only
stays true if something checks it, like the README's check counts.
"""

import re
from pathlib import Path

ADR_DIR = Path(__file__).resolve().parents[2] / "docs" / "adr"
ROW = re.compile(r"^\| \[(\d{4})\]\(([^)]+)\) \|", re.M)


def test_every_adr_file_is_listed_once_and_every_row_resolves() -> None:
    files = {p.name[:4]: p.name for p in ADR_DIR.glob("[0-9][0-9][0-9][0-9]-*.md")}
    assert len(files) > 50, "the ADR directory was not found; this test would be vacuous"
    rows = ROW.findall((ADR_DIR / "README.md").read_text(encoding="utf-8"))
    listed = [num for num, _ in rows]

    missing = sorted(set(files) - set(listed))
    assert not missing, f"ADRs not in docs/adr/README.md: {missing}"
    repeated = sorted({n for n in listed if listed.count(n) > 1})
    assert not repeated, f"listed more than once: {repeated}"
    broken = sorted(f"{num} -> {link}" for num, link in rows if files.get(num) != link)
    assert not broken, f"rows whose link is not the ADR's file: {broken}"
