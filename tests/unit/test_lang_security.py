"""Exact-value tests for meta_harness.lang_security (ast-grep `scan --json` output).

Fixture written BY HAND from ast-grep's documented JSON match shape (an array of
objects with ``file``, ``range.start.line`` (0-based), ``ruleId``, ``message``).
"""

from __future__ import annotations

import pytest

from meta_harness.lang_security import Finding, parse_ast_grep_json, render_findings

AST_GREP_JSON = """[
  {"text": "eval(s)", "range": {"byteOffset": {"start": 10, "end": 17},
   "start": {"line": 2, "column": 4}, "end": {"line": 2, "column": 11}},
   "file": "src/a.ts", "lines": "    eval(s)", "language": "TypeScript",
   "ruleId": "no-eval", "severity": "error", "message": "eval executes arbitrary code"},
  {"text": "new Function(b)", "range": {"byteOffset": {"start": 40, "end": 55},
   "start": {"line": 7, "column": 0}, "end": {"line": 7, "column": 15}},
   "file": "src/b.ts", "lines": "new Function(b)", "language": "TypeScript",
   "ruleId": "no-new-function", "severity": "error", "message": "Function constructor"}
]
"""


def test_parse_ast_grep_json_exact() -> None:
    assert parse_ast_grep_json(AST_GREP_JSON) == (
        Finding(path="src/a.ts", line=3, rule="no-eval", message="eval executes arbitrary code"),
        Finding(path="src/b.ts", line=8, rule="no-new-function", message="Function constructor"),
    )


def test_parse_ast_grep_json_empty_is_no_findings() -> None:
    assert parse_ast_grep_json("[]") == ()
    assert parse_ast_grep_json("") == ()


@pytest.mark.parametrize("text", ["not json", "{}", "[1, 2]", '[{"file": "x"}]'])
def test_parse_ast_grep_json_malformed_raises(text: str) -> None:
    with pytest.raises(ValueError):
        parse_ast_grep_json(text)


def test_render_findings_names_each_site() -> None:
    text = render_findings(parse_ast_grep_json(AST_GREP_JSON))
    assert "2 finding(s)" in text
    assert "src/a.ts:3 [no-eval] eval executes arbitrary code" in text
    assert "src/b.ts:8 [no-new-function]" in text


def test_render_no_findings() -> None:
    assert render_findings(()) == "no findings"
