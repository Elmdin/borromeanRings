"""Session charter: the written terms of a delegation, validated fail-closed.

A governed project may commit a ``CHARTER.toml`` naming what the work is for (``goal``),
how much is at stake (``stakes``: ``low`` or ``high`` — two opt-in tiers, never a dial),
what counts as finished (``done_when``), when the agent must stop (``stop_when``), what it
may never do (``may_not``) and who answers for it (``owner``). ``high`` additionally
requires the spine's ``[charter].high_stakes_fields`` (default rollback, reviewer,
blast_radius). Validation has no fallback path: a missing or malformed field becomes a
:class:`Violation` naming it, and every violation is collected before any is reported.

The hedge rule is deliberately tiny and local: a ``done_when`` item that *is* a hedge
phrase ("it works", "good enough") or *contains* a hedge word is not a predicate. Hedge
words come from Matt Might's weasel-word list
(https://matt.might.net/articles/shell-scripts-for-passive-voice-weasel-words-duplicates/);
the general predicate lint is a separate module (#174).

Mechanism inspired by an externally licensed (CC BY-NC-SA) design; everything here is
re-authored — see ADR-0063. See docs/specs/SPEC-charter.md.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

import tomllib

from meta_harness.spine import Config

STAKES: tuple[str, ...] = ("low", "high")
STRING_KEYS: tuple[str, ...] = ("goal", "owner")
LIST_KEYS: tuple[str, ...] = ("done_when", "stop_when", "may_not")
CORE_KEYS: frozenset[str] = frozenset(STRING_KEYS + LIST_KEYS + ("stakes",))

# Whole-item matches: a "predicate" that asserts nothing checkable.
HEDGE_PHRASES: frozenset[str] = frozenset(
    {
        "works",
        "it works",
        "done",
        "looks good",
        "good enough",
        "seems fine",
        "should work",
        "mostly done",
        "basically done",
    }
)
# Word matches (Matt Might's weasel words, plus the completion hedges they license).
HEDGE_WORDS: frozenset[str] = frozenset(
    {"probably", "mostly", "basically", "roughly", "seems", "hopefully", "largely", "somewhat"}
)

_GOAL_WIDTH = 117


@dataclass(frozen=True, order=True)
class Violation:
    """One reason the charter is not acceptable: the field and why."""

    field: str
    reason: str


class CharterError(ValueError):
    """The charter could not even be parsed into a :class:`Charter`.

    Carries every structural violation (bad TOML, unknown types, unreadable file) so the
    check reports them the same way it reports validation violations.
    """

    def __init__(self, violations: tuple[Violation, ...]) -> None:
        self.violations = violations
        super().__init__("; ".join(f"{v.field} — {v.reason}" for v in violations))


@dataclass(frozen=True)
class Charter:
    """A parsed charter. Absent keys are empty (``""``/``()``), never invented."""

    goal: str
    stakes: str
    done_when: tuple[str, ...]
    stop_when: tuple[str, ...]
    may_not: tuple[str, ...]
    owner: str
    extras: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))


# --- parsing ------------------------------------------------------------------


def _read_string(raw: Mapping[str, Any], key: str, problems: list[Violation]) -> str:
    value = raw.get(key, "")
    if not isinstance(value, str):
        problems.append(Violation(key, f"must be a string, got {type(value).__name__}"))
        return ""
    return value


def _read_list(raw: Mapping[str, Any], key: str, problems: list[Violation]) -> tuple[str, ...]:
    value = raw.get(key, [])
    if not isinstance(value, list):
        problems.append(Violation(key, f"must be a list of strings, got {type(value).__name__}"))
        return ()
    items: list[str] = []
    for index, item in enumerate(value):
        if isinstance(item, str):
            items.append(item)
        else:
            problems.append(
                Violation(f"{key}[{index}]", f"must be a string, got {type(item).__name__}")
            )
    return tuple(items)


def parse_charter(text: str) -> Charter:
    """Parse charter TOML into a :class:`Charter`; structural problems raise CharterError.

    Args:
        text: the charter file's content.

    Returns:
        The parsed charter (unvalidated — run :func:`validate`).

    Raises:
        CharterError: on invalid TOML or a value of the wrong type.
    """
    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise CharterError((Violation("file", f"not valid TOML: {exc}"),)) from exc
    problems: list[Violation] = []
    strings = {key: _read_string(raw, key, problems) for key in STRING_KEYS + ("stakes",)}
    lists = {key: _read_list(raw, key, problems) for key in LIST_KEYS}
    extras: dict[str, str] = {}
    for key in sorted(k for k in raw if k not in CORE_KEYS):
        extras[key] = _read_string(raw, key, problems)
    if problems:
        raise CharterError(tuple(sorted(problems)))
    return Charter(
        goal=strings["goal"],
        stakes=strings["stakes"],
        done_when=lists["done_when"],
        stop_when=lists["stop_when"],
        may_not=lists["may_not"],
        owner=strings["owner"],
        extras=MappingProxyType(extras),
    )


def load_charter(path: Path) -> Charter:
    """Read and parse the charter at ``path``; a missing or unreadable file fails closed.

    Args:
        path: the charter file (``[charter].path`` resolved against the project root).

    Returns:
        The parsed charter.

    Raises:
        CharterError: file missing/unreadable, invalid TOML, or wrong types.
    """
    if not path.is_file():
        raise CharterError((Violation("file", f"charter not found at {path}"),))
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CharterError((Violation("file", f"charter unreadable at {path}: {exc}"),)) from exc
    return parse_charter(text)


# --- validation ---------------------------------------------------------------


def _blank_reason(value: str) -> str | None:
    """Why a string is unacceptable — absent keys parse to "", so both read as missing."""
    if not value:
        return "missing or empty"
    if not value.strip():
        return "whitespace only"
    return None


def _normalize(item: str) -> str:
    return " ".join(item.lower().strip().rstrip(".!").split())


def _is_hedge(item: str) -> bool:
    normalized = _normalize(item)
    return normalized in HEDGE_PHRASES or any(word in HEDGE_WORDS for word in normalized.split())


def _check_strings(charter: Charter, problems: list[Violation]) -> None:
    for key in STRING_KEYS:
        value = getattr(charter, key)
        reason = _blank_reason(value)
        if reason:
            problems.append(Violation(key, reason))
    if not charter.stakes:
        problems.append(Violation("stakes", 'missing or empty; must be "low" or "high"'))
    elif charter.stakes not in STAKES:
        problems.append(Violation("stakes", f'must be "low" or "high", got "{charter.stakes}"'))


def _check_lists(charter: Charter, problems: list[Violation]) -> None:
    for key in LIST_KEYS:
        items: tuple[str, ...] = getattr(charter, key)
        if not items:
            problems.append(Violation(key, "missing or empty; list at least one item"))
            continue
        for index, item in enumerate(items):
            reason = _blank_reason(item)
            if reason:
                problems.append(Violation(f"{key}[{index}]", reason))
            elif key == "done_when" and _is_hedge(item):
                problems.append(Violation(f"{key}[{index}]", f'hedge, not a predicate: "{item}"'))


def _check_extras(charter: Charter, allowed: tuple[str, ...], problems: list[Violation]) -> None:
    problems.extend(Violation(key, "unknown key") for key in charter.extras if key not in allowed)
    if charter.stakes != "high":
        return
    for key in allowed:
        reason = _blank_reason(charter.extras.get(key, ""))
        if reason:
            problems.append(Violation(key, f'required at stakes "high"; {reason}'))


def validate(charter: Charter, config: Config) -> tuple[Violation, ...]:
    """Every rule in SPEC-charter.md, applied at once; sorted by field then reason.

    Args:
        charter: the parsed charter.
        config: the spine (``charter_high_stakes_fields`` selects the high-tier extras).

    Returns:
        All violations, or ``()`` when the charter is acceptable.
    """
    problems: list[Violation] = []
    _check_strings(charter, problems)
    _check_lists(charter, problems)
    _check_extras(charter, config.charter_high_stakes_fields, problems)
    return tuple(sorted(problems))


# --- rendering ----------------------------------------------------------------


def render(charter: Charter) -> str:
    """A short, honest summary of a valid charter for the check log.

    Args:
        charter: a charter that passed :func:`validate`.

    Returns:
        Three or four lines: tier + owner, the (bounded) goal, list sizes, and the extras.
    """
    goal = charter.goal
    if len(goal) > _GOAL_WIDTH:
        goal = goal[:_GOAL_WIDTH] + "…"
    lines = [
        f"charter OK — stakes: {charter.stakes}; owner: {charter.owner}",
        f"  goal: {goal}",
        f"  done_when: {len(charter.done_when)} predicate(s); "
        f"stop_when: {len(charter.stop_when)}; may_not: {len(charter.may_not)}",
    ]
    if charter.extras:
        lines.append("  " + "; ".join(f"{k}: {v}" for k, v in sorted(charter.extras.items())))
    return "\n".join(lines)


def missing_charter_reminder(path: str) -> str:
    """The one-line UserPromptSubmit reminder when ``[charter]`` is on but the file is absent.

    Args:
        path: the configured charter path.

    Returns:
        A single line, under 120 bytes for the default path.
    """
    return (
        f"borromeanRings: [charter] is enabled but {path} is missing — "
        "write it before governed work"
    )
