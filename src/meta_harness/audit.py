"""Dependency CVE audit — parse ``pip-audit`` JSON, fail on known vulnerabilities.

A dependency with a published CVE is a live security hole (matrix row **C —
dependency/CVE audit**). This is a **heavy** (CI-tier) check: ``pip-audit`` hits
the network and audits the whole installed closure, so it runs in CI's clean
environment (which contains exactly the project's declared deps), never on the
fast Stop gate.

The parse/decide logic here is pure (JSON in, findings out) and unit-tested; the
check script runs the tool. Base packaging tooling (``pip``/``setuptools``/
``wheel``) and explicitly-accepted CVEs are ignorable — they are the environment's
infrastructure, not the project's declared supply chain, and would otherwise make
the gate flap on CVEs the project can't act on. See docs/specs/SPEC-audit.md and
ADR-0034.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class VulnerablePackage:
    """A dependency with one or more (non-ignored) known vulnerabilities."""

    name: str
    version: str
    vuln_ids: tuple[str, ...]


def parse_pip_audit(
    json_text: str,
    *,
    ignore_packages: tuple[str, ...] = (),
    ignore_vulns: tuple[str, ...] = (),
) -> list[VulnerablePackage]:
    """Vulnerable packages in ``pip-audit --format json`` output.

    ``ignore_packages`` (case-insensitive) and ``ignore_vulns`` (CVE ids) are
    dropped — for base tooling and explicitly-accepted advisories.
    """
    data = json.loads(json_text)
    dependencies = data.get("dependencies", []) if isinstance(data, dict) else data
    skip_pkgs = {p.lower() for p in ignore_packages}
    skip_vulns = set(ignore_vulns)

    findings: list[VulnerablePackage] = []
    for dep in dependencies:
        name = dep.get("name", "")
        if name.lower() in skip_pkgs:
            continue
        ids = [v.get("id", "") for v in dep.get("vulns", []) if v.get("id") not in skip_vulns]
        deduped = tuple(dict.fromkeys(i for i in ids if i))
        if deduped:
            findings.append(VulnerablePackage(name, dep.get("version", ""), deduped))
    return findings
