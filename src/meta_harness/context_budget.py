"""Context budget: measure what borromeanRings itself puts into the agent's context.

Governance is not free — every hook line, skill file and directive the harness
injects is paid for on every turn. This module measures that always-loaded weight
so ``19_context_budget`` can **ratchet** it: the total may not regress above the
recorded baseline, and there is no absolute target (the project's stance against
number gates). Sources, per governed project root:

* ``directive`` — the UserPromptSubmit prompt-rewrite directive text (injected on
  **every prompt**; passed in by the caller, built from the project's ``[context]``).
* ``instructions`` — ``CLAUDE.md`` / ``AGENTS.md`` at the project root (loaded once
  per session by the wrapped agent).
* ``skill`` — every ``skills/*/SKILL.md`` and ``.claude/skills/*/SKILL.md`` (the
  frontmatter is always loaded; the body on invocation — the whole file is counted
  as the upper bound).
* ``hook`` — the static message templates a hook script can emit to the agent:
  the quoted literal on every line of ``.claude/hooks/*.sh`` whose first word is
  ``echo``, ``printf`` or ``deny`` (the PreToolUse guard's helper, which wraps its
  argument as ``permissionDecisionReason``). Messages composed at run time
  (``deny "$reason"``, the gate's verdict text) are out of scope — see the SPEC.

Tokens are **approximated as bytes / 4, rounded up** (``BYTES_PER_TOKEN``): the
common English-prose rule of thumb, deliberately chosen over a tokenizer dependency
— a ratchet only needs a *consistent* measure, not an exact one. Pure stdlib; the
only I/O is reading the files it reports on. See docs/specs/SPEC-context-budget.md
and ADR-0055.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

BYTES_PER_TOKEN = 4
DIRECTIVE_PATH = "<prompt_rewrite directive>"
_INSTRUCTION_FILES = ("CLAUDE.md", "AGENTS.md")
_SKILL_ROOTS = ("skills", ".claude/skills")
_HOOKS_DIR = ".claude/hooks"
# A line whose first word is echo/printf/deny, followed by one quoted literal: the
# message template the hook would emit. Group 2 or 3 holds the literal's text.
_MESSAGE_VERBS = ("echo", "printf", "deny")
_MESSAGE_LINE = re.compile(r"^\s*(" + "|".join(_MESSAGE_VERBS) + r""")\s+(?:"([^"]*)"|'([^']*)')""")


@dataclass(frozen=True)
class ContextSource:
    """One thing borromeanRings puts into context: what it is, where, and its weight."""

    kind: str
    path: str
    bytes: int
    tokens: int


@dataclass(frozen=True)
class ContextBudget:
    """The per-source rows and their total; ``is_empty`` ⇒ nothing measurable exists."""

    sources: tuple[ContextSource, ...]
    total_bytes: int
    total_tokens: int

    @property
    def is_empty(self) -> bool:
        """True when no source exists at all (the check reports ``noop``, not pass)."""
        return not self.sources


def estimate_tokens(n_bytes: int) -> int:
    """Approximate tokens for ``n_bytes`` of text as ``ceil(n_bytes / 4)``."""
    if n_bytes < 0:
        raise ValueError(f"byte count cannot be negative: {n_bytes}")
    return (n_bytes + BYTES_PER_TOKEN - 1) // BYTES_PER_TOKEN


def hook_message_bytes(script: str) -> int:
    """UTF-8 bytes of the quoted literal on each ``echo``/``printf``/``deny`` line of a hook."""
    total = 0
    for line in script.splitlines():
        found = _MESSAGE_LINE.match(line)
        if found:
            literal = found.group(2) if found.group(2) is not None else found.group(3)
            total += len(literal.encode("utf-8"))
    return total


def _source(kind: str, path: str, n_bytes: int) -> ContextSource:
    return ContextSource(kind=kind, path=path, bytes=n_bytes, tokens=estimate_tokens(n_bytes))


def _skill_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for skills_root in _SKILL_ROOTS:
        files.extend(sorted((root / skills_root).glob("*/SKILL.md")))
    return files


def measure_context_budget(project_root: str | Path, directive: str = "") -> ContextBudget:
    """Measure every context source under ``project_root`` (plus ``directive`` if set).

    Rows come in a stable order — directive, instructions, skills, hooks — each
    group sorted by path, so two runs over the same tree produce the same report.
    Hook scripts with no message literal contribute no row.
    """
    root = Path(project_root)
    rows: list[ContextSource] = []
    if directive:
        rows.append(_source("directive", DIRECTIVE_PATH, len(directive.encode("utf-8"))))
    for name in _INSTRUCTION_FILES:
        file = root / name
        if file.is_file():
            rows.append(_source("instructions", name, file.stat().st_size))
    for file in _skill_files(root):
        rows.append(_source("skill", file.relative_to(root).as_posix(), file.stat().st_size))
    for file in sorted((root / _HOOKS_DIR).glob("*.sh")):
        n_bytes = hook_message_bytes(file.read_text(encoding="utf-8", errors="replace"))
        if n_bytes:
            rows.append(_source("hook", file.relative_to(root).as_posix(), n_bytes))
    return ContextBudget(
        sources=tuple(rows),
        total_bytes=sum(row.bytes for row in rows),
        total_tokens=sum(row.tokens for row in rows),
    )


def format_report(budget: ContextBudget) -> str:
    """Render the rows and the total as the aligned text the check logs."""
    lines = [
        f"{row.kind:<13}{row.bytes:>6} B  ~{row.tokens} tok  {row.path}" for row in budget.sources
    ]
    lines.append(
        f"{'TOTAL':<13}{budget.total_bytes:>6} B  ~{budget.total_tokens} tok  (tokens ≈ bytes/4)"
    )
    return "\n".join(lines)
