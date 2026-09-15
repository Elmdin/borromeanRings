"""The rewrite contract — verifying that the agent honoured the prompt-rewrite directive.

The ``UserPromptSubmit`` hook injects a directive (:mod:`meta_harness.prompt_rewrite`)
asking the wrapped agent to open its reply with one ``Reading this as:`` line. Until
issue #81 nothing checked that it happened: an injected directive is a request, and a
request competing with the rest of the agent's context decays. This module turns the
directive into a **verifiable contract**: the Stop hook hands it the session transcript
(``transcript_path`` in the Stop payload), it finds the assistant turn that answered the
last human prompt and decides — deterministically, with no model call — whether the
contract was honoured. The verdict is recorded (``.meta-harness/rewrite_contract.jsonl``,
append-only) and tallied by the self-status view; it never blocks. Record, don't nag.

Pure core (:func:`assess_reply`, :func:`find_last_exchange`) plus one bounded reader
(:func:`read_tail`): a multi-GB transcript is never loaded whole — only its tail is
parsed, and the skipped prefix is streamed only to keep line numbers exact. Every
failure to obtain evidence yields the honest verdict ``unknown``, never a guess.
See docs/specs/SPEC-rewrite-contract.md and ADR-0059.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from meta_harness.prompt_rewrite import MARKER
from meta_harness.verdict import append_rewrite_record

__all__ = [
    "DEFAULT_TAIL_BYTES",
    "MARKER",
    "TRIVIAL_PROMPTS",
    "Exchange",
    "RewriteVerdict",
    "TranscriptRefused",
    "assess_reply",
    "default_transcript_root",
    "evaluate_transcript",
    "find_last_exchange",
    "is_trivial",
    "parse_entries",
    "prompt_hash",
    "read_tail",
    "record",
    "record_from_payload",
    "to_record",
]

#: How much of the transcript's tail is parsed. A single agentic turn can carry large
#: tool results, so this is generous; if the last prompt lies further back the verdict
#: is ``unknown`` (the tail held no human prompt), never a guess.
DEFAULT_TAIL_BYTES = 8 * 1024 * 1024
_CHUNK = 1024 * 1024
#: Evidence kept per record, so a record line stays small whatever the reply was.
_MATCHED_LIMIT = 200

#: The directive exempts "a bare yes/no/continue"; this is that exemption, made exact.
#: Compared after lower-casing, trimming, and stripping trailing punctuation.
TRIVIAL_PROMPTS = frozenset(
    {
        "y",
        "n",
        "yes",
        "no",
        "ok",
        "okay",
        "k",
        "go",
        "go ahead",
        "continue",
        "proceed",
        "sure",
        "yes please",
        "yes, please",
        "do it",
        "yep",
        "yeah",
        "nope",
    }
)
_STRIP_PUNCTUATION = ".!?"
#: Markdown decoration an agent may wrap the opening line in (``**Reading this as:**``).
_DECORATION = "*_#>`~ \t"
#: Where the substrate keeps session transcripts, relative to its config directory.
_TRANSCRIPT_SUBDIR = ("projects",)
_CONFIG_DIR_ENV = "CLAUDE_CONFIG_DIR"
_OUTSIDE = "transcript path outside the substrate's transcript directory"


class TranscriptRefused(ValueError):
    """The transcript path was refused before any byte of it was read."""


@dataclass(frozen=True)
class RewriteVerdict:
    """One deterministic decision about one prompt/reply pair, with its evidence.

    ``status`` is one of ``honoured``, ``not_honoured``, ``exempt`` (trivial prompt) or
    ``unknown`` (no evidence obtainable); ``line`` is the 1-based transcript line of the
    assessed reply and ``matched`` the opening text it was judged on (bounded).
    """

    status: str
    reason: str
    prompt_hash: str
    line: int | None = None
    matched: str = ""

    @property
    def honoured(self) -> bool | None:
        """``True``/``False`` for a judged verdict; ``None`` when nothing was judged."""
        if self.status == "honoured":
            return True
        if self.status == "not_honoured":
            return False
        return None


@dataclass(frozen=True)
class Exchange:
    """The last human prompt in a transcript and the assistant text that answered it."""

    prompt: str
    reply: str | None
    reply_line: int | None


def prompt_hash(prompt: str) -> str:
    """The prompt's record key — the same digest ``prompt_rewrite.sh`` dedupes on."""
    return hashlib.sha256(prompt.encode()).hexdigest()[:16]


def is_trivial(prompt: str) -> bool:
    """Is this a bare follow-up (yes/no/continue…) the directive itself exempts?"""
    bare = prompt.strip().lower().rstrip(_STRIP_PUNCTUATION).strip()
    return bare == "" or bare in TRIVIAL_PROMPTS


def _opening_line(reply: str) -> str:
    for line in reply.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped.lstrip(_DECORATION)
    return ""


def assess_reply(prompt: str, reply: str, line: int | None) -> RewriteVerdict:
    """Decide whether ``reply`` (the answer to ``prompt``) honoured the contract (pure)."""
    opening = _opening_line(reply)[:_MATCHED_LIMIT]
    digest = prompt_hash(prompt)
    if is_trivial(prompt):
        reason = "trivial prompt (exempt by the directive's own wording)"
        return RewriteVerdict("exempt", reason, digest, line, opening)
    if not opening:
        return RewriteVerdict("not_honoured", "reply had no text", digest, line, "")
    if opening.lower().startswith(MARKER.lower()):
        return RewriteVerdict("honoured", "reply opened with the marker", digest, line, opening)
    return RewriteVerdict("not_honoured", "reply opened with something else", digest, line, opening)


# --- transcript parsing ------------------------------------------------------------------


def parse_entries(lines: Sequence[str], first_line_no: int) -> list[tuple[int, dict[str, Any]]]:
    """Decode JSONL lines into ``(line_no, entry)`` pairs, skipping anything malformed."""
    entries: list[tuple[int, dict[str, Any]]] = []
    for offset, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            entries.append((first_line_no + offset, data))
    return entries


def _content(entry: Mapping[str, Any]) -> Any:
    message = entry.get("message")
    return message.get("content") if isinstance(message, Mapping) else None


def _is_human_entry(entry: Mapping[str, Any]) -> bool:
    """Is this a user entry the substrate marks as typed by the human (``origin.kind``)?

    Only those count: tool results, injected skill text (``isMeta``), slash commands,
    task notifications and post-compaction summaries are not prompts the directive
    fired on.
    """
    if entry.get("type") != "user" or entry.get("isMeta"):
        return False
    origin = entry.get("origin")
    return isinstance(origin, Mapping) and origin.get("kind") == "human"


def _prompt_text(content: Any) -> str | None:
    """The prompt text of a string or text-only block list; ``None`` for anything else."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list) or not all(
        isinstance(block, Mapping) and block.get("type") == "text" for block in content
    ):
        return None
    return " ".join(str(block.get("text", "")) for block in content)


def _human_prompt(entry: Mapping[str, Any]) -> str | None:
    """The prompt text if ``entry`` is a human-typed prompt, else ``None``."""
    return _prompt_text(_content(entry)) if _is_human_entry(entry) else None


def _assistant_text(entry: Mapping[str, Any]) -> str | None:
    """The first non-empty text block of a main-thread assistant entry, else ``None``."""
    if entry.get("type") != "assistant" or entry.get("isSidechain"):
        return None
    content = _content(entry)
    if not isinstance(content, list):
        return None
    for block in content:
        if isinstance(block, Mapping) and block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                return text
    return None


def find_last_exchange(
    entries: Sequence[tuple[int, Mapping[str, Any]]], *, final: bool = False
) -> Exchange | None:
    """The last human prompt and the assistant text that answered it (``None`` if no prompt).

    By default the reply is the *first* assistant text after the prompt — where this
    contract's opening line lives. With ``final=True`` it is the *last* one: the text the
    human reads at the end of a multi-entry turn, where the self-report block lives
    (:mod:`meta_harness.self_report`).
    """
    last_prompt: tuple[int, str] | None = None
    for index, (_, entry) in enumerate(entries):
        prompt = _human_prompt(entry)
        if prompt is not None:
            last_prompt = (index, prompt)
    if last_prompt is None:
        return None
    index, prompt = last_prompt
    replies = [
        (line_no, text)
        for line_no, entry in entries[index + 1 :]
        if (text := _assistant_text(entry)) is not None
    ]
    if not replies:
        return Exchange(prompt, None, None)
    line_no, text = replies[-1] if final else replies[0]
    return Exchange(prompt, text, line_no)


# --- bounded I/O -------------------------------------------------------------------------


def default_transcript_root() -> Path | None:
    """The directory the substrate's transcripts must live under (defense in depth).

    ``$CLAUDE_CONFIG_DIR/projects`` when the substrate relocated its config; otherwise
    ``~/.claude/projects`` when it exists, else the current user's home. ``None`` when
    even the home directory cannot be determined — the caller then refuses to read.
    """
    config_dir = os.environ.get(_CONFIG_DIR_ENV)
    if config_dir:
        return Path(config_dir).joinpath(*_TRANSCRIPT_SUBDIR)
    try:
        home = Path.home()
    except RuntimeError:
        return None
    default = home.joinpath(".claude", *_TRANSCRIPT_SUBDIR)
    return default if default.is_dir() else home


def _refuse_unless_allowed(path: Path, allowed_root: Path | None) -> None:
    """Raise :class:`TranscriptRefused` unless ``path`` is a plain ``.jsonl`` file that
    resolves (symlinks followed) to somewhere under ``allowed_root``."""
    if path.suffix != ".jsonl":
        raise TranscriptRefused("not a .jsonl transcript")
    if allowed_root is None or not path.resolve().is_relative_to(allowed_root.resolve()):
        raise TranscriptRefused(_OUTSIDE)
    if path.is_symlink():
        raise TranscriptRefused("transcript path is a symlink")


def read_tail(
    path: Path, max_bytes: int = DEFAULT_TAIL_BYTES, allowed_root: Path | None = None
) -> tuple[int, list[str]]:
    """The last ``max_bytes`` of ``path`` as lines, with the 1-based number of the first.

    Reads only the tail; the skipped prefix is streamed in chunks purely to count
    newlines so the reported line numbers stay exact. When the read starts mid-file the
    first (possibly partial) line is dropped. Refuses, before reading a byte, anything
    that is not a plain ``.jsonl`` file resolving under ``allowed_root`` (default:
    :func:`default_transcript_root`) — the hook passes the substrate's own transcript
    path and nothing else may be read through it, whatever the payload says.

    Raises:
        TranscriptRefused: not a ``.jsonl`` path, outside the transcript directory
            (symlink escapes included), or a symlink.
        OSError: the file is missing or unreadable.
    """
    root = default_transcript_root() if allowed_root is None else allowed_root
    _refuse_unless_allowed(path, root)
    start = max(0, path.stat().st_size - max_bytes)
    skipped_newlines = 0
    with path.open("rb") as fh:
        remaining = start
        while remaining > 0:
            chunk = fh.read(min(_CHUNK, remaining))
            skipped_newlines += chunk.count(b"\n")
            remaining -= len(chunk)
        data = fh.read(max_bytes)
    lines = data.decode("utf-8", errors="replace").split("\n")
    first_line_no = skipped_newlines + 1
    if start > 0:
        lines = lines[1:]
        first_line_no += 1
    return first_line_no, lines


def evaluate_transcript(
    path: Path, max_bytes: int = DEFAULT_TAIL_BYTES, allowed_root: Path | None = None
) -> RewriteVerdict:
    """The contract verdict for the last exchange in the transcript at ``path``.

    Never raises: a refused, unreadable, malformed or promptless transcript is ``unknown``.
    """
    try:
        first_line_no, lines = read_tail(path, max_bytes, allowed_root)
    except TranscriptRefused as exc:
        return RewriteVerdict("unknown", str(exc), "")
    except OSError as exc:
        return RewriteVerdict("unknown", f"transcript unreadable: {exc}", "")
    exchange = find_last_exchange(parse_entries(lines, first_line_no))
    if exchange is None:
        return RewriteVerdict("unknown", "no human prompt found in the transcript tail", "")
    if exchange.reply is None:
        reason = "no assistant text after the last prompt"
        return RewriteVerdict("unknown", reason, prompt_hash(exchange.prompt))
    return assess_reply(exchange.prompt, exchange.reply, exchange.reply_line)


# --- recording ---------------------------------------------------------------------------


def to_record(verdict: RewriteVerdict, session_id: str, timestamp: str) -> dict[str, object]:
    """The JSON-line shape persisted per Stop (see SPEC-rewrite-contract.md)."""
    return {
        "ts": timestamp,
        "session_id": session_id,
        "prompt_hash": verdict.prompt_hash,
        "honoured": verdict.honoured,
        "status": verdict.status,
        "reason": verdict.reason,
        "line": verdict.line,
        "matched": verdict.matched,
    }


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record(
    project_root: Path | str, verdict: RewriteVerdict, session_id: str, now: str | None = None
) -> None:
    """Append ``verdict`` to the project's rewrite-contract record (append-only)."""
    append_rewrite_record(project_root, to_record(verdict, session_id, now or _now()))


def record_from_payload(
    project_root: Path | str, payload: str, now: str | None = None
) -> RewriteVerdict:
    """Evaluate and record the verdict for a Stop-hook payload (JSON text); never raises.

    A garbage payload or one without ``transcript_path`` records ``unknown`` — the
    absence of evidence is itself recorded, so the tally stays honest.
    """
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        data = None
    if data is None:
        verdict = RewriteVerdict("unknown", "hook payload unreadable", "")
        session = ""
    else:
        session = str(data.get("session_id", "")) if isinstance(data, dict) else ""
        path = data.get("transcript_path") if isinstance(data, dict) else None
        if isinstance(path, str) and path:
            verdict = evaluate_transcript(Path(path))
        else:
            verdict = RewriteVerdict("unknown", "no transcript_path in the hook payload", "")
    record(project_root, verdict, session, now)
    return verdict
