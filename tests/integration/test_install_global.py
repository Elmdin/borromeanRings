"""``install-global.sh`` merges borromeanRings's hooks into a Claude config, non-destructively.

This script edits a user's *global* Claude settings, so the property that matters most is
that it MERGES: an unrelated key, or someone else's hook, must survive. It is also the
one entry point capable of changing a machine's behaviour outside any repository, which
is why every test here redirects it with ``CLAUDE_CONFIG_DIR`` — a test that wrote to the
real ``~/.claude`` would silently re-enable global governance on the developer's machine.
See issue #53.
"""

import json
import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
INSTALL = BORROMEANRINGS_HOME / "install-global.sh"
TIMEOUT_S = 120
HOOK_SCRIPTS = {
    "UserPromptSubmit": "prompt_rewrite.sh",
    "Stop": "stop_gate.sh",
    "PostToolUse": "post_edit_format.sh",
    "PreToolUse": "pre_bash_guard.sh",
}
HOOK_EVENTS = tuple(HOOK_SCRIPTS)


def _install(config_dir: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["CLAUDE_CONFIG_DIR"] = str(config_dir)  # never the real ~/.claude
    return subprocess.run(
        ["bash", str(INSTALL)],
        env=env,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_S,
        check=False,
    )


def _settings(config_dir: Path) -> dict:
    return json.loads((config_dir / "settings.json").read_text(encoding="utf-8"))


def test_installs_every_hook_pointing_at_this_borromeanrings(tmp_path: Path) -> None:
    config = tmp_path / "claude"
    assert _install(config).returncode == 0
    hooks = _settings(config)["hooks"]
    for event, script in HOOK_SCRIPTS.items():
        commands = [h["command"] for entry in hooks[event] for h in entry["hooks"]]
        # Both halves matter: the RIGHT script, from THIS install. Asserting only the
        # path would pass even if the wrong hook were wired under the event.
        assert any(script in c for c in commands), f"{event} is not wired to {script}"
        assert any(str(BORROMEANRINGS_HOME) in c for c in commands), (
            f"{event} does not point at this borromeanRings"
        )


def test_unrelated_settings_survive(tmp_path: Path) -> None:
    """It merges into a real config; clobbering someone's settings is not acceptable."""
    config = tmp_path / "claude"
    config.mkdir()
    (config / "settings.json").write_text(
        json.dumps({"theme": "dark", "permissions": {"allow": ["Bash(ls:*)"]}}),
        encoding="utf-8",
    )
    _install(config)
    settings = _settings(config)
    assert settings["theme"] == "dark"
    assert settings["permissions"] == {"allow": ["Bash(ls:*)"]}


def test_a_foreign_hook_on_the_same_event_is_kept(tmp_path: Path) -> None:
    """Only borromeanRings's own prior entries are replaced — not another tool's."""
    config = tmp_path / "claude"
    config.mkdir()
    foreign = {"hooks": [{"type": "command", "command": "/opt/other-tool/hook.sh"}]}
    (config / "settings.json").write_text(
        json.dumps({"hooks": {"Stop": [foreign]}}), encoding="utf-8"
    )
    _install(config)
    commands = [
        h["command"] for entry in _settings(config)["hooks"]["Stop"] for h in entry["hooks"]
    ]
    assert "/opt/other-tool/hook.sh" in commands, "a foreign hook was discarded"
    assert any(str(BORROMEANRINGS_HOME) in c for c in commands)


def test_rerunning_does_not_duplicate_our_hooks(tmp_path: Path) -> None:
    """Re-run after moving borromeanRings is documented usage; it must stay idempotent."""
    config = tmp_path / "claude"
    _install(config)
    _install(config)
    stop = _settings(config)["hooks"]["Stop"]
    ours = [h for entry in stop for h in entry["hooks"] if str(BORROMEANRINGS_HOME) in h["command"]]
    assert len(ours) == 1, f"expected one entry after re-running, got {len(ours)}"


def test_skills_are_installed_with_the_home_placeholder_substituted(tmp_path: Path) -> None:
    """A skill still carrying the placeholder would tell the agent to run a path that
    does not exist."""
    config = tmp_path / "claude"
    _install(config)
    skills = list((config / "skills").rglob("*.md"))
    assert skills, "no skills installed"
    for skill in skills:
        assert "__BORROMEANRINGS_HOME__" not in skill.read_text(encoding="utf-8")
