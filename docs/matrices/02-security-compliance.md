# Matrix #2 — Security & compliance

Scope: the project's *code, dependencies, secrets, build pipeline and licences* — what an
attacker or an auditor would ask about. Runtime hardening of a deployed service (TLS, authN/Z,
rate limiting) is an **archetype** concern and lives in #79's `web-api` profile; the container
rows are in matrix #4. Conventions: [`README.md`](README.md).

| Row | Criterion (binary or ratchet) | Enforced by | Buildability | Source |
|---|---|---|---|---|
| S1 | Static application security testing runs on every gate and any finding at/above the configured severity fails; scanning nothing is reported as `noop`, never `pass` | ✅ `50_security` (bandit on `[project].src_dir`; `noop` guard when no Python) | now | NIST SP 800-218 SSDF v1.1, PW.7 "Review and/or analyze human-readable code"; OpenSSF Scorecard check `SAST` |
| S2 | Every declared dependency is audited against a vulnerability database; a known CVE fails unless explicitly accepted by id | ✅ `70_pip_audit` (heavy lane; `[audit].ignore_vulns` by id; fails closed on a missing report) | now | OWASP ASVS 4.0.3 V14.2.1 (components up to date via a dependency checker); SSDF RV.1; Scorecard `Vulnerabilities` |
| S3 | No high-confidence secret (provider token, private-key block) in any tracked file; a project that cannot be enumerated fails, not passes | ✅ `12_secrets` (native; fails closed on a non-git dir — ADR-0032/0042) | now | OWASP ASVS 4.0.3 V2.10.4 (secrets not in source or repositories); OWASP Secrets Management Cheat Sheet |
| S4 | No high-confidence secret anywhere in reachable git history; a finding requires rotation and is acknowledged only by fingerprint | ✅ `74_secret_history` (heavy lane; `git rev-list --all` blobs; `[secrets].history_allow`) | now | ASVS V2.10.4; ADR-0042 |
| S5 | No dependency carries a licence matching the project's deny-list; exemptions are per vetted package | ✅ `72_licenses` (heavy lane; `[licenses].deny` substrings; off when deny is empty) | now | OpenChain ISO/IEC 5230:2020 (open-source licence compliance programme); SPDX licence identifiers |
| S6 | A machine-readable SBOM (CycloneDX or SPDX) is produced for each release and matches the declared dependency closure | gap → #58 (supply-chain hardening; SBOM sub-issue to be filed under #138) | now | NTIA "The Minimum Elements for a Software Bill of Materials" (July 2021); SSDF PS.3.2 (provenance data, e.g. SBOM) |
| S7 | Build provenance is attested (who built what from which commit) and verifiable | gap → #58 | telemetry (needs the CI build to sign) | SLSA v1.0 Build track L1–L3 (provenance exists / authentic / hardened); Scorecard `Signed-Releases` |
| S8 | Dependencies are pinned and a lockfile exists whose integrity the gate checks (a changed manifest without a changed lock fails) | gap → #58 | now | SSDF PW.4.1 (well-secured components, pinned); Scorecard `Pinned-Dependencies`; ASVS V14.2.4 (trusted repositories) |
| S9 | Automated dependency-update proposals are configured (the project cannot silently age) | gap → #58 (Dependabot acceptance criterion) | now (config presence) | Scorecard `Dependency-Update-Tool` |
| S10 | CI workflows pin third-party actions to commit SHAs and declare least-privilege `permissions:` for `GITHUB_TOKEN` | gap → #74 | now (workflow text) | Scorecard `Pinned-Dependencies`, `Token-Permissions`, `Dangerous-Workflow`; GitHub Docs "Security hardening for GitHub Actions" |
| S11 | The default branch is protected server-side: PR required, the gate is a required status check, no direct push | gap → #60 (local layer shipped: `pre_bash_guard.sh` denies `git commit`/`git push` on `[collaboration].protected_branches`, ADR-0021) | telemetry (repo settings, read via API) | Scorecard `Branch-Protection`; SSDF PS.1 (protect code from unauthorized changes) |
| S12 | Container image runs as non-root and pins its base image | ✅ `14_container` rules `non_root`, `pinned_base` — see matrix #4 rows O1–O2 | now | CIS Docker Benchmark v1.6.0 §4.1, §4.2 |
| S13 | Shell scripts (hooks, checks, entry points — executable supply chain) pass a static shell linter | gap → #52 (in flight on `feat/shellcheck-gate`, ADR-0050) | now | SSDF PW.7; #58 scope "review skills/hooks for unsafe patterns" |
| S14 | AI-generated code receives a security review distinct from the generator (a separate judge, fail-closed) | ⚠️ `56_critics` rubric `security` — seam shipped, dormant until `[critic].judge_command` is set (ADR-0030/0036); gap → #68 | now (agent-only: the user's own `claude -p`) | OWASP "LLM AI Cybersecurity & Governance Checklist" v1.1 (2024), AI-generated-code review item; `docs/ENFORCEMENT-COVERAGE.md` row J |
| S15 | Fuzzing or DAST runs on the heavy lane for projects that expose a parser or a network surface | gap → #138 (no sub-issue yet; archetype-gated by #79) | archetype | Scorecard `Fuzzing`; OWASP Web Security Testing Guide v4.2 |
| S16 | Every security finding the gate raises is tamper-evidently recorded (receipt + verdict history), so a "fixed" finding is provable | ✅ receipts + `last_verdict.json` + `verdict_history.jsonl` (`meta_harness.receipts`/`verdict`, ADR-0026/0046/0047) | now | SSDF RV.2 (assess, prioritise and remediate vulnerabilities — with records); ISO/IEC 27001:2022 A.8.8 (technical vulnerability management) |

## Notes

- **Language coverage.** S1 is Python-only today (`checks/python/`). The same row for
  TypeScript/Go is #67, not a new matrix row.
- **Why S6–S8 are `now`.** An SBOM, a lockfile and pinned actions are all *text the repo already
  contains or can generate offline*; they need no telemetry, only a check. They are the first
  rows to build (issue #138 acceptance: "every row buildable without telemetry has its own
  issue").
- **What is deliberately not here.** Runtime controls (authentication, rate limiting, input
  validation at HTTP boundaries, non-leaking error responses) are correct for a *service* and
  meaningless for a library or CLI. They are the `web-api` profile in #79 and will be rows of
  that archetype, unlocked by `[project].kind`.
