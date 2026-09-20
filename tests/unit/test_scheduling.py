"""The rule that decides which tests may run beside which (#253, ADR-0086).

The suite runs in parallel, and two of its files gate the SAME in-repo project and then
read "the newest run directory" out of it. Side by side, each read the other's run — the
first parallel run of this suite failed exactly there. Grouping is how that is prevented,
so the rule is worth a test of its own rather than a comment in a conftest.
"""

from __future__ import annotations

import pytest
from _scheduling import GROUP_ATTRIBUTE, group_for


def test_a_module_that_declares_nothing_is_its_own_group() -> None:
    """A file's tests stay together: most build a fixture project once, per module."""
    assert group_for("tests/integration/test_fast_lane.py") == "tests/integration/test_fast_lane.py"


def test_modules_that_share_a_resource_share_a_group() -> None:
    both = [
        group_for("tests/integration/test_example_governed.py", "examples-textkit"),
        group_for("tests/integration/test_harness_version_stamp.py", "examples-textkit"),
    ]

    assert both[0] == both[1] == "examples-textkit"


@pytest.mark.parametrize("declared", [None, "", "   ", 3, True, ["a"]])
def test_anything_that_is_not_a_name_falls_back_to_the_file(declared: object) -> None:
    """A typo'd declaration must not collapse the whole suite onto one worker, nor
    silently group unrelated files: it degrades to the safe default."""
    assert group_for("tests/unit/test_spine.py", declared) == "tests/unit/test_spine.py"


def test_surrounding_whitespace_in_a_declaration_is_not_a_different_group() -> None:
    assert group_for("a.py", " examples-textkit ") == group_for("b.py", "examples-textkit")


def test_the_attribute_modules_declare_is_named_here_once() -> None:
    assert GROUP_ATTRIBUTE == "XDIST_GROUP"
