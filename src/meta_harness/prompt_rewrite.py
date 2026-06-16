"""Prompt rewriting: borromeo enforces it; the wrapped agent performs it.

borromeo does not rewrite the user's prompt itself. It injects a directive (built
here from the spine's declared ``[context]``) instructing the wrapped agent to
rewrite the user's in-the-moment request — preserving intent and improving it per
the declared context and best practices — and to *show* the rewrite before acting.
This respects agent autonomy: it asks the agent to refine the prompt, it does not
dictate a plan. See docs/SPEC-prompt-rewrite.md and docs/adr/0011-*.md.
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
        "[borromeo] Before acting, REWRITE the user's request to preserve its "
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
        "Then SHOW the user the improved prompt and what changed, and PROPOSE it — unless the "
        "request is trivial/unambiguous, ASK them to confirm or edit before you act. Do not "
        "silently treat your rewrite as their words; let them steer."
    )
    return "\n".join(lines)
