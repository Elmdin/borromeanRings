# SPEC — Dependency license compliance (heavy)

**Status:** Implemented · **Realized by:** `src/meta_harness/licenses.py`,
`checks/ci/72_licenses.sh`, `[licenses]` · ADR-0035

## Contract

`72_licenses` (heavy/CI) runs `pip-licenses --format=json` over the installed
closure and fails on any dependency whose license matches a declared **deny**
pattern.

- **Denylist, not allowlist:** `[licenses].deny` holds case-insensitive substring
  patterns for *incompatible* license families (GPL/AGPL/SSPL); so the spellings a
  license string takes in the wild (`GPL-3.0-only`, `GPLv3`, `GNU General Public License v3`) all match. `allow_packages` exempts vetted deps.
- **Opt-in:** off when `deny` is empty. Fail-closed on a missing pip-licenses
  report.
- Receipts name each offender + the deny pattern it matched.

## borromeanRings config

```toml
[checks]
heavy = ["60_mutation", "70_pip_audit", "72_licenses"]
[licenses]
deny = ["GPL-2", "GPL-3", "GPLv2", "GPLv3", "AGPL", "Affero", "SSPL", "GNU General Public"]
allow_packages = []
```

Validated against borromeanRings's real closure (clean venv) → **0 violations**.
Pure `parse_pip_licenses` / `license_violations`, 100% covered.


## Scope: the project's dependencies, not the machine's (#228)

`pip-licenses` reports every **installed** distribution. The check narrows that to
the project's own closure — everything declared in `pyproject.toml` (runtime,
every optional-dependency group, every dependency group) plus everything those
pull in, via `meta_harness.closure`. The receipt names the scope size, so a reader
can see what was judged.

Without the narrowing the verdict depends on what else happens to be installed:
measured on a developer machine, 14 GPL-licensed distributions were reported —
`semgrep`, `pynput`, `ndspy`, `shiboken6` — none of them dependencies of anything
being gated. Worse, the remedy the check prints (vet it into
`[licenses].allow_packages`) would then write a permanent exception into the
project's config for a package it never depended on.

Fail closed: if the closure cannot be determined, the check fails with that as the
reason rather than widening back to everything installed.
