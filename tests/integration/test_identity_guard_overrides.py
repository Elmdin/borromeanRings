"""The PreToolUse guard denies identity overrides, not just a wrong repo config.

The guard used to check only the repository's *configured* identity, and to find the
command by the literal substring ``"git commit"``. Both are evadable (issue #54): git
accepts an identity on the command line and in the environment, and every spelling that
puts a global option between the two words slips past a substring match.

These drive the real hook over its stdin protocol, so they test the wiring — not just
the pure functions underneath it.
"""

import json
import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
GUARD = BORROMEANRINGS_HOME / ".claude" / "hooks" / "pre_bash_guard.sh"

EVASIONS = [
    'git commit --author="Wrong <bad@example.com>" -m x',
    "git -c user.email=bad@example.com commit -m x",
    "GIT_AUTHOR_EMAIL=bad@example.com git commit -m x",
    "git -C . -c user.name=Wrong commit -m x",
]


def _run_guard(command: str) -> str:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    proc = subprocess.run(
        ["bash", str(GUARD)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=60,
        # Inherit the real environment: the guard shells out to python3, and a minimal
        # PATH silently removes it — the guard would then fail open and the test would
        # be asserting nothing.
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(BORROMEANRINGS_HOME)},
    )
    return proc.stdout


def test_every_identity_override_is_denied() -> None:
    for command in EVASIONS:
        assert '"deny"' in _run_guard(command), f"guard allowed an evasion: {command}"


def test_a_normal_commit_is_still_allowed() -> None:
    """Negative control: a guard that denied everything would pass the test above."""
    assert '"deny"' not in _run_guard("git commit -m 'a normal commit'")


def test_a_command_merely_mentioning_git_is_not_blocked() -> None:
    """Writing a file that talks about git identity must not be mistaken for committing."""
    text = "printf '%s' 'docs mention git -c user.email=someone@example.com commit' > /tmp/x"
    assert '"deny"' not in _run_guard(text)
