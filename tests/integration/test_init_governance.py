"""``init.sh`` bootstraps a project into governance, and the gate then runs there.

This is the portability claim (ADR-0013) in executable form: borromeanRings is not copied
into a project, it is *referenced* by one. If `init.sh` writes a config the spine cannot
load, or hooks that point at the wrong place, governance silently does not happen in that
project — and nothing else in the suite would notice. See issue #53.
"""

import json
import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
INIT = BORROMEANRINGS_HOME / "init.sh"
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
TIMEOUT_S = 180

HOOK_SCRIPTS = {
    "UserPromptSubmit": "prompt_rewrite.sh",
    "Stop": "stop_gate.sh",
    "PostToolUse": "post_edit_format.sh",
    "PreToolUse": "pre_bash_guard.sh",
}


def _init(target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(INIT), str(target)],
        capture_output=True,
        text=True,
        timeout=TIMEOUT_S,
        check=False,
    )


def test_init_writes_a_config_the_spine_can_load(tmp_path: Path) -> None:
    """A config that does not load is a project that is not governed."""
    project = tmp_path / "fresh"
    project.mkdir()
    assert _init(project).returncode == 0

    config = project / "borromeanrings.toml"
    assert config.is_file()

    from meta_harness.spine import load_config

    loaded = load_config(config)
    assert loaded.required_checks, "a governed project must require at least one check"
    assert loaded.src_dir


def test_init_wires_every_hook_at_this_borromeanrings(tmp_path: Path) -> None:
    """Hooks are how governance becomes automatic; a wrong path means it never runs."""
    project = tmp_path / "fresh"
    project.mkdir()
    _init(project)

    settings = json.loads((project / ".claude" / "settings.json").read_text(encoding="utf-8"))
    hooks = settings["hooks"]
    for event, script in HOOK_SCRIPTS.items():
        commands = [hook["command"] for entry in hooks[event] for hook in entry["hooks"]]
        assert any(script in command for command in commands), f"{event} not wired"
        assert any(str(BORROMEANRINGS_HOME) in command for command in commands), (
            f"{event} does not point at this borromeanRings"
        )


def test_the_gate_actually_runs_in_a_freshly_initialised_project(tmp_path: Path) -> None:
    """The acceptance criterion: init, then gate, and the project is green.

    A starter config that cannot pass its own gate would make every new adoption start
    red, which is how people learn to ignore the gate.
    """
    project = tmp_path / "fresh"
    project.mkdir()
    _init(project)

    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(project)
    result = subprocess.run(
        ["bash", str(VERIFY)], env=env, capture_output=True, text=True, timeout=TIMEOUT_S
    )
    assert result.returncode == 0, (
        f"a freshly initialised project must gate green:\n{result.stdout}"
    )
    assert "RESULT: PASS" in result.stdout


def test_init_does_not_clobber_an_existing_config(tmp_path: Path) -> None:
    """Re-running init on an adopted project must not discard its tuned policy."""
    project = tmp_path / "adopted"
    project.mkdir()
    _init(project)
    config = project / "borromeanrings.toml"
    config.write_text(config.read_text(encoding="utf-8") + "\n# tuned by hand\n", encoding="utf-8")

    result = _init(project)
    assert result.returncode == 0
    assert "# tuned by hand" in config.read_text(encoding="utf-8")
    assert "already exists" in result.stdout


def test_init_installs_the_skills(tmp_path: Path) -> None:
    """Skills are how a session discovers what borromeanRings can do for it."""
    project = tmp_path / "fresh"
    project.mkdir()
    _init(project)
    skills_dir = project / ".claude" / "skills"
    installed = {p.name for p in skills_dir.iterdir() if p.is_dir()}
    assert installed, "no skills installed"
    # A skill still carrying the home placeholder would tell the agent to run a path
    # that does not exist. install-global.sh substitutes it; init.sh must too.
    placeholder = "__BORROMEANRINGS_" + "HOME__"
    for doc in skills_dir.rglob("*.md"):
        assert placeholder not in doc.read_text(encoding="utf-8"), (
            f"{doc.name} still carries the unsubstituted home placeholder"
        )
