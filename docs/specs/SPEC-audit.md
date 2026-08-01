# SPEC — Dependency CVE audit (heavy)

**Status:** Implemented · **Realized by:** `src/meta_harness/audit.py`,
`checks/ci/70_pip_audit.sh`, `[audit]` · ADR-0034

## Problem

Nothing checked dependencies for known CVEs (matrix row **C —
dependency/CVE audit**). A dependency with a published advisory is a live hole.

## Contract

`70_pip_audit` is a **heavy** (CI-tier) check: it runs `pip-audit --format json`
over the installed closure and fails on any known vulnerability.

- **Heavy, not T0:** pip-audit hits the network and audits the whole environment,
  so it runs only under `verify.sh --heavy` (CI), where the environment is exactly
  the project's declared deps (`pip install -e .[dev]`). It never runs on the fast
  Stop gate.
- **Ignores** (`[audit]`): `ignore_packages` drops base packaging tooling
  (`pip`/`setuptools`/`wheel` — the installer, not a declared dep) and
  `ignore_vulns` drops explicitly-accepted CVE ids. Without these the gate would
  flap on CVEs the project can't act on (e.g. `pip` itself).
- **Fail-closed:** an empty/absent pip-audit report (tool or network failure) is a
  failure, never a silent pass.

## Design

Pure `parse_pip_audit(json, ignore_packages, ignore_vulns)` (JSON in, findings
out), 100% covered, tolerant of both the `{dependencies: [...]}` and bare-list
shapes. The check script runs the tool; the module decides. Validated against
borromeanRings's real closure in a clean venv → 0 findings after ignoring `pip`.

## borromeanRings config

```toml
[checks]
heavy = ["70_pip_audit"]
[audit]
ignore_packages = ["pip", "setuptools", "wheel"]
ignore_vulns = []
```
