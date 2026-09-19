"""The self-report receipt — did the reply end with a *structural* verification block?

The ``ai-fluency-diligence`` skill asks the wrapped agent to close every substantive reply
with a ``VERIFICATION STATUS`` section: four labelled lines (``Verified``, ``Unverified``,
``Weakest claim``, ``Assumed``) that name what a reader can go and check. It is the agent's
half of the 4D contract made visible, and — like the rewrite directive before #81 — a
request nobody verifies decays. This module verifies it the same way
:mod:`meta_harness.rewrite_contract` verifies the opening line: the Stop hook hands over the
session transcript, the *final* assistant text of the last exchange is found, and a
deterministic verdict is recorded to ``.meta-harness/self_report.jsonl``. Never a block,
never a model call.

Two things are judged, both structural: that the block is there with all four lines, and
that it carries **no confidence grade** — no ``high/medium/low``, no percentage, no
``N/10``, no "confident". A grade invites the reader to defer to the agent's own opinion of
itself; a named unverified claim invites them to check it. See docs/specs/SPEC-self-report.md
and ADR-0066. The transcript reader, entry parser, exchange finder, exemption and prompt
digest are imported from the rewrite contract, not copied.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from meta_harness.rewrite_contract import (
    DEFAULT_TAIL_BYTES,
    TranscriptRefused,
    find_last_exchange,
    is_trivial,
    parse_entries,
    prompt_hash,
    read_tail,
)
from meta_harness.verdict import append_self_report_record

__all__ = [
    "FIELDS",
    "HEADING",
    "Block",
    "SelfReportVerdict",
    "classify",
    "evaluate_transcript",
    "find_block",
    "record",
    "record_from_payload",
    "to_record",
]

#: The heading that opens the block (matched case-insensitively, decoration stripped).
HEADING = "VERIFICATION STATUS"
#: The four labelled lines, in their canonical spelling and conventional order.
FIELDS: tuple[str, ...] = ("Verified", "Unverified", "Weakest claim", "Assumed")
#: Markdown decoration a heading or label may be wrapped in (``**Verified:**``, ``## …``).
_DECORATION = "*_#>`~ \t"
_FENCE = "```"
#: Evidence bounds, so a record line stays small whatever the reply was.
_TEXT_LIMIT = 400
_VIOLATION_LIMIT = 80

#: ``**Verified:** x``, ``- _Unverified_: y``, ``> Weakest claim : z`` are all labelled lines.
_LABEL_RE = re.compile(
    r"^[\s*_`>-]*(" + "|".join(re.escape(f) for f in FIELDS) + r")[\s*_`]*:[\s*_`]*(.*)$",
    re.IGNORECASE,
)
_CANONICAL = {field.lower(): field for field in FIELDS}
#: A grade word that IS a field's whole answer (``Weakest claim: medium``).
_GRADE_WORD_RE = re.compile(r"^(?:high|medium|med|low)[.!]?$", re.IGNORECASE)
#: Numeric levels and confidence talk anywhere in the block.
_GRADE_IN_TEXT_RE = re.compile(
    r"\d+(?:\.\d+)?\s*%|\b\d+\s*/\s*10\b|\bconfiden(?:t|ce)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class Block:
    """One ``VERIFICATION STATUS`` block as found in a reply (immutable).

    ``values`` pairs each canonical label found with its (last) value; ``text`` keeps the
    block's raw lines, bounded, as evidence.
    """

    values: tuple[tuple[str, str], ...]
    text: str

    @property
    def present(self) -> tuple[str, ...]:
        """The labels found, in canonical order."""
        found = {label for label, _ in self.values}
        return tuple(field for field in FIELDS if field in found)

    def value(self, label: str) -> str | None:
        """The text after ``label:``, or ``None`` when the label is missing."""
        return next((value for key, value in self.values if key == label), None)


@dataclass(frozen=True)
class SelfReportVerdict:
    """One deterministic decision about one reply's self-report, with its evidence.

    ``status`` is ``present``, ``absent``, ``malformed`` (a line missing), ``graded`` (the
    structural rule broken), ``exempt`` (trivial prompt) or ``unknown`` (no evidence).
    ``violation`` names the offending fragment for ``graded`` and is empty otherwise.
    """

    status: str
    reason: str
    prompt_hash: str
    present_fields: tuple[str, ...] = ()
    violation: str = ""
    line: int | None = None


# --- pure core ---------------------------------------------------------------------------


def _strip(line: str) -> str:
    return line.strip().strip(_DECORATION)


def _is_heading(line: str) -> bool:
    return _strip(line).rstrip(":").strip().lower() == HEADING.lower()


def _unfenced(text: str) -> list[str]:
    """The reply's lines with every fenced code block removed (fences included)."""
    kept: list[str] = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith(_FENCE):
            fenced = not fenced
            continue
        if not fenced:
            kept.append(line)
    return kept


def _parse_fields(lines: Sequence[str]) -> tuple[tuple[str, str], ...]:
    """Label/value pairs from the lines after the heading (last label wins; continuations join)."""
    values: dict[str, str] = {}
    current: str | None = None
    for line in lines:
        match = _LABEL_RE.match(line)
        if match:
            current = _CANONICAL[match.group(1).lower()]
            values[current] = match.group(2).strip()
        elif current is not None and line.strip():
            values[current] = f"{values[current]} {line.strip()}".strip()
    return tuple(values.items())


def find_block(text: str) -> Block | None:
    """The reply's ``VERIFICATION STATUS`` block, or ``None`` when it has none.

    Fenced code is ignored (a quoted template is not a filed report); when the heading
    appears more than once the last one is the block; a label repeated inside the block
    keeps its last value; an unlabelled line continues the previous field.
    """
    lines = _unfenced(text)
    headings = [index for index, line in enumerate(lines) if _is_heading(line)]
    if not headings:
        return None
    body = lines[headings[-1] + 1 :]
    raw = "\n".join(lines[headings[-1] :]).strip()
    return Block(_parse_fields(body), raw[:_TEXT_LIMIT])


def _grade(block: Block) -> str:
    """The first fragment that breaks the structural rule, or ``""`` when none does."""
    for label, value in block.values:
        if _GRADE_WORD_RE.match(value.strip()):
            return f"{label}: {value.strip()}"[:_VIOLATION_LIMIT]
    match = _GRADE_IN_TEXT_RE.search(block.text)
    return match.group(0)[:_VIOLATION_LIMIT] if match else ""


def classify(block: Block | None, digest: str = "", line: int | None = None) -> SelfReportVerdict:
    """Decide the verdict for a found (or missing) block (pure)."""
    if block is None:
        return SelfReportVerdict("absent", "reply carried no VERIFICATION STATUS block", digest)
    present = block.present
    if len(present) < len(FIELDS):
        missing = ", ".join(f for f in FIELDS if f not in present)
        reason = f"block is missing: {missing}"
        return SelfReportVerdict("malformed", reason, digest, present, line=line)
    violation = _grade(block)
    if violation:
        reason = "block carries a confidence grade (structural rule)"
        return SelfReportVerdict("graded", reason, digest, present, violation, line)
    return SelfReportVerdict(
        "present", "block present with all four lines", digest, present, line=line
    )


def assess_reply(prompt: str, reply: str, line: int | None) -> SelfReportVerdict:
    """The verdict for ``reply`` (the final text answering ``prompt``); trivial ⇒ exempt."""
    digest = prompt_hash(prompt)
    if is_trivial(prompt):
        reason = "trivial prompt (exempt, as for the rewrite contract)"
        return SelfReportVerdict("exempt", reason, digest, line=line)
    return classify(find_block(reply), digest, line)


# --- transcript --------------------------------------------------------------------------


def evaluate_transcript(
    path: Path, max_bytes: int = DEFAULT_TAIL_BYTES, allowed_root: Path | None = None
) -> SelfReportVerdict:
    """The self-report verdict for the last exchange in the transcript at ``path``.

    Never raises: a refused, unreadable, malformed or promptless transcript is ``unknown``.
    The judged reply is the *last* assistant text after the last human prompt.
    """
    try:
        first_line_no, lines = read_tail(path, max_bytes, allowed_root)
    except TranscriptRefused as exc:
        return SelfReportVerdict("unknown", str(exc), "")
    except OSError as exc:
        return SelfReportVerdict("unknown", f"transcript unreadable: {exc}", "")
    exchange = find_last_exchange(parse_entries(lines, first_line_no), final=True)
    if exchange is None:
        return SelfReportVerdict("unknown", "no human prompt found in the transcript tail", "")
    if exchange.reply is None:
        reason = "no assistant text after the last prompt"
        return SelfReportVerdict("unknown", reason, prompt_hash(exchange.prompt))
    return assess_reply(exchange.prompt, exchange.reply, exchange.reply_line)


# --- recording ---------------------------------------------------------------------------


def to_record(verdict: SelfReportVerdict, session_id: str, timestamp: str) -> dict[str, object]:
    """The JSON-line shape persisted per Stop (see SPEC-self-report.md)."""
    return {
        "ts": timestamp,
        "session_id": session_id,
        "prompt_hash": verdict.prompt_hash,
        "status": verdict.status,
        "present_fields": list(verdict.present_fields),
        "violation": verdict.violation,
        "line": verdict.line,
    }


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record(
    project_root: Path | str, verdict: SelfReportVerdict, session_id: str, now: str | None = None
) -> None:
    """Append ``verdict`` to the project's self-report record (append-only)."""
    append_self_report_record(project_root, to_record(verdict, session_id, now or _now()))


def record_from_payload(
    project_root: Path | str, payload: str, now: str | None = None
) -> SelfReportVerdict:
    """Evaluate and record the verdict for a Stop-hook payload (JSON text); never raises.

    A garbage payload or one without ``transcript_path`` records ``unknown`` — the
    absence of evidence is itself recorded, so the tally stays honest.
    """
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        data = None
    session = ""
    if not isinstance(data, dict):
        verdict = SelfReportVerdict("unknown", "hook payload unreadable", "")
    else:
        session = str(data.get("session_id", ""))
        path = data.get("transcript_path")
        if isinstance(path, str) and path:
            verdict = evaluate_transcript(Path(path))
        else:
            verdict = SelfReportVerdict("unknown", "no transcript_path in the hook payload", "")
    record(project_root, verdict, session, now)
    return verdict
