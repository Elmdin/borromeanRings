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
| Coverage non-regression | T1 | ✅ | ratchet vs `.borromeanrings-coverage-baseline` |
| **Mutation score** (assertion/oracle strength) | T1 | ✅ | `checks/ci/60_mutation.sh` (CI-tier heavy lane), ratchet vs `.borromeanrings-mutation-baseline`; baseline 0.80. Closes the coverage-Goodhart gap. ADR-0022 |
| Property-based / metamorphic testing present | T1/T3 | ❌ | Hypothesis / metamorphic invariants |
| Boundary-value / equivalence design | T2 | ❌ | needs a critic to judge input design |
| Flaky-test detection | T1 | ❌ | rerun variance; quarantine |
| Every bug-fix ships a regression test | T0/process | ⚠️ | stated in rules, not enforced |
| Test isolation / independence | T0 | ⚠️ | pytest fixtures; not asserted |
| Test-smell detection (assertion roulette, mystery guest) | T2 | ❌ | |

### B. Static correctness & type safety — CS130 §6
| Typecheck | T0 | ✅ | mypy (`30_typecheck`) |
| Lint | T0 | ✅ | ruff (`20_lint`) |
| Dead-code detection | T0/T1 | ❌ | vulture / ts-prune |
| Cyclomatic-complexity ceiling/ratchet | T1 | ❌ | radon |
| Duplication ratchet | T1 | ❌ | jscpd / pylint duplicate-code |

### C. Security — CS130 §14
| Static SAST | T0 | ✅ | bandit (`50_security`) |
| Dependency / CVE audit | T0 | ❌ | pip-audit / safety |
| Secret scanning | T0 | ❌ | gitleaks / trufflehog |
| Pinned deps / lockfile integrity / SBOM | T0 | ⚠️ | `pyproject.toml`; no lockfile-integrity gate |
| License compliance | T0 | ❌ | |
| Fuzzing / DAST | T1/T3 | ❌ | |

### D. Design & architecture — CS130 §4, §11
| **Dependency-direction / architecture fitness functions** | T0 | ❌ | import-linter / ArchUnit — enforce layering & the DIP |
| Layering / information-hiding | T0 | ⚠️ | `07_layout` enforces *file* layout, not *dependency* rules |
| Coupling/cohesion metrics | T1/T2 | ❌ | |
| ADR present for load-bearing decisions | T0/T3 | ⚠️ | ADRs by convention (`docs/adr`), not gated |
| Design-doc for N-file features | T0/T3 | ⚠️ | rule only |
| Public-API breaking-change detection | T1 | ❌ | API diff / semver enforcement |

### E. Code smells & maintainability — CS130 §6, §9
| Function/file size, nesting depth | T0 | ⚠️ | partial via ruff; nesting not bounded |
| Naming quality, feature envy, long-param, primitive obsession | T2 | ❌ | critic territory |

### F. Requirements & traceability — CS130 §1, §15
| Story → test traceability | T2 | ❌ | "trace each test to a decision to a requirement" |
| Spec present for features | T0 | ⚠️ | rule only (see [`SPEC-*`](specs/)) |
| Acceptance criteria as Given/When/Then tests | T3 | ❌ | |
| Requirements coverage | T2 | ❌ | |

### G. Documentation — CS130 §10
| Docstring / API-doc coverage | T1 | ❌ | interrogate / docstr-coverage |
| **Doc-drift** (docs match code) | T2 | ⚠️ | caught manually (e.g. the deep_research docstring); not enforced |
| Changelog updated | T0 | ❌ | |
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

### I. Performance & reliability — CS130 §11, §13
| Perf budget / benchmark ratchet | T1 | ❌ | |
| Bundle / binary size ratchet | T1 | ❌ | |
| Error-handling completeness | T2 | ❌ | |
| Logging / observability presence | T2 | ❌ | |
| Load / chaos testing | T3 | ❌ | |

### J. Intent / semantic correctness — the ceiling — CS130 §9, §14
| **"Built the right thing" rubric critic** | T2 | ❌ | roadmap ⏳ "External rubric critic"; workstream #3 |
| Explainability (no unexplained code) | T2/T3 | ❌ | CS130 §14 rule |
| AI-code security-review-by-default | T2 | ⚠️ | bandit only; no semantic security review |

### K. Meta — is the enforcement itself real? — CS130 §15
| **Adversarial self-test** (gate must catch known-bad) | T0 | ❌ | make the manual "buggy-code probe" a permanent check |
| Tamper-evident receipts | T0 | ⚠️ | receipts exist (`.meta-harness/receipts/`); no tamper-evidence |
| Mutation-test the gate's own checks | meta | ❌ | |

## 3. Honest scorecard (2026-07)

- **T0 (deterministic gate): strong, fairly complete for *hygiene*** — build, types, lint,
  static-security, layout, and the full process/collaboration set. This is borromeanRings's earned strength.
- **T1 (ratchet): opening up** — coverage (weak) **plus mutation score** (strong,
  assertion-level; ADR-0022), the latter on the CI-tier heavy lane. Mutation closes the
  coverage-Goodhart hole the probe exposed. Still unbuilt and T1-shaped: complexity,
  duplication, dead-code, perf, doc-coverage, API-diff. Still the biggest tier to deepen.
- **T2 (semantic critic): zero.** Every "does it do the right thing / is it well-designed / do the
  docs match / are requirements traced" practice lives here and none is enforced. This is the
  **quality ceiling**: mechanical gates check *form*, never *intent*.
- **T3 (advisory): thin but principled** — prompt-rewrite and research skills exist; the project
  profiler is the next T3 capability *and* the selector for this whole matrix.

**Verdict.** borromeanRings today enforces **hygiene comprehensively** and **quality partially**. Calling
it "enforces high-quality code" is only earned once T1 is filled (assertion strength) and the T2
critic seam exists (intent). Until then it is an honest, strong, regression-proof **floor**.

## 4. How rows graduate

A ❌/⚠️ row becomes ✅ the borromeanRings way *(matches [`ROADMAP.md`](ROADMAP.md) "How items graduate")*:
spec (`docs/specs/SPEC-*.md`) → branch → passes borromeanRings's **own** gate → human-approved merge.
Capabilities adopted *into* borromeanRings face a **same-or-stricter** gate (trust root). Prefer landing a
row at the **lowest tier** first (a ratchet beats a critic beats an advisory), then strengthen.

## 5. Active program (workstreams)

| # | Workstream | Fills | Tier |
|---|---|---|---|
| 1 | **This map** (persist as living doc) ✅ | K (self-knowledge) | — |
| 2 | **T1 ratchets** — mutation ✅ (ADR-0022); complexity, duplication, dead-code next | A, B | T1 |
| 3 | **T2 critic seam** — substrate-agnostic injected rubric critic (intent, doc-drift) | J, G, E, F | T2 |
| 4 | **Project profiler** — classify type → select active rows/tiers → emit `borromeanrings.toml` | selects all | T3 |

This document is **living**: as rows graduate, update their status here in the same PR — drift
between this map and reality is itself a defect (see row G/doc-drift).
