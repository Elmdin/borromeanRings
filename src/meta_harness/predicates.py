"""Predicate lint: hedge words and graph integrity in acceptance predicates.

A *predicate* is a checkable statement a document makes about done-ness: a SPEC
``Contract``/``Guarantees``/``Acceptance`` bullet, an ADR ``Consequences`` bullet phrased
as an obligation (must/never/shall), or an issue-form task-list item. Two defects are
mechanical to detect and this module detects both, purely (no I/O):

* **hedges** — a qualifier that leaves the predicate with no observable that would settle
  it: "the HEALTHCHECK command is *meaningful*" has no yes/no answer, "the HEALTHCHECK
  command *probes the service*" does. :func:`hedged` names the first such term.
* **orphans** — a SPEC that names no shipped check id, no existing test file and no issue,
  so no gate, test run or ticket can ever reach it. Only *resolvable* references count, so
  the orphan set can never be empty by construction (the vacuity 4D's validator once
  shipped).

The list of hedge terms is this repo's own, organised by the ambiguity categories of
ISO/IEC/IEEE 29148:2018 §5.2.7 and the INCOSE Guide for Writing Requirements.
Check ``23_predicates`` reads the files and gathers the known sets; see
docs/specs/SPEC-predicates.md and ADR-0064.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

# --------------------------------------------------------------------------- hedges

HEDGES: tuple[str, ...] = (
    # loopholes — a condition only the author can decide was met
    "as appropriate",
    "as applicable",
    "as needed",
    "when needed",
    "as necessary",
    "when necessary",
    "if necessary",
    "if possible",
    "where possible",
    "if feasible",
    "where feasible",
    "where relevant",
    "where applicable",
    "as required",
    # vague qualifiers — an adjective/adverb with no observable threshold
    "appropriate",
    "appropriately",
    "reasonable",
    "reasonably",
    "adequate",
    "adequately",
    "sufficient",
    "sufficiently",
    "suitable",
    "suitably",
    "proper",
    "properly",
    "acceptable",
    "timely",
    "minimal",
    "meaningful",
    "robust",
    "user-friendly",
    "intuitive",
    "easy",
    "easily",
    "seamless",
    "seamlessly",
    "efficient",
    "efficiently",
    "quickly",
    "significant",
    "significantly",
    # approximations — a frequency or quantity left open
    "approximately",
    "roughly",
    "mostly",
    "generally",
    "typically",
    "usually",
    "normally",
    "often",
    "sometimes",
    "several",
    "various",
    # open-ended — the list never closes
    "etc",
    "and so on",
    "and/or",
    "and more",
    # judgment calls — effort or care instead of an artifact
    "best judgment",
    "best effort",
    "carefully",
    "thoroughly",
    "optimal",
    "optimally",
)


def _hedge_pattern(terms: Iterable[str]) -> re.Pattern[str]:
    """Whole-word/phrase alternation; a hyphen counts as a word character on either side
    so ``best-effort`` (a technical term) is not ``best effort``."""
    ordered = sorted({t.strip().lower() for t in terms if t.strip()}, key=len, reverse=True)
    body = "|".join(re.escape(t).replace(r"\ ", r"\s+") for t in ordered)
    return re.compile(rf"(?<![\w-])(?:{body})(?![\w-])", re.IGNORECASE)


_BUILTIN_HEDGES = _hedge_pattern(HEDGES)


def hedged(predicate: str, extra: Iterable[str] = ()) -> str | None:
    """Return the first hedge term in ``predicate`` (earliest by position), else ``None``.

    Args:
        predicate: the predicate text (inline markdown is fine; matching is
            case-insensitive and whitespace-normalized).
        extra: project-specific terms appended to :data:`HEDGES`.
    """
    extra = tuple(extra)
    pattern = _hedge_pattern((*HEDGES, *extra)) if extra else _BUILTIN_HEDGES
    match = pattern.search(predicate)
    if match is None:
        return None
    return " ".join(match.group(0).lower().split())


# --------------------------------------------------------------------------- documents


@dataclass(frozen=True)
class Document:
    """A file's project-relative path and its text (classification is by path only)."""

    path: str
    text: str


@dataclass(frozen=True)
class Predicate:
    """One checkable statement: where it is, what it says, which document kind made it."""

    path: str
    line: int
    text: str
    kind: str


@dataclass(frozen=True)
class Finding:
    """A predicate and the hedge term that leaves it without a yes/no answer."""

    predicate: Predicate
    hedge: str


@dataclass(frozen=True)
class Report:
    """Everything the check needs to log: what was read, what was wrong."""

    predicates: tuple[Predicate, ...]
    findings: tuple[Finding, ...]
    orphans: tuple[str, ...]
    documents: int
    specs: int
    require_reference: bool = True

    @property
    def ok(self) -> bool:
        """True when nothing is hedged and no SPEC is orphaned."""
        return not self.findings and not self.orphans


_SPEC_SECTIONS = frozenset(
    {"acceptance", "acceptance criteria", "contract", "contracts", "guarantees"}
)
_ADR_SECTIONS = frozenset({"consequences"})
_OBLIGATION = re.compile(r"\b(?:must|never|shall)\b", re.IGNORECASE)

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|(\d+)[.)])\s+(.*\S)\s*$")
_CHECKBOX = re.compile(r"^\s*[-*+]\s+\[[ xX]\]\s+(.*\S)\s*$")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
_TITLE_NUMBER = re.compile(r"^\d+(?:\.\d+)*\.?\s+")
_TITLE_CUT = re.compile(r"\s+—\s+|\s+\(|:(?:\s+|$)|\s+/\s+")

_SPEC_NAME = re.compile(r"^SPEC.*\.md$")
_ADR_NAME = re.compile(r"^\d{4}-.*\.md$")


def kind_of(path: str) -> str | None:
    """Classify a document by its filename: ``"spec"``, ``"adr"``, ``"issue"`` or ``None``."""
    parts = path.replace("\\", "/").split("/")
    name = parts[-1]
    if _SPEC_NAME.match(name):
        return "spec"
    if _ADR_NAME.match(name):
        return "adr"
    if name.endswith((".yml", ".yaml")):
        return "issue"
    if name.endswith(".md") and "ISSUE_TEMPLATE" in parts[:-1]:
        return "issue"
    return None


def _normalized_title(heading_text: str) -> str:
    title = _TITLE_NUMBER.sub("", heading_text.strip()).lower()
    return _TITLE_CUT.split(title, maxsplit=1)[0].strip()


class _SectionScanner:
    """Line-by-line state for :func:`_section_items`: fences, the open section, the open item."""

    def __init__(self, sections: frozenset[str]) -> None:
        self.sections = sections
        self.items: list[tuple[int, str]] = []
        self.active: int | None = None  # heading level of the open predicate section
        self.current: list[str] | None = None  # the item being accumulated
        self.fence: str | None = None

    def feed(self, number: int, line: str) -> None:
        if self._inside_fence(line):
            return
        heading = _HEADING.match(line)
        if heading:
            self._enter_heading(len(heading.group(1)), heading.group(2))
        elif self.active is not None:
            self._collect(number, line)

    def _inside_fence(self, line: str) -> bool:
        marker = _FENCE.match(line)
        if self.fence is not None:
            if marker and marker.group(1)[0] == self.fence[0]:
                self.fence = None
            return True
        if marker:
            self.fence = marker.group(1)
            self.current = None
            return True
        return False

    def _enter_heading(self, level: int, title: str) -> None:
        if self.active is not None and level <= self.active:
            self.active = None
        if self.active is None and _normalized_title(title) in self.sections:
            self.active = level
        self.current = None

    def _interrupts_text(self, ordinal: str | None) -> bool:
        """CommonMark: inside a running item, ``NNNN) text`` is a new ordered item only when
        it starts at 1 — so a wrapped line beginning ``0047) had`` stays a continuation."""
        return self.current is not None and ordinal is not None and int(ordinal) != 1

    def _collect(self, number: int, line: str) -> None:
        item = _LIST_ITEM.match(line)
        if item and not self._interrupts_text(item.group(1)):
            self.current = [item.group(2)]
            self.items.append((number, item.group(2)))
        elif self.current is not None and line.strip() and line[0] in " \t":
            self.current.append(line.strip())
            self.items[-1] = (self.items[-1][0], " ".join(self.current))
        else:
            self.current = None


def _section_items(text: str, sections: frozenset[str]) -> list[tuple[int, str]]:
    """List items (first line number, joined text) under headings in ``sections``."""
    scanner = _SectionScanner(sections)
    for number, line in enumerate(text.splitlines(), start=1):
        scanner.feed(number, line)
    return scanner.items


def _checkbox_items(text: str) -> list[tuple[int, str]]:
    items: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        box = _CHECKBOX.match(line)
        if box and box.group(1).replace(".", "").replace("…", "").strip():
            items.append((number, box.group(1)))
    return items


def extract(document: Document) -> tuple[Predicate, ...]:
    """Extract the predicates a document makes, in document order (deterministic)."""
    kind = kind_of(document.path)
    if kind == "spec":
        found = _section_items(document.text, _SPEC_SECTIONS)
    elif kind == "adr":
        found = [
            (n, t) for n, t in _section_items(document.text, _ADR_SECTIONS) if _OBLIGATION.search(t)
        ]
    elif kind == "issue":
        found = _checkbox_items(document.text)
    else:
        return ()
    return tuple(Predicate(document.path, line, text, kind) for line, text in found)


# --------------------------------------------------------------------------- orphans

_CHECK_REF = re.compile(r"(?<![\w-])(\d{2}_[a-z][a-z0-9_]*)(?![\w-])")
_TEST_REF = re.compile(r"(?<![\w-])(test_[A-Za-z0-9_]+\.py)(?![\w-])")
_ISSUE_REF = re.compile(r"(?<![\w&#])#([1-9]\d*)(?!\d)")


def _references_something(
    text: str, known_checks: frozenset[str], known_tests: frozenset[str]
) -> bool:
    if any(ref in known_checks for ref in _CHECK_REF.findall(text)):
        return True
    if any(ref in known_tests for ref in _TEST_REF.findall(text)):
        return True
    return _ISSUE_REF.search(text) is not None


def orphans(
    documents: Iterable[Document],
    *,
    known_checks: frozenset[str],
    known_tests: frozenset[str],
) -> tuple[str, ...]:
    """Paths of SPEC documents that name no shipped check, no existing test and no issue.

    Only references that *resolve* count: an id-shaped token absent from ``known_checks``,
    a ``test_*.py`` absent from ``known_tests`` or ``#0`` does not rescue a SPEC.
    """
    return tuple(
        sorted(
            d.path
            for d in documents
            if kind_of(d.path) == "spec"
            and not _references_something(d.text, known_checks, known_tests)
        )
    )


# --------------------------------------------------------------------------- report


def lint(
    documents: Iterable[Document],
    *,
    known_checks: frozenset[str],
    known_tests: frozenset[str],
    extra_hedges: Iterable[str] = (),
    require_reference: bool = True,
) -> Report:
    """Run the whole lint over ``documents``; the check logs :func:`render` of the result."""
    docs = tuple(documents)
    extra = tuple(extra_hedges)
    predicates = tuple(p for d in docs for p in extract(d))
    findings: list[Finding] = []
    for predicate in predicates:
        hedge = hedged(predicate.text, extra)
        if hedge is not None:
            findings.append(Finding(predicate, hedge))
    specs = sum(1 for d in docs if kind_of(d.path) == "spec")
    orphaned = (
        orphans(docs, known_checks=known_checks, known_tests=known_tests)
        if require_reference
        else ()
    )
    return Report(predicates, tuple(findings), orphaned, len(docs), specs, require_reference)


def render(report: Report) -> str:
    """Human-readable log: ``file:line — predicate — hedge`` per finding, orphans by path."""
    lines: list[str] = []
    if report.findings:
        lines.append(f"PREDICATE LINT — {len(report.findings)} hedged predicate(s):")
        lines.extend(
            f"  {f.predicate.path}:{f.predicate.line} — {f.predicate.text} — {f.hedge}"
            for f in report.findings
        )
        lines.append(
            "  Replace the qualifier with the yes/no fact it stands for "
            "(e.g. 'meaningful HEALTHCHECK' -> 'HEALTHCHECK probes the service')."
        )
    if report.orphans:
        lines.append(
            f"ORPHAN SPEC(s) — {len(report.orphans)} name no shipped check id (NN_name), "
            "no existing test file (test_*.py) and no issue (#N):"
        )
        lines.extend(f"  {path}" for path in report.orphans)
    if not lines:
        refs = "reference rule off"
        if report.require_reference:
            refs = f"{report.specs} SPEC(s) referenced"
        lines.append(
            f"predicate lint satisfied: {len(report.predicates)} predicate(s) in "
            f"{report.documents} document(s); 0 hedged; {refs}"
        )
    return "\n".join(lines)
