# ADR-0035 — Dependency license compliance on the heavy lane (pip-licenses)

**Status:** Accepted

## Context
No check caught an incompatible dependency license (matrix row **C**). A copyleft
(GPL/AGPL/SSPL) dependency can force the whole project's license — a real legal
risk for an Apache-2.0 project. Like CVE auditing, it reads the installed closure,
so it is a heavy (CI-tier) check.

## Decision
Add `72_licenses` + `meta_harness.licenses`: run `pip-licenses --format=json` in
CI and fail on any dependency whose license matches a declared **deny** pattern.
`[licenses].deny` (case-insensitive substrings) + `allow_packages` (vetted
exceptions). borromeanRings denies the GPL/AGPL/SSPL family. Off when `deny` is
empty.

## Alternatives considered
- **Allowlist of acceptable licenses** — rejected: license *strings* are wildly
  inconsistent ("MIT" / "MIT License" / "Expat"; "Apache-2.0" / "Apache Software
  License"), so an allowlist is brittle and rejects benign deps on spelling. A
  denylist targets the small, well-known set of *incompatible* families and is
  robust to spelling.
- **SPDX-normalize every license first** — cleaner in theory, rejected as
  overkill: it needs an SPDX mapping table (another dependency to maintain) for a
  check whose job is to reject a handful of known-bad patterns. `allow_packages`
  handles the rare ambiguous case.
- **Fail on `UNKNOWN` licenses** — considered; left **opt-in** (a project adds
  `UNKNOWN` to `deny`). borromeanRings's closure has two UNKNOWN-license packages
  that are in fact permissive; auto-failing them would block on metadata gaps, not
  real incompatibility.
- **Native license introspection** — rejected: reading each dist's metadata
  reliably is exactly what pip-licenses does; reimplementing it is worse.

## Consequences
- (+) A copyleft dependency now blocks the CI gate, naming the package + the deny
  pattern it matched, with an explicit vet path (`allow_packages`).
- (+) Pure `parse_pip_licenses` / `license_violations`, 100% covered; validated
  against borromeanRings's real closure (0 violations) in a clean venv.
- (−) Denylist ≠ full SPDX compatibility analysis — dual-licensed or exotic terms
  may need a human call (that's what `allow_packages` is for).
- (−) Depends on each dependency declaring its license honestly in metadata;
  `UNKNOWN` is surfaced but not failed by default.
