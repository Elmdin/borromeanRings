"""Citation extraction: what does this document claim exists?

The largest defect class this repository's review cycle found was **doc overclaim** —
prose asserting something the branch does not contain. Most instances were not judgement
calls but path-resolution facts: a doc citing ``docs/HANDOFF.md`` on a base where that
file lives only on another branch; ``ADR-0057`` cited bare where ``docs/adr/`` stops at
0047; ``docs/CHECKS.md`` described as being "on this base" when it is not.

This module is the pure decision core for that: it turns Markdown text into the citations
it makes, and filters those against an **injected** resolver. It performs no I/O at all —
not a single ``open`` — so what it recognises is decided by *shape alone* and every rule
is testable with a dictionary. Looking things up on disk belongs to
``checks/shared/26_citations.sh``.

Two boundaries are deliberate and permanent, because a gate that implies more than it
verifies is the very defect being fixed: **external URLs are never checked** (that needs a
network, and this runs on every gate) and **issue/PR numbers are never checked** (that
truth lives in GitHub's mutable state). See docs/specs/SPEC-citations.md and ADR-0073.
"""

from __future__ import annotations

import posixpath
import re
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass

#: Top-level names a repo-relative path token may start at. Requiring one of these is what
#: separates a citation from an unrelated slashed string: `origin/docs/handoff` (a git ref)
#: and `learn.chatgpt.com/docs/hooks` (a URL without its scheme) both fail it.
REPO_ROOTS = frozenset(
    {
        ".",
        ".claude",
        ".github",
        "checks",
        "docs",
        "examples",
        "scripts",
        "skills",
        "src",
        "tests",
        "tools",
    }
)

#: One path segment. `*` is admitted only so the ADR form `docs/adr/0043-*.md` can be
#: recognised and rejected-or-converted deliberately; every other glob/placeholder
#: character is left out of the class so a template like `src/<pkg>/mod.py` never matches.
_SEGMENT = r"[A-Za-z0-9._*-]+"

#: A repo-relative path token: at least one `/`, a final segment carrying an extension
#: that STARTS WITH A LETTER, and an optional `#anchor` or `:line` suffix. The letter is
#: load-bearing: without it `checks/00..50` (prose for "the checks numbered 00 to 50")
#: reads as a file named `checks/00.` with extension `50`.
_PATH = rf"(?:{_SEGMENT}/)+{_SEGMENT}\.[A-Za-z][A-Za-z0-9]*(?:\#[A-Za-z0-9._-]+|:\d+(?:-\d+)?)?"

_TOKEN_RE = re.compile(
    r"\[[^\]]*\]\(\s*(?P<link>[^)\s]+)(?:\s+\"[^\"]*\")?\s*\)"
    rf"|(?<![\w./-])(?P<path>{_PATH})"
    r"|(?<![\w-])ADR-(?P<adr>\d{4})(?![\w-])"
    r"|(?<![\w./-])(?P<check>\d{2}_[a-z][a-z0-9_]*)(?![\w-])"
)

#: The ONLY accepted forward-reference marker, anchored at the end of the citation it
#: excuses: an optional closing backtick, spaces, at most one `,`/`;`, then a
#: parenthesised `(lands with X)` / `(on X)` whose X is a PR number or a branch-shaped
#: name. Narrow on purpose — a marker ordinary prose could produce by accident would let
#: the whole check be bypassed. `(on line 5)` is deliberately not a marker.
_LABEL_RE = re.compile(
    r"`?[ ]*[,;]?[ ]*\((?:lands with|on)\s+"
    r"`?(?:\#\d+|[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9._-]+)+)`?\)",
    re.IGNORECASE,
)

_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
_SCHEME_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")
_LINE_SUFFIX_RE = re.compile(r":\d+(?:-\d+)?$")
_ADR_FILE_RE = re.compile(r"(\d{4})-")
_BACKTICKS_RE = re.compile(r"`+")
_SLUG_DROP_RE = re.compile(r"[^\w\s-]", re.UNICODE)
_SLUG_SPACE_RE = re.compile(r"\s")


@dataclass(frozen=True)
class Citation:
    """One thing a document claims exists.

    ``kind`` is ``path``, ``anchor``, ``adr`` or ``check``; ``target`` is the normalised
    thing to look up; ``line`` is 1-based; ``has_forward_label`` records that the author
    marked it as deliberately ahead of this branch.
    """

    kind: str
    target: str
    line: int
    has_forward_label: bool


#: One unresolved citation with the document that made it — what :func:`render` prints.
Finding = tuple[str, Citation]


def code_spans(line: str) -> list[tuple[int, int]]:
    """Half-open ranges of the inline-code spans in ``line``.

    A run of N backticks opens a span that the next run of exactly N backticks closes.
    Used only to suppress **links** written inside backticks: such a link renders as
    literal text, so it is not a link and cannot be a dead one. Backticked *paths* are
    still citations — backticks are how this repository writes its real ones.
    """
    runs = [(match.start(), match.end()) for match in _BACKTICKS_RE.finditer(line)]
    spans: list[tuple[int, int]] = []
    index = 0
    while index < len(runs):
        start, end = runs[index]
        for candidate in range(index + 1, len(runs)):
            if runs[candidate][1] - runs[candidate][0] == end - start:
                spans.append((start, runs[candidate][1]))
                index = candidate
                break
        index += 1
    return spans


def prose_lines(text: str) -> Iterator[tuple[int, str]]:
    """The 1-based numbered lines of ``text`` that are not inside a fenced code block.

    Everything between triple-backtick or ``~~~`` fences is example configuration, a
    terminal transcript or a template — illustrative by construction, never a claim.
    """
    fence = ""
    for number, line in enumerate(text.splitlines(), start=1):
        opener = _FENCE_RE.match(line)
        if opener:
            marker = opener.group(1)[0]
            fence = "" if fence == marker else (fence or marker)
            continue
        if not fence:
            yield number, line


def slugify(heading: str) -> str:
    """The GitHub-style anchor slug for a heading.

    Lowercase, every character that is not a letter/digit/underscore/space/hyphen dropped,
    then **each remaining space** replaced by a hyphen — one per space, not one per run.
    That last detail is not cosmetic: a heading with an em dash renders as ``a--b``, so
    collapsing runs would make every such anchor look broken.
    """
    text = _SLUG_DROP_RE.sub("", heading.strip().lower())
    return _SLUG_SPACE_RE.sub("-", text.strip())


def heading_slugs(text: str) -> tuple[str, ...]:
    """Every anchor a reader could link to in ``text``, in document order."""
    return tuple(
        slugify(match.group(1))
        for _, line in prose_lines(text)
        if (match := _HEADING_RE.match(line))
    )


def _split_suffix(raw: str) -> tuple[str, str]:
    """Split a path token into (path, heading fragment), dropping any ``:line`` suffix."""
    path, _, fragment = raw.partition("#")
    return _LINE_SUFFIX_RE.sub("", path), fragment


def _adr_from_glob(segments: Sequence[str]) -> tuple[str, str] | None:
    """A globbed ADR path (`docs/adr/0043-*.md`) as a reference to the record number.

    The single exception to "a glob is illustrative": the number is the citation, and the
    filename after it is decoration. Any other globbed path is not a claim about a file
    that exists, so it is not a citation at all.
    """
    number = _ADR_FILE_RE.match(segments[-1])
    if number is None or segments[-2] != "adr":
        return None
    return "adr", f"ADR-{number.group(1)}"


def _classify_token(raw: str) -> tuple[str, str] | None:
    """Classify a bare or backticked path token; ``None`` when it is not a citation."""
    path, fragment = _split_suffix(raw)
    segments = path.split("/")
    if segments[0] not in REPO_ROOTS:
        return None
    if "*" in path:
        return _adr_from_glob(segments)
    normal = posixpath.normpath(path)
    if fragment:
        return "anchor", f"{normal}#{fragment}"
    return "path", normal


def _classify_link(raw: str, base: str) -> tuple[str, str] | None:
    """Classify a Markdown link target; ``None`` when it is not a repo-relative citation.

    Link targets are file-relative by Markdown's own rules, so they are joined to ``base``
    — the citing document's directory — and normalised. External schemes, absolute paths,
    bare ``#fragment`` links, globs, and anything escaping the repository are not claims
    this check can settle.
    """
    if _SCHEME_RE.match(raw) or raw.startswith("/") or "*" in raw:
        return None
    path, _, fragment = raw.partition("#")
    if not path:
        return None
    normal = posixpath.normpath(posixpath.join(base, path))
    if normal == "." or normal.startswith(".."):
        return None
    if fragment:
        return "anchor", f"{normal}#{fragment}"
    return "path", normal


def _classify(match: re.Match[str], base: str) -> tuple[str, str] | None:
    """Route one token match to the rule for its shape."""
    if (link := match.group("link")) is not None:
        return _classify_link(link, base)
    if (path := match.group("path")) is not None:
        return _classify_token(path)
    if (adr := match.group("adr")) is not None:
        return "adr", f"ADR-{adr}"
    return "check", match.group("check")


def _line_citations(line: str, number: int, base: str) -> Iterator[Citation]:
    """Every citation on one non-fenced line."""
    spans = code_spans(line)
    for match in _TOKEN_RE.finditer(line):
        if match.group("link") is not None and any(
            start <= match.start() < end for start, end in spans
        ):
            continue
        classified = _classify(match, base)
        if classified is None:
            continue
        kind, target = classified
        yield Citation(kind, target, number, _LABEL_RE.match(line, match.end()) is not None)


def citations(text: str, *, base: str = "") -> tuple[Citation, ...]:
    """Every citation ``text`` makes, in source order.

    Args:
        text: the Markdown document.
        base: the citing document's directory, used to resolve file-relative link
            targets. Path tokens in prose are repo-relative and ignore it.
    """
    return tuple(
        citation
        for number, line in prose_lines(text)
        for citation in _line_citations(line, number, base)
    )


def unresolved(
    found: Sequence[Citation], resolve: Callable[[Citation], bool]
) -> tuple[Citation, ...]:
    """The citations that do not resolve and were not labelled as forward references.

    ``resolve`` is injected rather than imported so this module never touches a
    filesystem: the check supplies a resolver over git-tracked paths, and tests supply a
    dictionary.
    """
    return tuple(
        citation for citation in found if not citation.has_forward_label and not resolve(citation)
    )


def render(findings: Sequence[Finding]) -> str:
    """The failure report: one ``file:line — citation — verdict`` line per finding."""
    lines = [
        "UNRESOLVED CITATIONS — documentation on this branch cites what it does not contain:",
        "",
    ]
    lines += [
        f"  {path}:{citation.line} — {citation.target} — does not exist on this branch"
        for path, citation in findings
    ]
    lines += [
        "",
        "Fix the document. If the reference is deliberately ahead of this branch, label it "
        "in place: `docs/THING.md` (lands with #NNN). See docs/specs/SPEC-citations.md.",
    ]
    return "\n".join(lines)
