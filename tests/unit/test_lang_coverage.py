"""Exact-value tests for meta_harness.lang_coverage on hand-written tool-output fixtures.

The fixtures are written BY HAND from the tools' documented output formats (istanbul's
``coverage-summary.json`` as emitted by vitest/jest ``json-summary``; ``go tool cover
-func`` and ``go test`` output), not captured from a live run — see
docs/specs/SPEC-multi-language.md §4.
"""

from __future__ import annotations

import pytest

from meta_harness.lang_coverage import (
    GoTestSummary,
    coverage_percent,
    go_func_total_percent,
    istanbul_line_percent,
    parse_go_test_summary,
)

# istanbul json-summary (vitest --coverage.reporter=json-summary / jest json-summary).
ISTANBUL_SUMMARY = """{
  "total": {
    "lines": {"total": 40, "covered": 34, "skipped": 0, "pct": 85},
    "statements": {"total": 42, "covered": 36, "skipped": 0, "pct": 85.71},
    "functions": {"total": 6, "covered": 6, "skipped": 0, "pct": 100},
    "branches": {"total": 10, "covered": 7, "skipped": 0, "pct": 70}
  },
  "/proj/src/index.ts": {
    "lines": {"total": 40, "covered": 34, "skipped": 0, "pct": 85},
    "statements": {"total": 42, "covered": 36, "skipped": 0, "pct": 85.71},
    "functions": {"total": 6, "covered": 6, "skipped": 0, "pct": 100},
    "branches": {"total": 10, "covered": 7, "skipped": 0, "pct": 70}
  }
}
"""

# istanbul's value when nothing was instrumented.
ISTANBUL_UNKNOWN = (
    '{"total": {"lines": {"total": 0, "covered": 0, "skipped": 0, "pct": "Unknown"}}}'
)

# `go tool cover -func=cover.out`
GO_FUNC = """example.com/m/pkg/a.go:5:\tAdd\t\t100.0%
example.com/m/pkg/a.go:9:\tSub\t\t50.0%
example.com/m/cmd/main.go:3:\tmain\t\t0.0%
total:\t\t\t\t(statements)\t62.5%
"""

# `go test -cover ./...` on a module with one tested package and one untested one.
GO_TEST = """ok  \texample.com/m/pkg\t0.004s\tcoverage: 62.5% of statements
?   \texample.com/m/cmd\t[no test files]
"""

GO_TEST_ALL_UNTESTED = """?   \texample.com/m/pkg\t[no test files]
?   \texample.com/m/cmd\t[no test files]
"""

GO_TEST_FAILING = """--- FAIL: TestAdd (0.00s)
    a_test.go:8: got 3, want 4
FAIL
coverage: 62.5% of statements
FAIL\texample.com/m/pkg\t0.004s
ok  \texample.com/m/other\t0.002s\tcoverage: 100.0% of statements
"""


def test_istanbul_line_percent_exact() -> None:
    assert istanbul_line_percent(ISTANBUL_SUMMARY) == 85.0


def test_istanbul_unknown_pct_is_no_number() -> None:
    assert istanbul_line_percent(ISTANBUL_UNKNOWN) is None


@pytest.mark.parametrize(
    "text",
    ["", "not json", "[]", '{"total": {}}', '{"total": {"lines": {}}}', '{"nototal": 1}'],
)
def test_istanbul_malformed_is_no_number(text: str) -> None:
    assert istanbul_line_percent(text) is None


def test_go_func_total_percent_exact() -> None:
    assert go_func_total_percent(GO_FUNC) == 62.5


def test_go_func_total_takes_the_last_total_line() -> None:
    assert go_func_total_percent(GO_FUNC + "total:\t(statements)\t70.0%\n") == 70.0


@pytest.mark.parametrize("text", ["", "no total here\n", "total: (statements) n/a\n"])
def test_go_func_total_missing_is_no_number(text: str) -> None:
    assert go_func_total_percent(text) is None


def test_parse_go_test_summary_counts_packages() -> None:
    assert parse_go_test_summary(GO_TEST) == GoTestSummary(ok=1, failed=0, no_test_files=1)
    assert parse_go_test_summary(GO_TEST_ALL_UNTESTED) == GoTestSummary(0, 0, 2)
    assert parse_go_test_summary(GO_TEST_FAILING) == GoTestSummary(ok=1, failed=1, no_test_files=0)
    assert parse_go_test_summary("") == GoTestSummary(0, 0, 0)


def test_go_summary_knows_whether_anything_was_tested() -> None:
    assert parse_go_test_summary(GO_TEST).tested is True
    assert parse_go_test_summary(GO_TEST_ALL_UNTESTED).tested is False
    assert parse_go_test_summary("").tested is False


def test_coverage_percent_dispatches_by_language() -> None:
    assert coverage_percent("typescript", ISTANBUL_SUMMARY) == 85.0
    assert coverage_percent("go", GO_FUNC) == 62.5


def test_coverage_percent_rejects_unknown_language() -> None:
    with pytest.raises(ValueError, match="rust"):
        coverage_percent("rust", "")
