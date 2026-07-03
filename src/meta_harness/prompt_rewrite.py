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


def build_directive(context: Mapping[str, Any]) -> str:
    """Build the prompt-rewrite directive injected into the agent's context.

    Args:
        context: the spine's declared ``[context]`` (account, value priorities, …).

    Returns:
        The directive text the agent receives before acting on the user's request.
    """
    lines = [
        "[borromeanRings] Before acting, REWRITE the user's request to preserve its "
        "intent and improve it:",
        "- keep the user's original intent intact; do not add scope they did not ask for;",
        "- apply best agentic-engineering and software-engineering practices;",
    ]
    account = context.get("account")
    if account:
        lines.append(f"- operating context/account in effect: {account};")
    priorities = context.get("value_priorities")
    if priorities:
        lines.append(f"- honor these value priorities (highest first): {', '.join(priorities)};")
    lines.append(
        "Then act on your improved reading, and OPEN your reply with one line — "
        '"Reading this as: <your sharpened version of the request>" — so the user can '
        "correct course immediately. Skip that line only for trivial follow-ups (a bare "
        "yes/no/continue). If your reading changes the request's scope, or acting on it is "
        "irreversible (merge, publish, delete, deploy), STOP and get confirmation first. "
        "Never silently treat your rewrite as the user's words."
    )
    return "\n".join(lines)
