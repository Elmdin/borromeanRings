# Architecture Decision Records

> CS130 (Part 1 L4 / Part 4): an ADR is the organizational memory of a load-bearing decision —
> context, the alternatives considered, the choice, and its consequences — so the decision can be
> revisited later instead of silently re-litigated. borromeanRings records these because its own thesis
> is auditable, evidence-backed engineering: it would be hypocritical to make these choices without
> a trail.

Format per record: **Status · Context · Decision · Alternatives considered · Consequences.**

| ADR | Title | Status |
|---|---|---|
| [0001](0001-substrate-claude-code.md) | Substrate = Claude Code (hook-based gate) | Accepted |
| [0002](0002-model-hosting-frontier-api.md) | Model hosting = frontier API | Accepted |
| [0003](0003-no-local-model-wsl2.md) | No local model (WSL2, no GPU) | Accepted |
| [0004](0004-first-stack-python.md) | First governed stack = Python | Accepted |
| [0005](0005-checks-registry-and-adapter-seam.md) | Checks as a uniform-contract registry; substrate Adapter seam | Accepted |
| [0007](0007-gated-explicit-merge.md) | Gated, explicitly-requested merge (no autonomous self-merge) | Accepted |
| [0008](0008-ci-runs-the-gate.md) | CI runs the gate as the required status check | Accepted |
| [0009](0009-command-orchestrated-auto-merge.md) | Command-orchestrated auto-merge (free private repo) | Accepted |
| [0010](0010-config-policy-spine.md) | Config/policy spine (`borromeanrings.toml`) | Accepted |
| [0011](0011-prompt-rewriting.md) | Prompt rewriting: enforced by borromeanRings, performed by the agent | Accepted |
| [0012](0012-engineering-process.md) | Engineering process = risk-driven + TDD | Accepted |
| [0013](0013-portability-reference-model.md) | Portability: govern any project by reference | Accepted |
| [0014](0014-research-enhances-agent-not-searches.md) | Research enhancement steers the agent's own search | Accepted |
| [0015](0015-per-language-check-sets.md) | Per-language check sets (gate adjusts to the project) | Accepted |
| [0016](0016-no-op-stop-gate-skip.md) | Skip the Stop gate when the governed state is unchanged | Accepted |
| [0017](0017-git-identity-enforcement.md) | Enforce the declared git commit identity (guard + gate) | Accepted |
| [0018](0018-repository-layout-enforcement.md) | Enforce declared repo layout (specs dir, root-doc allowlist, test grouping) | Accepted |
| [0019](0019-git-identity-local-guard-only-public-repo.md) | Git identity: local-guard-only for the public repo (amends 0017) | Accepted |
| [0020](0020-ai-fluency-4d-vocabulary.md) | Adopt AI Fluency 4D as collaboration vocabulary (re-authored, Apache-2.0) | Accepted |
| [0021](0021-gitflow-lite-branching.md) | Gitflow-lite branching: feature → `dev` (default) → `main` | Accepted |
| [0022](0022-mutation-ratchet-ci-heavy-tier.md) | Mutation-score ratchet on a CI-tier "heavy" check lane | Accepted |
| [0023](0023-external-rubric-critic-seam.md) | T2 external rubric critic as a substrate-agnostic, injected-judge seam | Accepted |
| [0024](0024-project-profiler-advisory-selector.md) | Project profiler as an advisory (T3) matrix selector | Accepted |
| [0025](0025-adversarial-selftest-corpus.md) | Adversarial self-test: a known-bad corpus the gate must reject | Accepted |
| [0026](0026-tamper-evident-receipts.md) | Tamper-evident receipts (content digest + fail-closed verdict) | Accepted |
| [0027](0027-native-import-direction-arch-fitness.md) | Native import-direction architectural fitness (not import-linter) | Accepted |
| [0028](0028-changelog-discipline.md) | Changelog discipline (Keep a Changelog), non-retroactive first | Accepted |
| [0029](0029-docstring-coverage-ratchet.md) | Docstring-coverage ratchet (native, non-regression) | Accepted |
| [0030](0030-doc-drift-critic-live-judge.md) | Doc-drift: the first live application of the T2 critic seam | Accepted |
| [0031](0031-cyclomatic-complexity-ratchet.md) | Cyclomatic-complexity ratchet (native, non-regression) | Accepted |
| [0032](0032-native-secret-scanning.md) | Native high-confidence secret scanning | Accepted |
| [0033](0033-ci-heavy-lane-machinery.md) | CI-tier "heavy" check lane (machinery) | Accepted |
| [0034](0034-dependency-cve-audit-heavy.md) | Dependency CVE audit on the heavy lane (pip-audit) | Accepted |
| [0035](0035-dependency-license-compliance-heavy.md) | Dependency license compliance on the heavy lane (pip-licenses) | Accepted |
| [0036](0036-wave2-critic-rubric-family.md) | Wave-2 critic rubric family (advisory) | Accepted |
| [0037](0037-agent-enhancement-recommender.md) | Agent-enhancement recommender (advisory) | Accepted |
| [0038](0038-coupling-ratchet.md) | Coupling ratchet (worst-case fan-out, native) | Accepted |
| [0039](0039-example-governed-project.md) | An example governed project (textkit) to prove portability | Accepted |
| [0040](0040-public-api-breaking-change.md) | Public-API breaking-change detection | Accepted |
| [0041](0041-adoption-helper.md) | Adoption helper for existing governed projects | Accepted |
| [0042](0042-secret-scanning-completeness.md) | Secret-scanning completeness: history + non-git fail-closed | Accepted |
| [0043](0043-adr-discipline-gate.md) | ADR-discipline gate | Accepted |
| [0044](0044-container-hygiene.md) | Container (Dockerfile) hygiene gate | Accepted |
| [0045](0045-static-accessibility.md) | Static accessibility (a11y) invariants gate | Accepted |
| [0046](0046-portfolio-status.md) | Portfolio status (roster health) command | Accepted |
| [0047](0047-effectiveness-ledger.md) | Effectiveness ledger (verdict history) | Accepted |
| [0048](0048-harness-versioning-and-run-stamping.md) | Harness versioning + per-run version stamping | Accepted |
| [0049](0049-honest-noop-status-and-source-coherence.md) | Honest no-op status, the source-coherence guard, and self-status | Accepted |
| [0050](0050-shell-lint-gate.md) | Shell lint gate (shellcheck) | Accepted |
| [0051](0051-prior-art-gate.md) | Prior-art gate: look before building, on the record | Accepted |
| [0052](0052-self-description.md) | Capability self-description, generated from the registry | Accepted |
| [0053](0053-compaction-brief.md) | Governance state must survive compaction (PreCompact + SessionStart hooks) | Accepted |
| [0054](0054-api-usage-contracts.md) | API-usage contracts are deterministic AST rules, not LLM judgement | Accepted |
| [0055](0055-context-budget-ratchet.md) | Context-budget ratchet (what borromeanRings itself costs per turn) | Accepted |
| [0056](0056-verdict-evidence-intent-risk-band.md) | Evidence, intent and a categorical risk band in the verdict | Accepted |
| [0057](0057-claude-code-plugin-distribution.md) | Ship borromeanRings as a Claude Code plugin (by-reference governance, one-line install) | Accepted |
| [0058](0058-trunk-based-branch-policy-enforcement.md) | Enforce the branch policy: nothing lands on a protected branch except via PR + gate | Accepted |
| [0059](0059-rewrite-contract-receipt.md) | The prompt-rewrite directive is a verified contract, recorded at Stop | Accepted |
| [0060](0060-research-skill-token-budget.md) | Research skill: declared budget, state on disk, extract-not-ingest | Accepted |
| [0061](0061-supply-chain-hardening.md) | Supply-chain hardening: lockfile integrity, pinned dependencies, SBOM | Accepted |
| [0062](0062-application-archetypes.md) | Application archetypes: required-feature gates, playbooks, and archetype-forced non-`noop` | Accepted |
| [0063](0063-session-charter-gate.md) | Session charter gate — delegation terms written down and validated fail-closed | Accepted |
| [0064](0064-predicate-lint.md) | Predicate lint: hedge words and graph integrity in acceptance predicates | Accepted |
| [0065](0065-quote-fidelity-verifier.md) | Quote fidelity: verbatim quotation vs saved source (`24_quotes`) | Accepted |
| [0066](0066-self-report-receipt.md) | The agent's self-report is structural, taught by the skills, recorded at Stop | Accepted |
| [0067](0067-swe-state-report.md) | SWE-state report: practises / lacks / adopt next, categorical and sourced | Accepted |
| [0068](0068-multi-language-lanes.md) | TypeScript and Go check lanes — honest about absent tools, never networked | Accepted |
| [0069](0069-multi-harness-substrate.md) | Multi-harness substrates: one gate, one hook set, per-substrate wiring adapters | Accepted |
| [0070](0070-provenance-gate.md) | Provenance gate: binary shingle overlap against a declared source, classified by a human allowlist | Accepted |
| [0071](0071-executor-and-generator-interfaces.md) | Executor and generator interfaces: one gate, pluggable where-it-runs and who-generates | Accepted |
| [0072](0072-approach-advisor.md) | Approach advisor: rules as data, questions before approaches, never a gate | Accepted |
| [0073](0073-citation-resolution-gate.md) | Citations must resolve on the branch that carries them | Accepted |
| [0074](0074-verification-ladder-property-tier-first.md) | The verification ladder, property tier first | Accepted |
| [0075](0075-static-a11y-labels-links-headings.md) | Static a11y rules for labels, link text and heading structure (U4–U6) | Accepted |
| [0076](0076-worktree-executor.md) | The `worktree` executor: a separate entry point, proven by conformance | Accepted |
| [0077](0077-pin-the-check-toolchain.md) | Pin the check toolchain exactly (amends 0008) | Accepted |
| [0078](0078-headless-generator-and-loop-conformance.md) | The headless generator: one decision, two thin drivers, and provenance in the verdict | Accepted |
| [0079](0079-retry-count-outside-the-tree.md) | Keep the Stop hook's retry count outside the governed tree | Accepted |
| [0080](0080-gate-python-off-project-sys-path.md) | The gate's trusted Python must not run with the project on sys.path | Accepted |
| [0081](0081-fast-interactive-lane.md) | A fast (interactive) lane, so the Stop gate is not the whole test suite | Accepted |
| [0082](0082-no-op-skip-state-outside-the-tree.md) | The Stop hook's no-op skip must not rest on anything the project can write | Accepted |
| [0083](0083-trim-the-injected-directive.md) | Trim what borromeanRings injects, and pin the obligations against the trimming | Accepted |
| [0084](0084-init-makes-a-repository-so-secrets-can-be-a-default.md) | `init.sh` makes a repository, so `12_secrets` can be a default | Accepted |
| [0086](0086-the-full-test-lane-runs-in-parallel.md) | The full test lane runs in parallel, and tests declare what they share | Accepted |

Open items live in [`../DELAYED-DECISIONS.md`](../DELAYED-DECISIONS.md); a delayed decision
graduates to an ADR once the Maintainer resolves it.
