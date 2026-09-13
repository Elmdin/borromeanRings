"""Prompt rewriting: borromeanRings enforces it; the wrapped agent performs it.

borromeanRings does not rewrite the user's prompt itself. It injects a directive (built
here from the spine's declared ``[context]``) instructing the wrapped agent to
rewrite the user's in-the-moment request — preserving intent and improving it per
the declared context and best practices — and to open its reply with a one-line
``Reading this as:`` rendering of the improved request, so the user can steer.
Confirmation-before-acting is reserved for irreversible or scope-changing
readings: a contract cheap enough to survive real sessions (the original
show-and-confirm ceremony decayed into invisibility — see issue #81). This
respects agent autonomy: it asks the agent to refine the prompt, it does not
dictate a plan. See docs/specs/SPEC-prompt-rewrite.md and docs/adr/0011-*.md.
"""

from collections.abc import Mapping
from typing import Any

#: The line the directive asks the agent to open its reply with. The single source for
#: both the directive text and the Stop-side verification (meta_harness.rewrite_contract).
MARKER = "Reading this as:"


def build_directive(context: Mapping[str, Any]) -> str:
    """Build the prompt-rewrite directive injected into the agent's context.

    Args:
        context: the spine's declared ``[context]`` (account, value priorities, …).

    Returns:
        The directive text the agent receives before acting on the user's request.
    """
    lines = [
        "[borromeanRings] Before acting, REWRITE the user's request to sharpen it "
        "without changing it:",
        "- keep their intent; add no scope they did not ask for;",
        "- apply best agentic- and software-engineering practice;",
    ]
    account = context.get("account")
    if account:
        lines.append(f"- operating context: {account};")
    priorities = context.get("value_priorities")
    if priorities:
        lines.append(f"- value priorities (highest first): {', '.join(priorities)};")
    lines.append(
        # The trimmed wording (#135), but built from MARKER: rewrite_contract (#81)
        # decides whether a reply honoured the contract by looking for exactly this
        # string, so the directive and the checker must never drift apart.
        "Act on that reading and OPEN your reply with one line — "
        f'"{MARKER} <your sharpened request>" — so the user can correct course. '
        "Skip it for trivial follow-ups (yes/no/continue). If your reading changes scope, "
        "or the act is irreversible (merge, publish, delete, deploy), STOP and confirm. "
        "Never pass your rewrite off as the user's words."
    )
    return "\n".join(lines)
