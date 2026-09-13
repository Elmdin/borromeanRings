"""Quote fidelity: is a quotation a document attributes to a saved source really its text?

The research skill saves the passages it relies on under ``docs/research/<slug>/`` and
promises that every claim is entailed by one of them (ADR-0060). This module gives that
promise a mechanism for the verbatim part: a document marks a quotation as

    > the quoted lines
    — source: docs/research/<slug>/sources/3.md#L12-L14

(or ``<!-- quote: path#L12-L14 -->``), and ``verify`` re-reads the named span and reports
the quotation as ``verbatim``, ``drifted`` (with a unified diff), ``missing`` (no such
file), ``out_of_range`` (the span is not in the file) or ``orphan`` (a marker with no
blockquote). Both sides are normalised the same way — curly quotes straightened,
whitespace collapsed, one wrapping pair of double quotes and trailing sentence
punctuation dropped — and nothing else: wording must match. Matching is
**line-for-line**: a single-line quote must sit inside one source line, a multi-line
quote must cover a contiguous run of source lines, and a match may not start or end
inside a word — so a word dropped at a line boundary can never hide (PR #182 review).

Pure: no I/O. The caller injects ``resolve_source(path) -> str | None`` (``None`` ⇒
missing) and lets an ``OSError`` propagate so it can fail closed. See
docs/specs/SPEC-quotes.md and ADR-0065.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Callable
from dataclasses import dataclass, field

STATUSES: tuple[str, ...] = ("verbatim", "drifted", "missing", "out_of_range", "orphan")
_COUNT_LABELS = {"out_of_range": "out of range"}
_SPAN = r"(?P<path>[^\s#]+)#L(?P<start>\d+)(?:-L(?P<end>\d+))?"
_MARKER = re.compile(
    r"^\s*(?:(?:—|--)\s*source:\s*"
    + _SPAN
    + r"|<!--\s*quote:\s*"
    + _SPAN.replace("(?P<", "(?P<c_")
    + r"\s*-->)\s*$",
    re.IGNORECASE,
)
_CURLY = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})
_TRAILING_PUNCTUATION = ".,;:!?…"
_FENCES = ("```", "~~~")
_NOT_REPO_RELATIVE = "path must be repo-relative (no leading '/', no '..')"
_ORPHAN_DETAIL = "marker has no blockquote in front of it"
_NO_SUCH_FILE = "no such file"
_OUTSIDE_PROJECT = "outside the project"


class OutsideProject(Exception):
    """Raised by a resolver that refuses a source whose real location is outside the root."""


@dataclass(frozen=True)
class Marker:
    """Where a quotation claims to come from: a repo-relative path and a 1-based span."""

    path: str
    start: int
    end: int

    @property
    def label(self) -> str:
        """The span as it is written back in reports: ``path#L<start>-L<end>``."""
        return f"{self.path}#L{self.start}-L{self.end}"


@dataclass(frozen=True)
class Quotation:
    """A marker found in a document; ``text`` is the blockquote it follows (None ⇒ orphan)."""

    line: int
    text: str | None
    marker: Marker


@dataclass(frozen=True)
class QuoteResult:
    """The verdict on one marker: its document position, status and a human detail."""

    document: str
    line: int
    marker: Marker
    status: str
    detail: str = ""


@dataclass(frozen=True)
class QuoteReport:
    """Every result for one document (or a merged set); ``ok`` iff all are verbatim."""

    results: tuple[QuoteResult, ...]

    @property
    def is_empty(self) -> bool:
        """True when nothing was marked — the check reports ``noop``, not pass."""
        return not self.results

    @property
    def ok(self) -> bool:
        """True when every marked quotation is verbatim (vacuously true when empty)."""
        return all(result.status == "verbatim" for result in self.results)

    @property
    def counts(self) -> dict[str, int]:
        """How many results carry each status, keyed in ``STATUSES`` order."""
        return {
            status: sum(1 for result in self.results if result.status == status)
            for status in STATUSES
        }


def _strip_ends(text: str) -> str:
    """Trailing sentence punctuation, one wrapping ``"`` pair, trailing punctuation again."""
    text = text.rstrip(_TRAILING_PUNCTUATION).rstrip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = text[1:-1]
    return text.rstrip(_TRAILING_PUNCTUATION).strip()


def normalise(text: str) -> str:
    """Apply the SPEC's normalisation rules to a text as one line.

    Curly quotes → straight; whitespace runs (newlines included) → one space; trailing
    sentence punctuation stripped; one wrapping pair of ``"`` stripped; punctuation
    stripped again (so ``"wrapped".`` and ``"wrapped."`` both become ``wrapped``).
    """
    return _strip_ends(" ".join(text.translate(_CURLY).split()))


def normalise_lines(text: str) -> tuple[str, ...]:
    """The same rules, keeping line structure: whole-text ends first, then each line's
    whitespace collapsed; blank lines dropped. This is what matching compares."""
    text = _strip_ends(text.translate(_CURLY).strip())
    return tuple(line for line in (" ".join(raw.split()) for raw in text.splitlines()) if line)


def _at_word_boundary(hay: str, start: int, end: int) -> bool:
    """True when hay[start:end] neither starts nor ends in the middle of a word."""
    before = start == 0 or not (hay[start - 1].isalnum() and hay[start].isalnum())
    after = end == len(hay) or not (hay[end - 1].isalnum() and hay[end].isalnum())
    return before and after


def _within_line(needle: str, hay: str) -> bool:
    """``needle`` occurs in ``hay`` at word boundaries (any occurrence)."""
    at = hay.find(needle)
    while at != -1:
        if _at_word_boundary(hay, at, at + len(needle)):
            return True
        at = hay.find(needle, at + 1)
    return False


def _ends_line(needle: str, hay: str) -> bool:
    return hay.endswith(needle) and _at_word_boundary(hay, len(hay) - len(needle), len(hay))


def _starts_line(needle: str, hay: str) -> bool:
    return hay.startswith(needle) and _at_word_boundary(hay, 0, len(needle))


def matches(quote: str, span: str) -> bool:
    """Is ``quote`` verbatim in ``span``, line-for-line and at word boundaries?

    One normalised quote line must occur inside one span line; several must cover a
    contiguous run of span lines — the first as the end of its line, the last as the
    start of its line, every line between equal. An empty quote matches nothing.
    """
    needle, hay = normalise_lines(quote), normalise_lines(span)
    if not needle:
        return False
    if len(needle) == 1:
        return any(_within_line(needle[0], line) for line in hay)
    for offset in range(len(hay) - len(needle) + 1):
        window = hay[offset : offset + len(needle)]
        if (
            _ends_line(needle[0], window[0])
            and window[1:-1] == needle[1:-1]
            and _starts_line(needle[-1], window[-1])
        ):
            return True
    return False


def parse_marker(line: str) -> Marker | None:
    """Parse one document line as a source marker, in either written form; else None."""
    found = _MARKER.match(line)
    if found is None:
        return None
    prefix = "" if found.group("path") is not None else "c_"
    start = int(found.group(prefix + "start"))
    end_text = found.group(prefix + "end")
    end = int(end_text) if end_text is not None else start
    return Marker(path=found.group(prefix + "path"), start=start, end=end)


def _blockquote_text(line: str) -> str:
    body = line[1:]
    return body[1:] if body.startswith(" ") else body


@dataclass
class _Scan:
    """Line-by-line state while extracting: the open blockquote, if any, and fences."""

    found: list[Quotation] = field(default_factory=list)
    pending: list[str] | None = None  # the blockquote awaiting its marker
    pending_line: int = 0
    closed: bool = False  # a blank line has ended `pending` (a new `>` starts afresh)
    in_fence: bool = False

    def feed(self, number: int, line: str) -> None:
        if line.lstrip().startswith(_FENCES):
            self.in_fence, self.pending = not self.in_fence, None
        elif self.in_fence:
            return
        elif line.startswith(">"):
            self._quote_line(number, line)
        elif (marker := parse_marker(line)) is not None:
            self._marker_line(number, marker)
        elif line.strip():
            self.pending = None
        elif self.pending is not None:
            self.closed = True

    def _quote_line(self, number: int, line: str) -> None:
        if self.pending is None or self.closed:
            self.pending, self.pending_line, self.closed = [], number, False
        self.pending.append(_blockquote_text(line))

    def _marker_line(self, number: int, marker: Marker) -> None:
        if self.pending is None:
            self.found.append(Quotation(line=number, text=None, marker=marker))
        else:
            text = "\n".join(self.pending)
            self.found.append(Quotation(line=self.pending_line, text=text, marker=marker))
            self.pending = None


def extract(document_text: str) -> tuple[Quotation, ...]:
    """Find every marker; attach the blockquote it directly follows, or none (orphan).

    A blockquote is a run of ``>`` lines. Blank lines may separate it from its marker;
    any other line ends it unmarked. A second marker after the same blockquote, or a
    marker with no blockquote, is an orphan quotation (``text`` is None). Fenced code
    blocks (triple backticks or ``~~~``) are examples, not claims: skipped entirely, and
    a fence ends any open blockquote.
    """
    scan = _Scan()
    for number, line in enumerate(document_text.splitlines(), 1):
        scan.feed(number, line)
    return tuple(scan.found)


def _escapes_root(path: str) -> bool:
    return path.startswith("/") or ".." in path.split("/")


def _diff(text: str, line: int, marker: Marker, span: list[str], document: str) -> str:
    lines = difflib.unified_diff(
        text.splitlines(),
        span,
        fromfile=f"quote ({document}:{line})",
        tofile=marker.label,
        lineterm="",
    )
    return "\n".join(lines) + "\n"


def _judge(
    text: str, line: int, marker: Marker, source: str | None, document: str
) -> tuple[str, str]:
    """Return (status, detail) for the blockquote ``text`` at ``line`` against its source."""
    if source is None:
        return "missing", _NO_SUCH_FILE
    lines = source.splitlines()
    if marker.start < 1 or marker.end < marker.start or marker.end > len(lines):
        return "out_of_range", f"span L{marker.start}-L{marker.end} is outside 1-{len(lines)}"
    span = lines[marker.start - 1 : marker.end]
    if matches(text, "\n".join(span)):
        return "verbatim", ""
    return "drifted", _diff(text, line, marker, span, document)


def _load(
    resolve_source: Callable[[str], str | None],
    cache: dict[str, str | None],
    outside: set[str],
    path: str,
) -> str | None:
    """Resolve ``path`` once; remember a refusal in ``outside`` instead of a text."""
    if path not in cache and path not in outside:
        try:
            cache[path] = resolve_source(path)
        except OutsideProject:
            outside.add(path)
    return cache.get(path)


def verify(
    document_text: str,
    resolve_source: Callable[[str], str | None],
    document: str = "",
) -> QuoteReport:
    """Verify every marked quotation in ``document_text`` against its saved source.

    ``resolve_source(path)`` returns the source file's text or ``None`` when there is no
    such file; it is called at most once per distinct path. A path that is absolute or
    contains a ``..`` segment is never resolved — it is reported ``missing``; so is one
    the resolver refuses with :class:`OutsideProject` (a symlink that leaves the root).
    Any other exception the resolver raises propagates (the caller fails closed).
    """
    cache: dict[str, str | None] = {}
    outside: set[str] = set()
    results: list[QuoteResult] = []
    for quotation in extract(document_text):
        marker = quotation.marker
        if quotation.text is None:
            status, detail = "orphan", _ORPHAN_DETAIL
        elif _escapes_root(marker.path):
            status, detail = "missing", _NOT_REPO_RELATIVE
        else:
            source = _load(resolve_source, cache, outside, marker.path)
            if marker.path in outside:
                status, detail = "missing", _OUTSIDE_PROJECT
            else:
                status, detail = _judge(quotation.text, quotation.line, marker, source, document)
        results.append(
            QuoteResult(
                document=document, line=quotation.line, marker=marker, status=status, detail=detail
            )
        )
    return QuoteReport(results=tuple(results))


def render(report: QuoteReport) -> str:
    """Format a report as the check's log: one row per result, then the counts."""
    if report.is_empty:
        return "no marked quotations"
    rows: list[str] = []
    for result in report.results:
        row = f"{result.document}:{result.line}: {result.status.upper()} {result.marker.label}"
        if result.status == "drifted":
            rows.append(row)
            rows.extend(f"    {line}" for line in result.detail.rstrip("\n").split("\n"))
        elif result.detail:
            rows.append(f"{row} ({result.detail})")
        else:
            rows.append(row)
    counts = report.counts
    rows.append(
        "quotes: "
        + ", ".join(f"{counts[status]} {_COUNT_LABELS.get(status, status)}" for status in STATUSES)
    )
    return "\n".join(rows)
