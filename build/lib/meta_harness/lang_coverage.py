"""Coverage numbers for the non-Python lanes — parse tool output, never compute in bash.

The coverage ratchet (``40_test``) needs one number per run: percent of lines covered.
Python's ``pytest --cov`` writes a JSON the shell reads directly; TypeScript and Go tools
write their own formats, parsed here so the shell only orchestrates (the same split as
:mod:`meta_harness.mutation`). Every parser returns ``None`` for "no number", and the
check fails CLOSED on ``None`` — a coverage the tool could not report is never a pass.
See docs/specs/SPEC-multi-language.md §4 and ADR-0068.

Formats (documented, not captured — fixtures in tests/unit/test_lang_coverage.py):

* **istanbul ``coverage-summary.json``** — emitted by vitest
  (``--coverage.reporter=json-summary``) and jest (``--coverageReporters=json-summary``):
  ``{"total": {"lines": {"total": N, "covered": M, "skipped": K, "pct": P}, ...}, ...}``.
  ``pct`` is the string ``"Unknown"`` when nothing was instrumented.
* **``go tool cover -func=<profile>``** — one line per function and a final
  ``total:\\t(statements)\\tP%`` line.
* **``go test ./...``** — one line per package: ``ok  \\tpkg\\t0.1s\\tcoverage: P% of
  statements``, ``FAIL\\tpkg\\t0.1s`` or ``?   \\tpkg\\t[no test files]``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

_GO_TOTAL_RE = re.compile(r"^total:\s.*?(\d+(?:\.\d+)?)%\s*$", re.MULTILINE)
_GO_OK_RE = re.compile(r"^ok\s+\S+", re.MULTILINE)
_GO_FAIL_RE = re.compile(r"^FAIL\s+\S+\s+[\d.]+s", re.MULTILINE)
_GO_NO_TESTS_RE = re.compile(r"^\?\s+\S+\s+\[no test files\]", re.MULTILINE)


@dataclass(frozen=True)
class GoTestSummary:
    """Per-package tallies from ``go test ./...`` output."""

    ok: int
    failed: int
    no_test_files: int

    @property
    def tested(self) -> bool:
        """Whether at least one package actually ran tests (passing or failing)."""
        return self.ok + self.failed > 0


def istanbul_line_percent(text: str) -> float | None:
    """``total.lines.pct`` from an istanbul ``coverage-summary.json``; ``None`` if absent."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    total = data.get("total")
    if not isinstance(total, dict):
        return None
    lines = total.get("lines")
    if not isinstance(lines, dict):
        return None
    pct = lines.get("pct")
    if isinstance(pct, bool) or not isinstance(pct, int | float):
        return None  # istanbul writes "Unknown" when zero lines were instrumented
    return float(pct)


def go_func_total_percent(text: str) -> float | None:
    """The percent on the (last) ``total:`` line of ``go tool cover -func``; ``None`` if absent."""
    matches = _GO_TOTAL_RE.findall(text)
    return float(matches[-1]) if matches else None


def parse_go_test_summary(text: str) -> GoTestSummary:
    """Count ``ok`` / ``FAIL`` / ``[no test files]`` package lines in ``go test`` output."""
    return GoTestSummary(
        ok=len(_GO_OK_RE.findall(text)),
        failed=len(_GO_FAIL_RE.findall(text)),
        no_test_files=len(_GO_NO_TESTS_RE.findall(text)),
    )


_PARSERS = {"typescript": istanbul_line_percent, "go": go_func_total_percent}


def coverage_percent(language: str, text: str) -> float | None:
    """Dispatch to the lane's parser. Unknown ``language`` raises (fail closed)."""
    try:
        parser = _PARSERS[language]
    except KeyError:
        raise ValueError(f"no coverage parser for language '{language}'") from None
    return parser(text)
