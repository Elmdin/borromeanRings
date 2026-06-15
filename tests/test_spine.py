"""Tests for the policy spine loader (docs/SPEC-spine.md §5)."""

from pathlib import Path

import pytest

from meta_harness.spine import load_config


def _write(tmp_path: Path, body: str) -> Path:
    config = tmp_path / "borromeo.toml"
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
