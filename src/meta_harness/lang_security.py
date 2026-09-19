"""ast-grep findings for the non-Python ``50_security`` checks — parse, never grep.

ast-grep (survey-verified: MIT, offline, no key) is the structural matcher ADR-0054
routes non-Python contracts through; the TypeScript ``50_security`` check runs
``ast-grep scan --json`` with a shipped rule file and hands the JSON here. A finding is
a fact about a call site, so the verdict is binary: any finding fails. Malformed JSON
raises so the check fails CLOSED rather than reading garbage as "clean".
See docs/specs/SPEC-multi-language.md §3 and ADR-0068.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    """One ast-grep match: where (1-based line) and which rule."""

    path: str
    line: int
    rule: str
    message: str


def _finding(item: object) -> Finding:
    if not isinstance(item, dict):
        raise ValueError(f"ast-grep match is not an object: {item!r}")
    try:
        start = item["range"]["start"]["line"]
        return Finding(
            path=str(item["file"]),
            line=int(start) + 1,  # ast-grep lines are 0-based
            rule=str(item.get("ruleId", "")),
            message=str(item.get("message", "")),
        )
    except (KeyError, TypeError) as exc:
        raise ValueError(f"ast-grep match missing a field: {item!r}") from exc


def parse_ast_grep_json(text: str) -> tuple[Finding, ...]:
    """Parse ``ast-grep scan --json`` output. Empty output is no findings."""
    if not text.strip():
        return ()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"ast-grep output is not JSON: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError("ast-grep output is not a JSON array")
    return tuple(_finding(item) for item in data)


def render_findings(findings: tuple[Finding, ...]) -> str:
    """The log text: one line per finding, or ``no findings``."""
    if not findings:
        return "no findings"
    lines = [f"{len(findings)} finding(s):"]
    lines.extend(f"  - {f.path}:{f.line} [{f.rule}] {f.message}" for f in findings)
    return "\n".join(lines)
