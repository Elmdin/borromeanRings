"""The fast (interactive) lane's scope decisions. ADR-0081, issue #226.

Everything here guards one property in two directions: the fast lane narrows verification
ONLY where a project asked for it, and a narrowed run is always labelled as narrowed.
"""

from __future__ import annotations

import pytest

from meta_harness.lane import (
    FAST,
    FAST_LANE_NOTE,
    FULL,
    LANE_ENV,
    effective_lane,
    fast_lane_summary,
    fast_pytest_args,
    fast_test_paths,
    lane_from_env,
    resolve_lane,
    validate_fast_paths,
)
from meta_harness.spine import Config


def _config(*fast_paths: str) -> Config:
    return Config(required_checks=("40_test",), context={}, test_fast_paths=tuple(fast_paths))


def test_lane_is_full_unless_the_environment_says_exactly_fast() -> None:
    assert lane_from_env({}) == FULL
    assert lane_from_env({"OTHER": FAST}) == FULL
    assert lane_from_env({LANE_ENV: FAST}) == FAST
    # An unset, misspelled, cased, or forged value must never narrow verification.
    for forged in ("Fast", " fast", "fast ", "FAST", "1", "true", "heavy"):
        assert lane_from_env({LANE_ENV: forged}) == FULL, forged


def test_no_declaration_means_no_narrowing_in_any_lane() -> None:
    # The default for every project that configures nothing: the fast lane is a no-op.
    assert fast_test_paths(_config(), FAST) == ()
    assert fast_pytest_args(_config(), FAST) == ""


def test_declared_paths_apply_only_to_the_fast_lane() -> None:
    config = _config("tests/unit")
    assert fast_test_paths(config, FAST) == ("tests/unit",)
    assert fast_test_paths(config, FULL) == ()
    assert fast_pytest_args(config, FULL) == ""


def test_paths_reach_a_command_line_so_unsafe_ones_are_rejected() -> None:
    for unsafe in (
        "/etc/passwd",
        "../outside",
        "tests/../../etc",
        "tests/unit; rm -rf /",
        "tests/$(whoami)",
        "tests/unit && echo",
        "tests/unit|cat",
        "tests unit",
        "",
        "   ",
    ):
        with pytest.raises(ValueError):
            validate_fast_paths((unsafe,))


def test_safe_relative_paths_survive_validation() -> None:
    paths = ("tests/unit", "tests/unit/test_a.py", "src/pkg-1/tests", "tests_2")
    assert validate_fast_paths(paths) == paths
    assert validate_fast_paths(("  tests/unit  ",)) == ("tests/unit",)


def test_a_narrowed_result_names_itself_and_what_it_skipped() -> None:
    # Exact-shaped, not merely containing: the gate prints this verbatim beside the
    # status, and a label that reads as anything other than "partial" defeats the point.
    assert fast_lane_summary(("tests/unit",)) == "FAST LANE — only tests/unit; full suite pre-merge"
    assert fast_lane_summary(("a", "b")).startswith("FAST LANE — only a, b;")
    # The honesty contract: the note says what was not run AND where it still runs.
    assert FAST_LANE_NOTE.startswith("FAST LANE: a partial run.")
    assert FAST_LANE_NOTE.endswith("See ADR-0081.")
    assert "NOT run" in FAST_LANE_NOTE
    assert "coverage was NOT measured" in FAST_LANE_NOTE
    assert "CI before merge" in FAST_LANE_NOTE


def test_pytest_arguments_are_shell_quoted() -> None:
    # The check interpolates this into a shell command; a path with a space (rejected
    # today) or a dot-name must not split into two arguments if validation ever widens.
    assert fast_pytest_args(_config("tests/unit", "tests/e2e"), FAST) == "tests/unit tests/e2e"


def test_heavy_always_resolves_to_the_full_lane() -> None:
    # --heavy IS the pre-merge lane, so it is never narrowed — otherwise the one lane
    # that blocks a merge could be told to skip most of the suite.
    assert resolve_lane([], {}) == (FULL, False)
    assert resolve_lane(["--fast"], {}) == (FAST, False)
    assert resolve_lane(["--heavy"], {}) == (FULL, True)
    assert resolve_lane(["--fast", "--heavy"], {}) == (FULL, True)
    assert resolve_lane(["--heavy", "--fast"], {}) == (FULL, True)
    assert resolve_lane(["--fast"], {"BORROMEANRINGS_HEAVY": "1"}) == (FULL, True)
    # an unknown flag neither narrows nor escalates
    assert resolve_lane(["--verbose"], {}) == (FULL, False)
    # only an exact "1" in the env escalates; an unrelated variable never does
    assert resolve_lane([], {"BORROMEANRINGS_HEAVY": "0"}) == (FULL, False)
    assert resolve_lane(["--fast"], {"BORROMEANRINGS_HEAVY": "yes"}) == (FAST, False)
    assert resolve_lane([], {"BORROMEANRINGS_LANE": "1"}) == (FULL, False)


def test_a_run_is_reported_fast_only_if_it_actually_narrowed_anything() -> None:
    # Typing --fast in a project that declared nothing ran EVERYTHING; labelling that
    # result partial would mislead in the other direction. ADR-0081.
    assert effective_lane(_config(), FAST) == FULL
    assert effective_lane(_config("tests/unit"), FAST) == FAST
    assert effective_lane(_config("tests/unit"), FULL) == FULL
