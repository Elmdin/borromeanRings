# borromeanRings — Enforcement Coverage Map

> **What this is.** The canonical answer to *"does borromeanRings truly consider and enforce
> software-engineering best practices — for any project?"* It enumerates **every** SWE quality
> dimension, the **mechanism** by which each can be enforced, and borromeanRings's **current status**.
> It is both a self-audit and the **backlog**: every ❌/⚠️ row is a candidate future gate.
>
> Grounded in the CS130 knowledge base (see the `cs130-se` skill; §-refs below point at its topics)
> and cross-linked to [`ROADMAP.md`](ROADMAP.md) (where items graduate) and
> [`VISION.md`](VISION.md) (the red line: enforce *outcomes*, never dictate the agent's decisions).
>
> Status legend: ✅ have · ⚠️ partial · ❌ missing.

## 1. The enforcement spectrum (the spine)

Every best practice lands on a spectrum of enforcement strength. borromeanRings's edge is **how far
down this spectrum it pushes each practice** — the lower the tier, the more objective and the
harder to game.

| Tier | Mechanism | Best for | Property |
|---|---|---|---|
| **T0** | Deterministic gate (pass/fail, fail-closed) | anything with a mechanical oracle | objective, fast, can't-argue |
| **T1** | Non-regression **ratchet** (metric may not regress vs. a recorded baseline) | continuous metrics with no natural threshold | no arbitrary target; blocks *drift* |
| **T2** | Semantic **critic** (separate model, rubric-scored, fail-closed) | judgments (intent, design, naming) | catches *intent*; probabilistic |
| **T3** | **Advisory** / human-gated (proposes; human decides) | irreversible or taste decisions | preserves autonomy (red line) |

**Two governing laws.**

1. **Push practices down the tiers.** Enforce each at the *lowest tier that can express it*, and
   move it lower as tooling allows. Example: *"good tests"* — vibes (T3) → coverage ratchet (T1) →
   **mutation** ratchet (T1, stronger) → assertion-density critic (T2). Never leave something at
   "advisory" when a ratchet can capture it. *(CS130 §8/§13, §15: "verify continuously;
   mutation > coverage".)*
2. **Right-size per project.** Not every row is active on every project — a throwaway script must
   not carry a fintech gate *(CS130 §3/§15: right-size to risk/reversibility)*. The **project
   profiler** (roadmap; workstream #4) selects *which rows are active at which tier* for a given
   project type. The profiler **selects** this matrix; the T1/T2 build **deepens** it.

## 2. The coverage matrix

> "Tier" is the *lowest* mechanism that faithfully expresses the practice. A practice may also be
> reinforced at a higher tier (e.g. tests-pass at T0 **and** a design critic at T2).

### A. Correctness & test quality — CS130 §8, §13
| Practice | Tier | Status | Notes |
|---|---|---|---|
| Tests pass | T0 | ✅ | `checks/…/40_test.sh` |
| Coverage non-regression | T1 | ❌ | **candidate** — no check exists (`.borromeanrings-coverage-baseline` was never wired; this row previously mis-claimed ✅). Buildable now; mutation is the stronger signal but coverage catches un-executed code |
| **Mutation score** (assertion/oracle strength) | T1 | ✅ | `checks/ci/60_mutation.sh` (heavy lane); ratchet 0.83 vs baseline 0.80; fail-closed on 0-evaluated (ADR-0022) |
| Property-based / metamorphic testing present | T1/T3 | ❌ | deferred — mutation testing already measures oracle strength |
| Boundary-value / equivalence design | T2 | ⚠️ | `56_critics` rubric `boundary_value` — advisory critic, dormant until a judge is wired (ADR-0036) |
| Flaky-test detection | T1 | ❌ | rerun variance; quarantine |
| Every bug-fix ships a regression test | T0/process | ⚠️ | stated in rules, not enforced |
| Test isolation / independence | T0 | ⚠️ | pytest fixtures; not asserted |
| Test-smell detection (assertion roulette, mystery guest) | T2 | ⚠️ | `56_critics` rubric `test_smell` — advisory critic (ADR-0036) |

### B. Static correctness & type safety — CS130 §6
| Typecheck | T0 | ✅ | mypy (`30_typecheck`) |
| Lint | T0 | ✅ | ruff (`20_lint`) |
| Dead-code detection | T0/T1 | ❌ | deliberately deferred — vulture is false-positive-prone on bash-invoked functions here (noise-gate) |
| Cyclomatic-complexity ceiling/ratchet | T1 | ✅ | `checks/python/32_complexity.sh` — native McCabe worst-case ratchet, no external tool (ADR-0031) |
| Coupling / fan-out ratchet | T1 | ✅ | `checks/python/33_coupling.sh` — worst-case efferent coupling over the internal import graph, native (ADR-0038) |
| Duplication ratchet | T1 | ❌ | deliberately deferred — low value on a small, clean codebase |

### C. Security — CS130 §14
| Static SAST | T0 | ✅ | bandit (`50_security`) |
| Dependency / CVE audit | T0 | ✅ | `checks/ci/70_pip_audit.sh` (heavy lane) — pip-audit, `[audit]` ignores (ADR-0034) |
| Secret scanning | T0 | ✅ | `checks/shared/12_secrets.sh` — native high-confidence scan (tracked files); gitleaks (entropy) is the heavy-lane follow-up (ADR-0032). **Hardening candidate:** fails vacuously on a non-git dir (empty `git ls-files`) — a "can't-scan ≠ nothing-to-find" gap found in rollout (spaceThink) |
| Git-history secret scan | T0 | ❌ | candidate — a deleted-then-committed secret stays compromised; scan history, not just HEAD |
| Pinned deps / lockfile integrity / SBOM | T0 | ✅ | `checks/ci/78_pins.sh` (upper bound / exact pin per requirement), `checks/ci/76_lockfile.sh` (manifest change ⇒ lockfile change; `noop` here — no lockfile), `sbom.sh` (CycloneDX 1.5, stdlib, unsigned) — ADR-0061. Signing/provenance + Dependabot are maintainer decisions (CI-dependent; exact config in the ADR) |
| License compliance | T0 | ✅ | `checks/ci/72_licenses.sh` (heavy lane) — pip-licenses denylist (ADR-0035) |
| Fuzzing / DAST | T1/T3 | ❌ | |

### D. Design & architecture — CS130 §4, §11
| **Dependency-direction / architecture fitness functions** | T0 | ✅ | `checks/python/35_architecture.sh` — native import-graph contracts: leaves/private/forbidden/acyclic (ADR-0027) |
| Layering / information-hiding | T0 | ✅ | `35_architecture` now enforces *dependency* rules (not just file layout) (ADR-0027) |
| Coupling/cohesion metrics | T1 | ✅ | `checks/python/33_coupling.sh` — worst-case fan-out ratchet (ADR-0038) |
| ADR present for load-bearing decisions | T0/T3 | ⚠️ | 41 ADRs by convention (`docs/adr`), not gated — a candidate T0 gate |
| Design-doc for N-file features | T0/T3 | ⚠️ | rule only |
| Public-API breaking-change detection | T1 | ✅ | `checks/python/34_api_diff.sh` — signature diff vs merge-base; fails on removed symbol / renamed param / new required arg unless `[api].allow_breaking`; dogfooded on `examples/textkit` (ADR-0040) |
| Behavioral / type-aware API breaks | T1/T2 | ❌ | candidate — `34_api_diff` is signature-shape only |

### E. Code smells & maintainability — CS130 §6, §9
| Function/file size, nesting depth | T0 | ⚠️ | partial via ruff; nesting not bounded |
| Naming quality, feature envy, long-param, primitive obsession | T2 | ⚠️ | `56_critics` rubric `naming` — advisory critic (ADR-0036) |

### F. Requirements & traceability — CS130 §1, §15
| Story → test traceability | T2 | ❌ | "trace each test to a decision to a requirement" |
| Spec present for features | T0 | ⚠️ | rule only (see [`SPEC-*`](specs/)) |
| Acceptance criteria as Given/When/Then tests | T3 | ❌ | |
| Requirements coverage | T2 | ❌ | |

### G. Documentation — CS130 §10
| Docstring / API-doc coverage | T1 | ✅ | `checks/python/45_docstrings.sh` — native ratchet at 1.0 (ADR-0029) |
| **Doc-drift** (docs match code) | T2 | ⚠️ | `55_doc_drift.sh` advisory critic — seam shipped; activation **paused by choice** (critics must use the user's own agent, e.g. `claude -p`, never independent API keys / token burn — ADR-0030) |
| Changelog updated | T0 | ✅ | `checks/shared/11_changelog.sh` — presence + Unreleased; strict entry-on-src-change now on (ADR-0028) |
| README / ARCHITECTURE freshness | T2 | ❌ | |

### H. Process & collaboration — CS130 §7, §12
| Branch policy | T0 | ✅ | `08_branch` (ADR-0021) |
| Commit conventions | T0 | ✅ | `09_commits` |
| Gated, explicit merge | T0 | ✅ | `merge.sh` (ADR-0007) |
| CI runs the gate | T0 | ✅ | `.github/workflows/verify.yml` (ADR-0008) |
| PR review required | T2 | ⚠️ | human review; the **T2 critic** is the automated form |
| Atomic-commit / conventional-commit → changelog | T0/T2 | ❌ | |
| Repository hygiene / layout | T0 | ✅ | `05_hygiene`, `07_layout` (ADR-0018) |
| Commit identity | T0 | ✅ | `06_git_identity` guard (ADR-0017/0019) |
| Adoption upgrade path for existing projects | T0 | ✅ | `adopt.sh` — adds newer checks + seeds ratchet baselines from current state; complements `init.sh` (ADR-0041) |
| DORA flow metrics (lead time, deploy freq, change-fail, MTTR) | T1 | ❌ | candidate — PR/commit-size ratchet is git-derivable now; deploy/MTTR need CI/deploy telemetry |

### I. Performance & reliability — CS130 §11, §13
| Perf budget / benchmark ratchet | T1 | ❌ | deliberately deferred — borromeanRings has no perf-critical hot paths (meaningless ratchet here) |
| Bundle / binary size ratchet | T1 | ❌ | |
| Error-handling completeness | T2 | ⚠️ | `56_critics` rubric `error_handling` — advisory critic (ADR-0036) |
| Logging / observability presence | T2 | ❌ | |
| Load / chaos testing | T3 | ❌ | |

### J. Intent / semantic correctness — the ceiling — CS130 §9, §14
| **"Built the right thing" rubric critic** | T2 | ✅ | critic seam + `55_doc_drift` + `56_critics` rubric family (ADR-0023/0030/0036) |
| Explainability (no unexplained code) | T2/T3 | ❌ | CS130 §14 rule |
| AI-code security-review-by-default | T2 | ⚠️ | bandit (`50_security`) + `56_critics` rubric `security` — advisory semantic review (ADR-0036) |

### K. Meta — is the enforcement itself real? — CS130 §15
| **Adversarial self-test** (gate must catch known-bad) | T0 | ✅ | `tests/test_gate_adversarial.py` — known-bad corpus, permanent (ADR-0025) |
| Tamper-evident receipts | T0 | ✅ | content-digest receipts + fail-closed verdict + run-digest anchor (ADR-0026) |
| Mutation-test the gate's own checks | meta | ✅ | the checks' logic lives in `meta_harness/*` which `60_mutation` mutates (ADR-0022) |

## 3. Honest scorecard (2026-08, v1 released to `main`)

- **T0 (deterministic gate): strong and broad** — build, types, lint, static-security,
  layout, the full process/collaboration set, native secret-scan, dependency-direction
  architecture fitness, **public-API breaking-change detection** (`34_api_diff`, dogfooded on
  `examples/textkit`), and an **adoption upgrade path** (`adopt.sh`). borromeanRings's earned strength.
- **T1 (ratchet): filled** — mutation-score (the assertion-strength signal that closes the
  coverage-Goodhart hole the probe exposed), cyclomatic-complexity, **coupling/fan-out**, and
  docstring-coverage ratchets; CVE audit and license compliance on the CI heavy lane. The
  deliberately-broken-function probe is a **permanent adversarial check**. *Deliberately*
  deferred: perf/bundle (no hot paths here), duplication (low value), property-based (mutation
  covers oracle strength). *Buildable candidates:* **coverage** (this doc previously mis-claimed
  it — no check exists), flaky-detection, type-coverage.
- **T2 (semantic critic): seam + rubric family, activation PAUSED by choice.** The critic (a
  judge external to the generator, fail-closed) is built: doc-drift + error-handling / naming /
  security / boundary-value / test-smell as a DRY rubric registry. Activation is **deliberately
  paused** — a critic must use the **user's own agent** (e.g. `claude -p`), never independent
  API keys or token burn (see the red line in §VISION). Promotion to gating is a heavy-lane +
  `required=True` step once the user opts in.
- **T3 (advisory): principled** — prompt-rewrite, research skills, the project profiler (the
  selector for this whole matrix), and the shipped **agent-enhancement recommender**
  (`meta_harness.enhancements`, ADR-0037) — curated open-source tools that improve the *wrapped
  agent* (routing / caching / observability), advisory, never gating.

**Verdict.** borromeanRings enforces **hygiene comprehensively and quality substantively**: the
T1 tier is filled (assertion strength is enforced, not just execution), receipts are
tamper-evident, portability is proven end-to-end (`examples/textkit`), and all 10 governed
projects are migrated to the newer check set. What remains is *by choice* (deferred poor-fit
ratchets), *the user's opt-in* (critic activation), or the **other governance axes** (§6).

## 6. Beyond code quality — the other governance matrices

The A–K matrix above is **one axis** (code quality). borromeanRings governs it strongly; these
are the other axes, each a full matrix. Per "justified building", each row lands only when a
real project of that archetype needs it (as `examples/textkit` justified `34_api_diff`).

| Matrix | Status | First real rows |
|---|---|---|
| **AI-agent quality** | partial | agent-enhancement recommender ✅; eval-regression ratchet, citation verification (candidates — **agent-only, no API keys**) |
| **Security & compliance** | partial | SAST / CVE / secrets / licenses / pins / lockfile / SBOM ✅; git-history secret-scan ✅; provenance signing + Dependabot (maintainer, CI-dependent) |
| **Delivery / DORA** | partial | branch / commit / merge / CI gates ✅; PR-size ratchet (git-derivable); deploy-freq / MTTR (telemetry-gated) |
| **Operational / SRE** | archetype | needs a deployed service (candidate archetype: `AutoApply`) |
| **Data / ML** | archetype | needs an ML project |
| **Product / UX** | archetype | a11y / Core Web Vitals (candidate archetype: `portfolio` — has `package.json`) |

## 4. How rows graduate

A ❌/⚠️ row becomes ✅ the borromeanRings way *(matches [`ROADMAP.md`](ROADMAP.md) "How items graduate")*:
spec (`docs/specs/SPEC-*.md`) → branch → passes borromeanRings's **own** gate → human-approved merge.
Capabilities adopted *into* borromeanRings face a **same-or-stricter** gate (trust root). Prefer landing a
row at the **lowest tier** first (a ratchet beats a critic beats an advisory), then strengthen.

## 5. Active program (workstreams)

| # | Workstream | Fills | Tier |
|---|---|---|---|
| 1 | **This map** (persist as living doc) | K (self-knowledge) | — |
| 2 | **T1 ratchets** — mutation, complexity, duplication, dead-code | A, B | T1 |
| 3 | **T2 critic seam** — substrate-agnostic injected rubric critic (intent, doc-drift) | J, G, E, F | T2 |
| 4 | **Project profiler** — classify type → select active rows/tiers → emit `borromeanrings.toml` | selects all | T3 |

This document is **living**: as rows graduate, update their status here in the same PR — drift
between this map and reality is itself a defect (see row G/doc-drift).
