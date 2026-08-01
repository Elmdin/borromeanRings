"""Dependency license compliance — parse ``pip-licenses`` JSON, deny incompatible
licenses.

A copyleft (GPL/AGPL/SSPL) dependency can force the whole project's license
(matrix row **C — license compliance**). This is a **heavy** (CI-tier) check: it
reads the installed closure, so it runs in CI's clean environment.

Denylist, not allowlist: license *strings* vary wildly ("MIT" vs "MIT License"
vs "Expat"), so enumerating every acceptable spelling is brittle. Instead the
project declares the handful of **incompatible** patterns to reject
(`[licenses].deny`, case-insensitive substring), with `allow_packages` for
vetted exceptions. Pure parse/decide here; the check script runs the tool. See
docs/specs/SPEC-licenses.md and ADR-0035.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class PackageLicense:
    """A dependency and its declared license string."""

    name: str
    version: str
    license: str


@dataclass(frozen=True)
class LicenseViolation:
    """A dependency whose license matched a declared deny pattern."""

    name: str
    version: str
    license: str
    matched: str


def parse_pip_licenses(json_text: str) -> list[PackageLicense]:
    """Parse ``pip-licenses --format=json`` into ``PackageLicense`` rows."""
    return [
        PackageLicense(
            name=row.get("Name", ""),
            version=row.get("Version", ""),
            license=row.get("License", ""),
        )
        for row in json.loads(json_text)
    ]


def license_violations(
    packages: list[PackageLicense],
    *,
    deny: tuple[str, ...],
    allow_packages: tuple[str, ...] = (),
) -> list[LicenseViolation]:
    """Packages whose license matches a ``deny`` pattern (case-insensitive
    substring) and are not in ``allow_packages``."""
    allow = {p.lower() for p in allow_packages}
    violations: list[LicenseViolation] = []
    for pkg in packages:
        if pkg.name.lower() in allow:
            continue
        lower = pkg.license.lower()
        for pattern in deny:
            if pattern.lower() in lower:
                violations.append(LicenseViolation(pkg.name, pkg.version, pkg.license, pattern))
                break
    return violations
