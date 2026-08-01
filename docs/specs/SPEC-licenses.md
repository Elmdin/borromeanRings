# SPEC — Dependency license compliance (heavy)

**Status:** Implemented · **Realized by:** `src/meta_harness/licenses.py`,
`checks/ci/72_licenses.sh`, `[licenses]` · ADR-0035

## Contract

`72_licenses` (heavy/CI) runs `pip-licenses --format=json` over the installed
closure and fails on any dependency whose license matches a declared **deny**
pattern.

- **Denylist, not allowlist:** `[licenses].deny` holds case-insensitive substring
  patterns for *incompatible* license families (GPL/AGPL/SSPL); robust to the wild
  variance in license strings. `allow_packages` exempts vetted deps.
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
