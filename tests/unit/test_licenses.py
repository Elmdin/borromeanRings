"""License-compliance parsing + denylist. ADR-0035."""

from meta_harness.licenses import (
    LicenseViolation,
    PackageLicense,
    license_violations,
    parse_pip_licenses,
)

_SAMPLE = """
[
  {"Name": "clean-a", "Version": "1.0", "License": "MIT License"},
  {"Name": "clean-b", "Version": "2.0", "License": "Apache-2.0"},
  {"Name": "copyleft", "Version": "3.0", "License": "GPL-3.0"},
  {"Name": "network-copyleft", "Version": "4.0", "License": "GNU Affero General Public License v3"}
]
"""

_DENY = ("GPL-3.0", "Affero", "SSPL")


def test_parse_rows() -> None:
    pkgs = parse_pip_licenses(_SAMPLE)
    assert PackageLicense("clean-a", "1.0", "MIT License") in pkgs
    assert len(pkgs) == 4


def test_denies_copyleft() -> None:
    v = license_violations(parse_pip_licenses(_SAMPLE), deny=_DENY)
    names = {x.name for x in v}
    assert names == {"copyleft", "network-copyleft"}


def test_permissive_licenses_pass() -> None:
    v = license_violations(parse_pip_licenses(_SAMPLE), deny=_DENY)
    assert all(x.name not in {"clean-a", "clean-b"} for x in v)


def test_case_insensitive_match() -> None:
    pkgs = [PackageLicense("x", "1", "gpl-3.0")]
    assert license_violations(pkgs, deny=("GPL-3.0",))[0].matched == "GPL-3.0"


def test_allow_packages_exempts() -> None:
    v = license_violations(parse_pip_licenses(_SAMPLE), deny=_DENY, allow_packages=("copyleft",))
    names = {x.name for x in v}
    assert names == {"network-copyleft"}  # copyleft exempted


def test_reports_matched_pattern() -> None:
    v = license_violations([PackageLicense("p", "1", "MPL-2.0")], deny=("MPL",))
    assert v == [LicenseViolation("p", "1", "MPL-2.0", "MPL")]


def test_no_deny_patterns_passes_everything() -> None:
    assert license_violations(parse_pip_licenses(_SAMPLE), deny=()) == []
