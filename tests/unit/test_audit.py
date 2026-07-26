"""Parsing of pip-audit JSON for the CVE heavy check. ADR-0034."""

from meta_harness.audit import VulnerablePackage, parse_pip_audit

_SAMPLE = """
{"dependencies": [
  {"name": "clean-pkg", "version": "1.0", "vulns": []},
  {"name": "bad-pkg", "version": "2.1", "vulns": [
    {"id": "PYSEC-2026-1", "fix_versions": ["2.2"]},
    {"id": "GHSA-xxxx", "fix_versions": []}
  ]},
  {"name": "pip", "version": "24.0", "vulns": [{"id": "PYSEC-2026-196", "fix_versions": []}]}
]}
"""


def test_flags_vulnerable_package() -> None:
    findings = parse_pip_audit(_SAMPLE)
    assert VulnerablePackage("bad-pkg", "2.1", ("PYSEC-2026-1", "GHSA-xxxx")) in findings
    # pip is not ignored by default here → also flagged
    assert any(f.name == "pip" for f in findings)


def test_clean_package_absent() -> None:
    assert all(f.name != "clean-pkg" for f in parse_pip_audit(_SAMPLE))


def test_ignore_packages_is_case_insensitive() -> None:
    findings = parse_pip_audit(_SAMPLE, ignore_packages=("PIP",))
    assert all(f.name != "pip" for f in findings)
    assert any(f.name == "bad-pkg" for f in findings)


def test_ignore_vulns_by_id() -> None:
    findings = parse_pip_audit(_SAMPLE, ignore_vulns=("PYSEC-2026-1",))
    bad = next(f for f in findings if f.name == "bad-pkg")
    assert bad.vuln_ids == ("GHSA-xxxx",)


def test_all_vulns_ignored_drops_package() -> None:
    findings = parse_pip_audit(
        _SAMPLE, ignore_packages=("pip",), ignore_vulns=("PYSEC-2026-1", "GHSA-xxxx")
    )
    assert findings == []


def test_accepts_top_level_list_shape() -> None:
    # pip-audit can emit a bare list depending on version/flags.
    findings = parse_pip_audit('[{"name": "x", "version": "1", "vulns": [{"id": "A"}]}]')
    assert findings == [VulnerablePackage("x", "1", ("A",))]


def test_no_vulns_anywhere() -> None:
    assert parse_pip_audit('{"dependencies": [{"name": "a", "version": "1", "vulns": []}]}') == []
