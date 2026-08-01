"""The force-push guard must permit ``--force-with-lease`` while still blocking
bare ``--force`` / ``-f``.

Regression: the deny-list matched the substring ``git push --force``, which also
occurs inside ``git push --force-with-lease`` — so the guard blocked the exact
flag its own deny message told you to use ("Use --force-with-lease deliberately
if truly required"). Every feature-branch amend (reword + re-push) tripped it.
The over-broad match also denied *any* command that merely mentioned the string
(e.g. a ``grep`` for it). See ADR-0019 (local-guard-only) and
docs/specs/SPEC-collaboration.md.

Each test drives the real hook with a crafted PreToolUse payload on stdin and
asserts the emitted permission decision.
"""

import json
import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
HOOKS = BORROMEANRINGS_HOME / ".claude" / "hooks"


def _governed_project(tmp_path: Path) -> Path:
    """A minimal governed project: no [git]/[collaboration], so only the
    deny-list can produce a verdict (identity/protected-branch checks fail open)."""
    (tmp_path / "borromeanrings.toml").write_text(
        '[project]\nlanguage = "none"\npackage = "x"\n\n'
        '[checks]\nrequired = ["05_hygiene"]\n\n'
        "[hygiene]\nrequires = []\n"
    )
    return tmp_path


def _guard_denies(project: Path, command: str) -> bool:
    """Run the guard on ``command``; True iff it emits a deny decision."""
    payload = json.dumps({"tool_input": {"command": command}})
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(project)
    env["BORROMEANRINGS_HOOK_STDIN_TIMEOUT"] = "5"
    out = subprocess.run(
        ["bash", str(HOOKS / "pre_bash_guard.sh")],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    ).stdout
    if not out.strip():
        return False
    try:
        decision = json.loads(out)["hookSpecificOutput"]["permissionDecision"]
    except (json.JSONDecodeError, KeyError):
        return False
    return decision == "deny"


def test_force_with_lease_is_allowed(tmp_path: Path) -> None:
    project = _governed_project(tmp_path)
    assert not _guard_denies(project, "git push --force-with-lease origin feat/x"), (
        "guard must permit --force-with-lease (the flag its deny message recommends)"
    )


def test_bare_force_is_denied(tmp_path: Path) -> None:
    assert _guard_denies(_governed_project(tmp_path), "git push --force origin main")


def test_short_force_flag_is_denied(tmp_path: Path) -> None:
    assert _guard_denies(_governed_project(tmp_path), "git push -f origin main")


def test_unrelated_mention_is_not_denied(tmp_path: Path) -> None:
    # Merely naming the pattern (e.g. grepping for it) must not be a force-push.
    project = _governed_project(tmp_path)
    assert not _guard_denies(project, "grep -r 'git push --force' docs/")
