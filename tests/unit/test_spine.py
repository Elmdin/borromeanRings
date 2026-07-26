"""Tests for the policy spine loader (docs/specs/SPEC-spine.md §5)."""

from pathlib import Path

import pytest

from meta_harness.spine import load_config


def _write(tmp_path: Path, body: str) -> Path:
    config = tmp_path / "borromeanrings.toml"
    config.write_text(body, encoding="utf-8")
    return config


def test_loads_required_checks_and_context(tmp_path: Path) -> None:
    config = _write(
        tmp_path,
        '[checks]\nrequired = ["00_build", "40_test"]\n[context]\naccount = "x"\n',
    )
    loaded = load_config(config)
    assert loaded.required_checks == ("00_build", "40_test")
    assert loaded.context["account"] == "x"


def test_changelog_loaded_and_defaults_off(tmp_path: Path) -> None:
    declared = _write(
        tmp_path,
        '[checks]\nrequired = ["00_build"]\n[changelog]\n'
        'enabled = true\npath = "HISTORY.md"\nrequire_entry_on_src_change = true\n',
    )
    cfg = load_config(declared)
    assert cfg.changelog_enabled is True
    assert cfg.changelog_path == "HISTORY.md"
    assert cfg.changelog_require_entry_on_src_change is True

    default = _write(tmp_path, '[checks]\nrequired = ["00_build"]\n')
    off = load_config(default)
    assert off.changelog_enabled is False
    assert off.changelog_path == "CHANGELOG.md"
    assert off.changelog_require_entry_on_src_change is False


def test_architecture_contracts_parse(tmp_path: Path) -> None:
    config = _write(
        tmp_path,
        '[checks]\nrequired = ["00_build"]\n\n'
        "[architecture]\n"
        'leaves = ["spine"]\n'
        'private = ["deep_research"]\n'
        'forbidden = [["hygiene", "layout"], ["a", "b"]]\n'
        "forbid_cycles = true\n",
    )
    loaded = load_config(config)
    assert loaded.architecture_leaves == ("spine",)
    assert loaded.architecture_private == ("deep_research",)
    assert loaded.architecture_forbidden == (("hygiene", "layout"), ("a", "b"))
    assert loaded.architecture_forbid_cycles is True


def test_architecture_defaults_off(tmp_path: Path) -> None:
    config = _write(tmp_path, '[checks]\nrequired = ["00_build"]\n')
    loaded = load_config(config)
    assert loaded.architecture_leaves == ()
    assert loaded.architecture_forbidden == ()
    assert loaded.architecture_forbid_cycles is False


def test_critic_judge_command_loaded_and_defaults_empty(tmp_path: Path) -> None:
    declared = _write(
        tmp_path,
        '[checks]\nrequired = ["00_build"]\n[critic]\njudge_command = "claude -p"\n',
    )
    assert load_config(declared).critic_judge_command == "claude -p"
    default = _write(tmp_path, '[checks]\nrequired = ["00_build"]\n')
    assert load_config(default).critic_judge_command == ""


def test_heavy_checks_loaded_and_default_empty(tmp_path: Path) -> None:
    declared = _write(
        tmp_path,
        '[checks]\nrequired = ["00_build"]\nheavy = ["60_mutation", "70_audit"]\n',
    )
    assert load_config(declared).heavy_checks == ("60_mutation", "70_audit")
    default = _write(tmp_path, '[checks]\nrequired = ["00_build"]\n')
    assert load_config(default).heavy_checks == ()


def test_audit_ignores_loaded_and_default_empty(tmp_path: Path) -> None:
    declared = _write(
        tmp_path,
        '[checks]\nrequired = ["00_build"]\n[audit]\n'
        'ignore_packages = ["pip", "setuptools"]\nignore_vulns = ["PYSEC-1"]\n',
    )
    cfg = load_config(declared)
    assert cfg.audit_ignore_packages == ("pip", "setuptools")
    assert cfg.audit_ignore_vulns == ("PYSEC-1",)
    default = _write(tmp_path, '[checks]\nrequired = ["00_build"]\n')
    assert load_config(default).audit_ignore_packages == ()


def test_license_policy_loaded_and_default_empty(tmp_path: Path) -> None:
    declared = _write(
        tmp_path,
        '[checks]\nrequired = ["00_build"]\n[licenses]\n'
        'deny = ["GPL", "AGPL"]\nallow_packages = ["special"]\n',
    )
    cfg = load_config(declared)
    assert cfg.license_deny == ("GPL", "AGPL")
    assert cfg.license_allow_packages == ("special",)
    default = _write(tmp_path, '[checks]\nrequired = ["00_build"]\n')
    assert load_config(default).license_deny == ()


def test_critic_rubrics_loaded_and_default_empty(tmp_path: Path) -> None:
    declared = _write(
        tmp_path,
        '[checks]\nrequired = ["00_build"]\n[critic]\nrubrics = ["naming", "security"]\n',
    )
    assert load_config(declared).critic_rubrics == ("naming", "security")
    default = _write(tmp_path, '[checks]\nrequired = ["00_build"]\n')
    assert load_config(default).critic_rubrics == ()


def test_enhancements_interests_loaded_and_default_empty(tmp_path: Path) -> None:
    declared = _write(
        tmp_path,
        '[checks]\nrequired = ["00_build"]\n[enhancements]\ninterests = ["model-routing"]\n',
    )
    assert load_config(declared).enhancements_interests == ("model-routing",)
    default = _write(tmp_path, '[checks]\nrequired = ["00_build"]\n')
    assert load_config(default).enhancements_interests == ()


def test_empty_required_is_fail_closed(tmp_path: Path) -> None:
    config = _write(tmp_path, "[checks]\nrequired = []\n")
    with pytest.raises(ValueError, match="fail-closed"):
        load_config(config)


def test_context_defaults_to_empty(tmp_path: Path) -> None:
    config = _write(tmp_path, '[checks]\nrequired = ["00_build"]\n')
    loaded = load_config(config)
    assert loaded.required_checks == ("00_build",)
    assert dict(loaded.context) == {}
    assert loaded.prompt_rewriting_enabled is False


def test_prompt_rewriting_toggle(tmp_path: Path) -> None:
    config = _write(
        tmp_path,
        '[checks]\nrequired = ["00_build"]\n[prompt_rewriting]\nenabled = true\n',
    )
    assert load_config(config).prompt_rewriting_enabled is True


def test_hygiene_requires_loaded(tmp_path: Path) -> None:
    config = _write(
        tmp_path,
        '[checks]\nrequired = ["00_build"]\n[hygiene]\nrequires = ["README.md", "LICENSE"]\n',
    )
    assert load_config(config).hygiene_requires == ("README.md", "LICENSE")


def test_project_targeting_loaded_with_defaults(tmp_path: Path) -> None:
    declared = _write(
        tmp_path,
        '[checks]\nrequired = ["00_build"]\n[project]\npackage = "widget"\nsrc_dir = "lib"\n',
    )
    cfg = load_config(declared)
    assert (cfg.package, cfg.src_dir, cfg.tests_dir) == ("widget", "lib", "tests")

    default = _write(tmp_path, '[checks]\nrequired = ["00_build"]\n')
    assert (load_config(default).package, load_config(default).src_dir) == ("", "src")
    assert load_config(default).language == "python"  # default


def test_language_selects_check_set(tmp_path: Path) -> None:
    declared = _write(
        tmp_path, '[checks]\nrequired = ["00_build"]\n[project]\nlanguage = "typescript"\n'
    )
    assert load_config(declared).language == "typescript"


def test_git_identity_loaded_and_defaults_empty(tmp_path: Path) -> None:
    declared = _write(
        tmp_path,
        '[checks]\nrequired = ["00_build"]\n[git]\nname = "wimaan3"\nemail = "a@b.c"\n',
    )
    cfg = load_config(declared)
    assert (cfg.git_name, cfg.git_email) == ("wimaan3", "a@b.c")

    default = _write(tmp_path, '[checks]\nrequired = ["00_build"]\n')
    assert (load_config(default).git_name, load_config(default).git_email) == ("", "")


def test_layout_loaded_and_defaults_off(tmp_path: Path) -> None:
    declared = _write(
        tmp_path,
        '[checks]\nrequired = ["00_build"]\n[layout]\n'
        'specs_dir = "docs/specs"\nroot_doc_allowlist = ["README.md"]\n'
        'test_grouping_threshold = 15\ntest_groups = ["unit", "e2e"]\n',
    )
    cfg = load_config(declared)
    assert cfg.specs_dir == "docs/specs"
    assert cfg.root_doc_allowlist == ("README.md",)
    assert cfg.test_grouping_threshold == 15
    assert cfg.test_groups == ("unit", "e2e")

    default = _write(tmp_path, '[checks]\nrequired = ["00_build"]\n')
    off = load_config(default)
    assert (off.specs_dir, off.root_doc_allowlist) == ("", ())
    assert (off.test_grouping_threshold, off.test_groups) == (0, ())


def test_collaboration_loaded_and_defaults_off(tmp_path: Path) -> None:
    declared = _write(
        tmp_path,
        '[checks]\nrequired = ["00_build"]\n[collaboration]\n'
        'protected_branches = ["main", "dev"]\n'
        'branch_patterns = ["feat/*", "fix/*"]\n'
        'commit_types = ["feat", "fix"]\n'
        "subject_max_length = 72\n",
    )
    cfg = load_config(declared)
    assert cfg.collaboration_protected_branches == ("main", "dev")
    assert cfg.collaboration_branch_patterns == ("feat/*", "fix/*")
    assert cfg.collaboration_commit_types == ("feat", "fix")
    assert cfg.collaboration_subject_max_length == 72

    default = _write(tmp_path, '[checks]\nrequired = ["00_build"]\n')
    off = load_config(default)
    assert off.collaboration_protected_branches == ()
    assert off.collaboration_branch_patterns == ()
    assert off.collaboration_commit_types == ()
    assert off.collaboration_subject_max_length == 0
