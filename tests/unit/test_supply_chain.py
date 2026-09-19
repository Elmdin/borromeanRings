"""Supply-chain decision logic: lockfile integrity + pinned dependencies. ADR-0061.

Every case pins an exact value (status string, the offending requirement line), so a
mutant that flips an operator or drops a branch is caught, not merely "still returns
a report".
"""

from __future__ import annotations

import pytest

from meta_harness.supply_chain import (
    DEFAULT_MANIFESTS,
    LockfileVerdict,
    PinFinding,
    PinReport,
    lockfile_verdict,
    parse_requirement,
    pin_report,
    pin_status,
)

# --------------------------------------------------------------------------- lockfile


def test_no_lockfile_declared_is_noop_whatever_changed() -> None:
    verdict = lockfile_verdict(["pyproject.toml"], lockfile="")
    assert verdict == LockfileVerdict("noop", verdict.message)
    assert "no [supply_chain].lockfile declared" in verdict.message


def test_manifest_changed_without_lockfile_fails_naming_both_files() -> None:
    verdict = lockfile_verdict(["pyproject.toml", "src/x.py"], lockfile="uv.lock")
    assert verdict.status == "fail"
    assert "pyproject.toml" in verdict.message
    assert "uv.lock" in verdict.message
    assert "did not change" in verdict.message


def test_manifest_and_lockfile_both_changed_passes() -> None:
    verdict = lockfile_verdict(["pyproject.toml", "uv.lock"], lockfile="uv.lock")
    assert verdict.status == "pass"
    assert "uv.lock" in verdict.message


def test_lockfile_only_change_passes() -> None:
    verdict = lockfile_verdict(["uv.lock"], lockfile="uv.lock")
    assert verdict.status == "pass"


def test_no_manifest_change_passes_and_says_so() -> None:
    verdict = lockfile_verdict(["src/x.py", "README.md"], lockfile="poetry.lock")
    assert verdict.status == "pass"
    assert "no manifest" in verdict.message


def test_nothing_changed_passes() -> None:
    assert lockfile_verdict([], lockfile="requirements.lock").status == "pass"


def test_declared_lockfile_missing_from_tree_fails_closed() -> None:
    verdict = lockfile_verdict([], lockfile="uv.lock", lockfile_exists=False)
    assert verdict.status == "fail"
    assert "does not exist" in verdict.message
    assert "uv.lock" in verdict.message


def test_package_json_is_a_default_manifest() -> None:
    assert DEFAULT_MANIFESTS == ("pyproject.toml", "package.json")
    verdict = lockfile_verdict(["package.json"], lockfile="package-lock.json")
    assert verdict.status == "fail"
    assert "package.json" in verdict.message


def test_custom_manifest_list_replaces_the_default() -> None:
    # pyproject.toml is no longer a manifest when the project declares only setup.py.
    verdict = lockfile_verdict(["pyproject.toml"], lockfile="uv.lock", manifests=("setup.py",))
    assert verdict.status == "pass"
    verdict = lockfile_verdict(["setup.py"], lockfile="uv.lock", manifests=("setup.py",))
    assert verdict.status == "fail"


def test_paths_are_normalised_before_comparison() -> None:
    verdict = lockfile_verdict(["./pyproject.toml", "./uv.lock"], lockfile="./uv.lock")
    assert verdict.status == "pass"


def test_every_changed_manifest_is_named_in_the_failure() -> None:
    verdict = lockfile_verdict(["pyproject.toml", "package.json"], lockfile="uv.lock")
    assert verdict.status == "fail"
    assert "pyproject.toml, package.json" in verdict.message


# ------------------------------------------------------------------- requirement parse


@pytest.mark.parametrize(
    ("requirement", "name", "extras", "spec", "url", "marker"),
    [
        ("ruff>=0.6", "ruff", "", ">=0.6", "", ""),
        ("Ruff [lint,fmt] >= 0.6, < 1", "Ruff", "lint,fmt", ">= 0.6, < 1", "", ""),
        ("pytest", "pytest", "", "", "", ""),
        ('tomli>=2; python_version < "3.11"', "tomli", "", ">=2", "", 'python_version < "3.11"'),
        ("pkg @ https://x/y.whl", "pkg", "", "", "https://x/y.whl", ""),
        ("pkg (>=1, <2)", "pkg", "", ">=1, <2", "", ""),
    ],
)
def test_parse_requirement_fields(
    requirement: str, name: str, extras: str, spec: str, url: str, marker: str
) -> None:
    parsed = parse_requirement(requirement)
    assert parsed is not None
    assert (parsed.name, parsed.extras, parsed.specifier, parsed.url, parsed.marker) == (
        name,
        extras,
        spec,
        url,
        marker,
    )


def test_parse_requirement_rejects_garbage() -> None:
    assert parse_requirement("") is None
    assert parse_requirement("   ") is None
    assert parse_requirement(">=1.0") is None
    assert parse_requirement("-e .") is None


# ---------------------------------------------------------------------- pin status


@pytest.mark.parametrize(
    "requirement",
    [
        "ruff==0.6.1",
        "ruff===0.6.1",
        "ruff~=0.6",
        "ruff<1",
        "ruff>=0.6,<1",
        "ruff>=0.6, <=0.9",
        "ruff==0.6.*",
        "ruff[lint]>=0.6,<1",
        'ruff>=0.6,<1 ; python_version >= "3.10"',
        "ruff @ git+https://github.com/astral-sh/ruff@0123456789abcdef0123456789abcdef01234567",
        "ruff @ https://example.invalid/ruff-0.6.1.whl#sha256=deadbeef",
    ],
)
def test_pinned_forms(requirement: str) -> None:
    assert pin_status(requirement) == (True, "")


@pytest.mark.parametrize(
    ("requirement", "reason_fragment"),
    [
        ("ruff", "no version specifier"),
        ("ruff>=0.6", "only a lower bound"),
        ("ruff>0.6", "only a lower bound"),
        ("ruff!=0.6", "only a lower bound"),
        ("ruff>=0.6,!=0.7", "only a lower bound"),
        ("ruff @ git+https://github.com/astral-sh/ruff", "commit hash"),
        ("ruff @ git+https://github.com/astral-sh/ruff@main", "commit hash"),
        ("ruff>=", "unparseable"),
        ("ruff>=0.6,foo", "unparseable"),
        (">=1", "unparseable"),
    ],
)
def test_unpinned_forms_carry_the_reason(requirement: str, reason_fragment: str) -> None:
    pinned, reason = pin_status(requirement)
    assert pinned is False
    assert reason_fragment in reason


# ---------------------------------------------------------------------- pin report

_PYPROJECT = """
[project]
name = "demo"
dependencies = [
  "requests>=2.31,<3",
  "click",
  "rich>=13",
]

[project.optional-dependencies]
dev = ["pytest>=8", "ruff==0.6.1"]
docs = ["mkdocs<2"]
"""


def test_report_counts_runtime_deps_and_lists_each_unpinned_line() -> None:
    report = pin_report(_PYPROJECT)
    assert report == PinReport(
        inspected=3,
        findings=(
            PinFinding("project", "click", report.findings[0].reason),
            PinFinding("project", "rich>=13", report.findings[1].reason),
        ),
        dynamic=False,
    )
    assert "no version specifier" in report.findings[0].reason
    assert "only a lower bound" in report.findings[1].reason


def test_optional_groups_inspected_only_when_asked() -> None:
    report = pin_report(_PYPROJECT, pin_optional=True)
    assert report.inspected == 6
    assert [(f.group, f.requirement) for f in report.findings] == [
        ("project", "click"),
        ("project", "rich>=13"),
        ("dev", "pytest>=8"),
    ]


def test_no_dependencies_is_an_empty_report() -> None:
    report = pin_report('[project]\nname = "x"\n')
    assert report == PinReport(inspected=0, findings=(), dynamic=False)


def test_only_optional_deps_without_pin_optional_inspects_nothing() -> None:
    text = '[project]\nname = "x"\n[project.optional-dependencies]\ndev = ["pytest"]\n'
    assert pin_report(text).inspected == 0
    assert pin_report(text, pin_optional=True).inspected == 1


def test_dynamic_dependencies_are_flagged_not_silently_skipped() -> None:
    report = pin_report('[project]\nname = "x"\ndynamic = ["dependencies"]\n')
    assert report.dynamic is True
    assert report.inspected == 0


def test_dynamic_other_field_is_not_dynamic_dependencies() -> None:
    report = pin_report('[project]\nname = "x"\ndynamic = ["version"]\ndependencies = ["a==1"]\n')
    assert report.dynamic is False
    assert report.inspected == 1
    assert report.findings == ()


def test_unparseable_requirement_is_a_finding_not_a_crash() -> None:
    report = pin_report('[project]\nname = "x"\ndependencies = [">=1"]\n')
    assert report.inspected == 1
    assert report.findings[0].requirement == ">=1"
    assert "unparseable" in report.findings[0].reason


def test_invalid_toml_raises_value_error_with_context() -> None:
    with pytest.raises(ValueError, match="pyproject.toml"):
        pin_report("[project\n")


def test_non_list_dependencies_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="list of strings"):
        pin_report('[project]\ndependencies = "requests"\n')
    with pytest.raises(ValueError, match="list of strings"):
        pin_report("[project]\ndependencies = [1]\n")
