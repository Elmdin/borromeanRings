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

import pytest

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
GUARD = BORROMEANRINGS_HOME / ".claude" / "hooks" / "pre_bash_guard.sh"

DECLARED_NAME = "Declared Dev"
DECLARED_EMAIL = "declared@example.com"

# Hermetic on purpose. Pointing the guard at the harness repo made every verdict depend on
# ambient state the test does not control: a CI checkout has no user.name/user.email, so
# the configured-identity rule denied everything (the positive test passed for the wrong
# reason, the negative control failed); and on a protected branch (dev, main) the
# branch rule denies every commit. Here the configured identity matches the declared one
# and HEAD is a work branch, so an override is the only thing left that can be denied.
SPINE = f"""
[checks]
required = ["00_build"]

[git]
name = "{DECLARED_NAME}"
email = "{DECLARED_EMAIL}"

[collaboration]
protected_branches = ["main", "dev"]
"""

EVASIONS = [
    'git commit --author="Wrong <bad@example.com>" -m x',
    "git -c user.email=bad@example.com commit -m x",
    "GIT_AUTHOR_EMAIL=bad@example.com git commit -m x",
]

#: An override of the DISPLAY NAME only. Under the default rule (`[git].require =
#: "email"`) the name is not what the project requires, so this is not an evasion —
#: the gate would not fail such a commit either, and a guard that denied it would
#: disagree with the gate (#229). Under `email+name` it is an evasion.
NAME_ONLY_OVERRIDE = "git -C . -c user.name=Wrong commit -m x"


def _project_at(root: Path, spine: str) -> Path:
    """A governed project whose configured identity is the declared one, on a work branch."""
    root.mkdir()
    (root / "borromeanrings.toml").write_text(spine, encoding="utf-8")
    for args in (
        ["init", "-q", "-b", "feat/work"],
        ["config", "user.name", DECLARED_NAME],
        ["config", "user.email", DECLARED_EMAIL],
    ):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
    return root


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return _project_at(tmp_path / "project", SPINE)


def _run_guard(command: str, project: Path) -> str:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    proc = subprocess.run(
        ["bash", str(GUARD)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=60,
        cwd=project,
        # Inherit the real environment: the guard shells out to python3, and a minimal
        # PATH silently removes it — the guard would then fail open and the test would
        # be asserting nothing.
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(project)},
    )
    return proc.stdout


def test_every_identity_override_is_denied(project: Path) -> None:
    for command in EVASIONS:
        out = _run_guard(command, project)
        # Denied by the OVERRIDE rule — not by some other rule that happened to fire.
        assert '"deny"' in out, f"guard allowed an evasion: {command}"
        assert "override refused" in out, f"denied for the wrong reason: {command}: {out}"


def test_a_display_name_override_is_allowed_when_only_the_email_is_required(
    project: Path,
) -> None:
    """The guard and the gate must want the same thing. Under the default rule the
    address is the identity; the display name is a profile field on whichever host
    performs the merge, and requiring it made the gate unpassable on this project's own
    trunk (#229)."""
    out = _run_guard(NAME_ONLY_OVERRIDE, project)

    assert '"deny"' not in out, out


def test_a_display_name_override_is_denied_when_the_project_requires_the_name(
    tmp_path: Path,
) -> None:
    strict = _project_at(
        tmp_path / "strict",
        SPINE.replace(
            f'email = "{DECLARED_EMAIL}"', f'email = "{DECLARED_EMAIL}"\nrequire = "email+name"'
        ),
    )

    out = _run_guard(NAME_ONLY_OVERRIDE, strict)

    assert '"deny"' in out, out
    assert "override refused" in out, out


def test_a_normal_commit_is_still_allowed(project: Path) -> None:
    """Negative control: a guard that denied everything would pass the test above."""
    out = _run_guard("git commit -m 'a normal commit'", project)
    assert '"deny"' not in out, out


def test_a_command_merely_mentioning_git_is_not_blocked(project: Path) -> None:
    """Writing a file that talks about git identity must not be mistaken for committing."""
    text = "printf '%s' 'docs mention git -c user.email=someone@example.com commit' > /tmp/x"
    assert '"deny"' not in _run_guard(text, project)


def test_a_refusal_states_the_requirement_it_was_decided_against(project: Path) -> None:
    """The message used to be built from the raw config, so under the default rule it
    told the user to set a display name the project does not require — advice that would
    not change the outcome (review of #257)."""
    out = _run_guard("git commit --author='Wrong <bad@example.com>' -m x", project)

    assert '"deny"' in out, out
    assert DECLARED_EMAIL in out
    assert DECLARED_NAME not in out, f"claims the display name is required: {out}"
