"""The Claude Code plugin layout must be a faithful mirror of the three install scripts.

borromeanRings ships as a plugin (ADR-0057, #136): ``.claude-plugin/plugin.json`` names it,
``hooks/hooks.json`` wires the six hooks through ``${CLAUDE_PLUGIN_ROOT}``, and ``skills/``
exposes the project skills by symlink. None of that is exercised by the Python gate on
its own, so these tests pin the contract: the manifests parse and use only documented
fields, every referenced script exists and is executable, the hook wiring is the same
wiring ``init.sh``, ``install-global.sh`` and this repo's own settings produce (modulo the
path prefix), and the version is the repo's VERSION. Loads repo files by path, so it is
excluded from mutmut's sandbox like the other shell-integration suites (setup.cfg).
"""

from __future__ import annotations

import json
import os
import subprocess
import warnings
from pathlib import Path
from typing import Any

from meta_harness.status_assess import HOOK_SCRIPTS, classify_enforcement

HOME = Path(__file__).resolve().parents[2]
PLUGIN_JSON = HOME / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = HOME / ".claude-plugin" / "marketplace.json"
HOOKS_JSON = HOME / "hooks" / "hooks.json"
HOOKS_DIR = HOME / ".claude" / "hooks"
PROJECT_SKILLS = HOME / ".claude" / "skills"
PLUGIN_SKILLS = HOME / "skills"

PLUGIN_ROOT_TOKEN = "${CLAUDE_PLUGIN_ROOT}"

#: plugin.json keys documented in the plugins reference ("Plugin manifest schema":
#: required `name`; metadata fields; component path fields). Anything else is invented.
DOCUMENTED_MANIFEST_KEYS = frozenset(
    {
        "name",
        "displayName",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "metadata",
        "defaultEnabled",
        "skills",
        "commands",
        "agents",
        "workflows",
        "hooks",
        "mcpServers",
        "outputStyles",
        "lspServers",
        "experimental",
        "userConfig",
        "channels",
        "dependencies",
    }
)

#: The matchers init.sh registers per event: one entry per matcher value, in order.
#: ``None`` means an entry without a matcher (event-wide).
EXPECTED_MATCHERS: dict[str, list[str | None]] = {
    "UserPromptSubmit": [None],
    "Stop": [None],
    "PostToolUse": ["Edit|Write|MultiEdit"],
    "PreToolUse": ["Bash"],
    "PreCompact": [None],
    "SessionStart": ["compact", "resume"],
}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _shape(hooks: Any) -> dict[str, list[tuple[str | None, str, int | None]]]:
    """A hooks block reduced to what must agree across install paths.

    Per event, in order: (matcher, script basename, timeout). The command's path prefix is
    the one thing that legitimately differs (absolute home, ``${CLAUDE_PROJECT_DIR}``,
    ``${CLAUDE_PLUGIN_ROOT}``), so it is dropped.
    """
    shape: dict[str, list[tuple[str | None, str, int | None]]] = {}
    for event, entries in hooks.items():
        for entry in entries:
            for hook in entry["hooks"]:
                assert hook["type"] == "command"
                script = hook["command"].rstrip('"').rsplit("/", 1)[-1]
                shape.setdefault(event, []).append(
                    (entry.get("matcher"), script, hook.get("timeout"))
                )
    return shape


# --- manifests --------------------------------------------------------------------------


def test_plugin_manifest_uses_only_documented_fields_and_the_repo_version() -> None:
    manifest = _load(PLUGIN_JSON)
    assert manifest["name"] == "borromeanrings"
    unknown = set(manifest) - DOCUMENTED_MANIFEST_KEYS
    assert not unknown, f"undocumented plugin.json fields: {sorted(unknown)}"
    version = (HOME / "VERSION").read_text(encoding="utf-8").strip()
    assert manifest["version"] == version, "plugin.json version must track the VERSION file"
    assert manifest["description"]


def test_marketplace_lists_exactly_this_plugin_at_the_repo_root() -> None:
    """Self-hosted single-plugin marketplace: the entry's source is the marketplace root."""
    market = _load(MARKETPLACE_JSON)
    assert market["name"] == "borromeanrings"
    assert market["owner"]["name"]
    entries = market["plugins"]
    assert [e["name"] for e in entries] == [_load(PLUGIN_JSON)["name"]]
    assert entries[0]["source"] == "./"
    # The plugin manifest is the single source of the version: an entry-level version
    # would take precedence (reference, "Version management") and could drift from VERSION.
    assert "version" not in entries[0]


# --- hooks ------------------------------------------------------------------------------


def test_hooks_json_references_only_existing_executable_scripts_via_plugin_root() -> None:
    hooks = _load(HOOKS_JSON)["hooks"]
    for event, entries in hooks.items():
        assert event in HOOK_SCRIPTS, f"{event}: not a borromeanRings hook event"
        for entry in entries:
            for hook in entry["hooks"]:
                command = hook["command"]
                prefix = f'"{PLUGIN_ROOT_TOKEN}"/.claude/hooks/'
                assert command.startswith(prefix), command
                script = HOOKS_DIR / command[len(prefix) :]
                assert script.name == HOOK_SCRIPTS[event], command
                assert script.is_file(), f"{script} does not exist"
                assert os.access(script, os.X_OK), f"{script} is not executable"
                assert isinstance(hook["timeout"], int) and hook["timeout"] > 0


def test_every_hook_script_is_wired_once_per_matcher_used_by_init_sh() -> None:
    shape = _shape(_load(HOOKS_JSON)["hooks"])
    assert set(shape) == set(HOOK_SCRIPTS), "hooks.json must wire exactly HOOK_SCRIPTS"
    for event, script in HOOK_SCRIPTS.items():
        matchers = [matcher for matcher, _, _ in shape[event]]
        assert matchers == EXPECTED_MATCHERS[event], f"{event}: {matchers}"
        assert all(name == script for _, name, _ in shape[event])
        assert len(set(matchers)) == len(matchers), f"{event}: a matcher is registered twice"


def _init_sh_settings(tmp_path: Path) -> dict[str, Any]:
    target = tmp_path / "proj"
    target.mkdir()
    subprocess.run(["bash", str(HOME / "init.sh"), str(target)], check=True, capture_output=True)
    return _load(target / ".claude" / "settings.json")["hooks"]


def _install_global_settings(tmp_path: Path) -> dict[str, Any]:
    config_dir = tmp_path / "claude-config"
    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(config_dir))
    subprocess.run(
        ["bash", str(HOME / "install-global.sh")], check=True, capture_output=True, env=env
    )
    return _load(config_dir / "settings.json")["hooks"]


def test_plugin_wiring_is_identical_to_the_three_install_paths(tmp_path: Path) -> None:
    """One contract, four spellings: plugin, init.sh, install-global.sh, self-governance."""
    plugin = _shape(_load(HOOKS_JSON)["hooks"])
    assert plugin == _shape(_load(HOME / ".claude" / "settings.json")["hooks"])
    assert plugin == _shape(_init_sh_settings(tmp_path))
    assert plugin == _shape(_install_global_settings(tmp_path))


def test_self_status_reads_plugin_wiring_as_automatic_enforcement() -> None:
    """The real hooks.json, fed to the classifier as if it were a project's settings."""
    result = classify_enforcement(_load(HOOKS_JSON), str(HOME))
    assert result.mode == "auto", result.detail


# --- skills -----------------------------------------------------------------------------


def skill_link_state(link: Path, target: Path) -> str:
    """How ``skills/<name>`` reached this checkout: ``symlink``, ``degraded`` or ``broken``.

    ``degraded`` is a Windows clone without ``core.symlinks``: git writes the symlink as a
    plain text file whose whole content is the relative target path. It is a recognised
    state with a documented remedy (docs/PLUGIN.md, "Windows checkouts"), not corruption —
    anything else (a copy, a file naming some other path) is ``broken``.
    """
    if link.is_symlink():
        return "symlink" if link.resolve() == target.resolve() else "broken"
    if link.is_file():
        expected = os.path.relpath(target, link.parent).replace(os.sep, "/")
        return "degraded" if link.read_text(encoding="utf-8").strip() == expected else "broken"
    return "broken"


def test_skill_link_state_recognises_each_checkout_shape(tmp_path: Path) -> None:
    target = tmp_path / ".claude" / "skills" / "s"
    target.mkdir(parents=True)
    (tmp_path / "skills").mkdir()
    good = tmp_path / "skills" / "s"
    good.symlink_to(Path("..") / ".claude" / "skills" / "s")
    assert skill_link_state(good, target) == "symlink"
    good.unlink()
    good.write_text("../.claude/skills/s\n", encoding="utf-8")  # what git writes without symlinks
    assert skill_link_state(good, target) == "degraded"
    good.write_text("../elsewhere/s\n", encoding="utf-8")
    assert skill_link_state(good, target) == "broken"
    good.unlink()
    good.mkdir()  # a copy is not one source of truth
    assert skill_link_state(good, target) == "broken"


def test_project_skills_are_exposed_by_symlink_not_copy() -> None:
    """One source of truth: skills/<name> -> ../.claude/skills/<name> for every project skill."""
    project = sorted(p.name for p in PROJECT_SKILLS.iterdir() if p.is_dir())
    assert project, "no project skills to expose"
    for name in project:
        link = PLUGIN_SKILLS / name
        state = skill_link_state(link, PROJECT_SKILLS / name)
        if state == "degraded":
            warnings.warn(
                f"DEGRADED CHECKOUT: {link} is a symlink checked out as text (clone without "
                "core.symlinks / Developer Mode); the plugin will not load this skill. "
                "See docs/PLUGIN.md 'Windows checkouts'.",
                stacklevel=1,
            )
            continue
        assert state == "symlink", f"{link}: expected a symlink into .claude/skills/, got {state}"
        assert (link / "SKILL.md").is_file()
    stray = sorted(
        p.name for p in PLUGIN_SKILLS.iterdir() if p.is_symlink() and p.name not in project
    )
    assert not stray, f"symlinks in skills/ that point outside .claude/skills/: {stray}"


def test_plugin_skills_carry_the_plugin_root_token_not_the_legacy_placeholder() -> None:
    """Claude Code substitutes ${CLAUDE_PLUGIN_ROOT} in skill content (reference, "Environment
    variables"); the legacy __BORROMEANRINGS_HOME__ token would reach the model verbatim."""
    for skill in sorted(PLUGIN_SKILLS.glob("*/SKILL.md")):
        assert "__BORROMEANRINGS_HOME__" not in skill.read_text(encoding="utf-8"), skill


def test_install_global_substitutes_the_plugin_root_token(tmp_path: Path) -> None:
    """The same skill file must work installed by hand: install-global.sh resolves the token."""
    config_dir = tmp_path / "claude-config"
    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(config_dir))
    subprocess.run(
        ["bash", str(HOME / "install-global.sh")], check=True, capture_output=True, env=env
    )
    installed = (config_dir / "skills" / "borromeanrings" / "SKILL.md").read_text(encoding="utf-8")
    assert PLUGIN_ROOT_TOKEN not in installed
    assert f"{HOME}/init.sh" in installed


def test_install_global_warns_on_a_symlink_checked_out_as_text(tmp_path: Path) -> None:
    """A degraded checkout must be named, not skipped silently (PR #166 review)."""
    home = tmp_path / "home"
    (home / "skills").mkdir(parents=True)
    (home / "skills" / "borromeanrings-status").write_text(
        "../.claude/skills/borromeanrings-status\n"
    )
    (home / "install-global.sh").write_bytes((HOME / "install-global.sh").read_bytes())
    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(tmp_path / "cfg"))
    proc = subprocess.run(
        ["bash", str(home / "install-global.sh")], capture_output=True, text=True, env=env
    )
    assert proc.returncode == 0
    assert "core.symlinks" in proc.stderr and "borromeanrings-status" in proc.stderr
