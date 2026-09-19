# Matrix #4 — Operational / SRE

Scope: what a *deployed* artefact must carry to be run safely — container hygiene,
configuration, health, observability, release safety and incident learning. Rows O1–O3 are
derivable from the Dockerfile today; the rest need either a declared service archetype (#79)
or runtime telemetry. Conventions: [`README.md`](README.md).

| Row | Criterion (binary or ratchet) | Enforced by | Buildability | Source |
|---|---|---|---|---|
| O1 | The final image stage runs as a non-root `USER` (least privilege) | ✅ `14_container` rule `non_root` (ADR-0044) | now | CIS Docker Benchmark v1.6.0 §4.1 ("Ensure that a user for the container has been created"); Google SRE Book (Beyer et al., 2016) ch. 8 "Release Engineering" (hermetic, reproducible builds) |
| O2 | Every external `FROM` pins a non-`latest` tag or a digest (reproducible builds) | ✅ `14_container` rule `pinned_base` | now | CIS Docker Benchmark §4.2 (trusted base images); reproducible-builds.org definition; SRE Book ch. 8 (hermeticity) |
| O3 | A long-running service image declares a `HEALTHCHECK` (liveness is probeable) | ✅ `14_container` rule `healthcheck` (per-project `[container].require`; a run-and-exit image omits it, ADR-0044) | now | CIS Docker Benchmark §4.6 ("Ensure that HEALTHCHECK instructions have been added"); Kubernetes docs "Liveness, Readiness and Startup Probes" |
| O4 | The engineering surround a deployable needs exists: Dockerfile, CI workflow, licence, README (presence-gated, declared per project) | ✅ `05_hygiene` (`[hygiene].requires`; ADR-0012) | now | SRE Book ch. 8; Twelve-Factor App factor V (build, release, run) |
| O5 | Configuration and secrets come from the environment or a secret store, never from source | ✅ `12_secrets` / `74_secret_history` for the *negative* half (nothing in source); the positive half (env/secret-manager usage declared) is gap → #79 (`web-api` profile "Secrets management") | archetype | Twelve-Factor App factor III (config in the environment); OWASP ASVS 4.0.3 V14.1 (build and deploy) |
| O6 | A service exposes distinct liveness and readiness endpoints that respond | gap → #79 (`web-api` profile "Health/readiness endpoint") | archetype | Kubernetes "Liveness, Readiness and Startup Probes"; SRE Book ch. 6 "Monitoring Distributed Systems" |
| O7 | Logs are structured events written to stdout/stderr (no file-based logging in the container) | gap → #79 | archetype | Twelve-Factor App factor XI (logs as event streams); SRE Book ch. 6 |
| O8 | The four golden signals (latency, traffic, errors, saturation) are exported as metrics | gap → #79 / #138 | archetype + telemetry | SRE Book ch. 6 "The Four Golden Signals" |
| O9 | SLOs are declared in the repo as data (indicator, objective, window), and every alert references an SLO | gap → #157 | archetype | SRE Book ch. 4 "Service Level Objectives"; SRE Workbook (2018) ch. 2 "Implementing SLOs", ch. 5 "Alerting on SLOs" |
| O10 | Error-budget consumption is recorded per window; a release while the budget is exhausted is refused by policy | gap → #157 | telemetry | SRE Book ch. 3 "Embracing Risk" (error budgets); SRE Workbook ch. 2 |
| O11 | Every release can be rolled back: the previous artefact is retained and a rollback command exists and is exercised | gap → #79 (deploy archetype) | archetype | SRE Book ch. 8; DORA capability "Deployment automation" |
| O12 | Releases are canaried (a fraction of traffic on the new version with an automatic abort) | gap → #157 | telemetry | SRE Workbook ch. 16 "Canarying Releases"; SRE Book ch. 8 |
| O13 | Outbound calls carry timeouts and bounded retries (no unbounded waits that cascade) | gap → #130 (`api_contracts` rules `required_arg` / `must_check` can express "every HTTP call passes a timeout") | now (AST-derivable once #130 lands) | SRE Book ch. 22 "Addressing Cascading Failures" (timeouts, retries, load shedding) |
| O14 | Every incident produces a blameless postmortem document with action items tracked as issues | gap → #157 (process; presence of a `docs/postmortems/` entry linked from the incident) | telemetry | SRE Book ch. 15 "Postmortem Culture: Learning from Failure" |
| O15 | On-call playbooks exist for each alert (an alert without a playbook fails the alert-definition check) | gap → #157 | archetype | SRE Book ch. 11 "Being On-Call" (playbooks), ch. 14 "Managing Incidents" |
| O16 | The gate's own operational honesty: a check that inspected nothing reports `noop`, and a run leaning on `noop` says so | ✅ `_lib.sh` `emit_noop` + `verdict.NON_FAILING_STATUSES` + `status.sh` (ADR-0049) | now | SRE Book ch. 6 ("symptoms versus causes"; a green that hides absence is a monitoring defect) |

## Notes

- **The buildable slice is shipped.** O1–O3 are the deterministic, threshold-free rows ADR-0044
  identified; AutoApply (a real service in the roster) is the justified need and gets a
  live `healthcheck` finding on opt-in.
- **Why most rows are `archetype`.** A library or CLI has no liveness, no SLO and nothing to
  roll back. Until a project declares `[project].kind = "service"` (or similar, #79) these
  rows are legitimately `noop`. The archetype declaration is what makes them *required*.
- **Timeouts (O13) are the one runtime row that is statically decidable**: "every call to
  `requests.get` passes `timeout=`" is exactly the `required_arg` rule #130 proposes, so O13 is
  wired there rather than to a new SRE check.
