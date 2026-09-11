"""Pure core of the toolchain-pin guarantee. ADR-0077."""

from meta_harness.toolchain import (
    TOOLS,
    Drift,
    Tool,
    canonical,
    drifts,
    parse_pins,
    parse_version,
    render,
    unpinned,
)

_TOOLS = (Tool("ruff", ("ruff",)), Tool("pip-audit", ("python3", "-m", "pip_audit")))


def test_canonical_folds_case_and_separator_runs() -> None:
    assert canonical("Pip__Audit") == "pip-audit"
    assert canonical("pip.audit") == "pip-audit"
    assert canonical("ruff") == "ruff"


def test_parse_version_reads_every_shape_the_gate_tools_print() -> None:
    assert parse_version("ruff 0.15.8") == "0.15.8"
    assert parse_version("mypy 1.19.1 (compiled: yes)") == "1.19.1"
    assert parse_version("mutmut, version 3.6.0") == "3.6.0"
    assert parse_version("pytest 9.0.3") == "9.0.3"
    assert parse_version("tool 2.1.0rc1") == "2.1.0rc1"
    assert parse_version("tool 1.2.post1") == "1.2.post1"
    assert parse_version("tool 1.2.dev3") == "1.2.dev3"


def test_parse_version_is_none_when_there_is_no_version() -> None:
    assert parse_version("command not found") is None
    assert parse_version("") is None


def test_parse_pins_keeps_exact_pins_and_ignores_the_rest() -> None:
    pins = parse_pins(
        "\n".join(
            [
                "# a comment",
                "",
                "ruff==0.15.8",
                "mypy>=1.10",  # a range is not a pin
                "  Pip_Audit == 2.10.0  ",
                'pytest==9.0.3 ; python_version >= "3.12"',
                "bandit==1.9.4  # trailing",
                "-r other.txt",
            ]
        )
    )
    assert pins == {
        "ruff": "0.15.8",
        "pip-audit": "2.10.0",
        "pytest": "9.0.3",
        "bandit": "1.9.4",
    }


def test_no_drift_when_observed_matches_declared() -> None:
    declared = {"ruff": "0.15.8", "pip-audit": "2.10.0"}
    observed = {"ruff": "0.15.8", "pip-audit": "2.10.0"}
    assert drifts(declared, observed, _TOOLS) == ()


def test_a_newer_release_than_the_pin_is_a_drift() -> None:
    found = drifts({"ruff": "0.15.8"}, {"ruff": "0.16.7"}, _TOOLS)
    assert found == (Drift("ruff", "0.15.8", "0.16.7"),)
    assert "runs 0.16.7" in found[0].reason


def test_an_unreadable_version_is_a_drift_not_a_pass() -> None:
    found = drifts({"ruff": "0.15.8"}, {"ruff": None}, _TOOLS)
    assert found == (Drift("ruff", "0.15.8", None),)
    assert "could not read a version" in found[0].reason


def test_a_tool_absent_from_the_observation_is_a_drift() -> None:
    assert drifts({"ruff": "0.15.8"}, {}, _TOOLS) == (Drift("ruff", "0.15.8", None),)


def test_a_tool_with_no_pin_is_reported_as_unpinned_not_as_drift() -> None:
    assert drifts({"ruff": "0.15.8"}, {"ruff": "0.15.8"}, _TOOLS) == ()
    assert unpinned({"ruff": "0.15.8"}, _TOOLS) == ("pip-audit",)
    assert unpinned({"ruff": "1", "pip-audit": "2"}, _TOOLS) == ()


def test_render_names_both_failure_modes_and_is_empty_when_clean() -> None:
    assert render((), ()) == ""
    body = render((Drift("ruff", "0.15.8", "0.16.7"),), ("mypy",))
    assert "ruff: pinned 0.15.8, but the gate runs 0.16.7" in body
    assert "mypy: no exact pin declared" in body


def test_the_tools_table_is_not_empty() -> None:
    assert {t.dist for t in TOOLS} >= {"ruff", "mypy", "pytest"}
