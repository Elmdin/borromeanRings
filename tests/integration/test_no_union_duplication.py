"""Repetition a union merge leaves behind must not reach dev unnoticed.

A conflict resolved by keeping BOTH sides is additive, and when both sides carry the
same block it comes back twice. Nothing in the gate notices, because repetition is valid
Python and valid Markdown. It happened on every merge of one campaign: verdict.py's
NON_FAILING_STATUSES block grew one copy per merge, to fifteen, and CHANGELOG.md
carried one entry six times under eight separate ``### Added`` headings. These tests
pin both shapes on this repository's own tree.
"""

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src" / "meta_harness"
CHANGELOG = REPO / "CHANGELOG.md"


def _module_level_assignments(tree: ast.Module) -> list[str]:
    names: list[str] = []
    for node in tree.body:
        targets = (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target]
            if isinstance(node, ast.AnnAssign) and node.value is not None
            else []
        )
        names += [t.id for t in targets if isinstance(t, ast.Name)]
    return names


def test_no_module_assigns_the_same_top_level_name_twice() -> None:
    offenders: list[str] = []
    modules = sorted(SRC.rglob("*.py"))
    assert len(modules) > 20, "the package was not found; this test would be vacuous"
    for path in modules:
        names = _module_level_assignments(ast.parse(path.read_text(encoding="utf-8")))
        offenders += [
            f"{path.relative_to(REPO)}: {name} assigned {names.count(name)} times"
            for name in sorted(set(names))
            if names.count(name) > 1
        ]
    assert not offenders, "\n".join(offenders)


def _version_sections(text: str) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    for line in text.split("\n"):
        if line.startswith("## "):
            sections.append((line, []))
        elif sections:
            sections[-1][1].append(line)
    return sections


def test_each_changelog_version_has_one_heading_per_change_type() -> None:
    sections = _version_sections(CHANGELOG.read_text(encoding="utf-8"))
    assert sections, "no version sections found; this test would be vacuous"
    offenders = []
    for version, lines in sections:
        headings = [line for line in lines if re.match(r"### \S", line)]
        offenders += [
            f"{version}: {h!r} appears {headings.count(h)} times"
            for h in sorted(set(headings))
            if headings.count(h) > 1
        ]
    assert not offenders, "\n".join(offenders)


def test_no_changelog_entry_is_recorded_twice() -> None:
    entries = [
        line for line in CHANGELOG.read_text(encoding="utf-8").split("\n") if line.startswith("- ")
    ]
    assert entries, "no entries found; this test would be vacuous"
    repeated = sorted({e[:100] for e in entries if entries.count(e) > 1})
    assert not repeated, "\n".join(repeated)
