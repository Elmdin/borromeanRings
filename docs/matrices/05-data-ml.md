# Matrix #5 — Data / ML

Scope: projects whose behaviour is learned from data — data validation, training
reproducibility, model evaluation, serving safety and monitoring. No project in the governed
roster is an ML project yet, so every row is either shared with the code-quality axis or
**archetype-blocked** on a `[project].kind = "ml"` declaration (#79). The row structure follows
the four sections of the ML Test Score rubric. Conventions: [`README.md`](README.md).

| Row | Criterion (binary or ratchet) | Enforced by | Buildability | Source |
|---|---|---|---|---|
| M1 | Feature/input expectations are captured in a schema file and the schema is validated against training and serving data | gap → #79 (`ml` profile) | archetype | Breck et al., "The ML Test Score: A Rubric for ML Production Readiness and Technical Debt Reduction", IEEE Big Data 2017 — Data 1 (feature expectations in a schema) |
| M2 | Every feature-engineering / input-transform function has a unit test (feature code is tested like any code) | ✅ `40_test` for the *tests-exist-and-pass* half (source without tests fails); the "every feature function" mapping is gap → #79 | archetype (mapping) | ML Test Score — Data 7 (all input feature code is tested) |
| M3 | Data-pipeline code carries no PII in fixtures or logs and no secrets | ✅ `12_secrets` / `74_secret_history` for secrets; PII fixture scan is gap → #138 | now (secrets) / archetype (PII) | ML Test Score — Data 5 (privacy controls across the pipeline); GDPR Art. 5(1)(c) data minimisation |
| M4 | Model specification (code + config) is under version control and reviewed like code (ADR + PR) | ✅ `13_adr` + `09_commits` + `11_changelog` (the review half is D14) | now | ML Test Score — Model 1 (model specs reviewed and submitted); Sculley et al., "Hidden Technical Debt in Machine Learning Systems", NeurIPS 2015 (configuration debt) |
| M5 | Training is reproducible: fixed seeds, pinned data version, pinned dependency lock; two runs of the same commit produce the same metrics | gap → #79 + S8 (lockfile) | archetype | ML Test Score — Infra 1 (training is reproducible); Sculley et al. 2015 |
| M6 | Datasets and models carry documentation artefacts (datasheet, model card) that the gate checks for presence | gap → #79 (presence of `MODEL_CARD.md` / `DATASHEET.md` via `[hygiene].requires` once the archetype declares them) | archetype (presence is `now` once declared) | Mitchell et al., "Model Cards for Model Reporting", FAT* 2019; Gebru et al., "Datasheets for Datasets", CACM 2021 |
| M7 | **Offline evaluation ratchet**: the declared primary metric on the held-out set may not regress vs the recorded baseline (threshold-free) | gap → #79 (a `meta_harness.ratchet` instance over an evaluation receipt) | archetype | ML Test Score — Model 6 (quality on important slices) and Monitor 7 (prediction quality not regressed); `meta_harness.ratchet` (ADR-0022 shape) |
| M8 | **Slice ratchet**: the same metric on each declared data slice may not regress (fairness/inclusion is checked per slice, not on the aggregate) | gap → #79 | archetype | ML Test Score — Model 6 (slices), Model 7 (inclusion); Mitchell et al. 2019 (disaggregated evaluation) |
| M9 | A baseline model comparison is recorded: the deployed model is not beaten by the declared simple baseline | gap → #79 | archetype | ML Test Score — Model 5 (simpler model is not better) |
| M10 | Training/serving skew guard: the same feature computed by the training and serving paths yields the same value on a golden set | gap → #79 | archetype | ML Test Score — Monitor 3 (training and serving features compute the same values); Sculley et al. 2015 (feedback loops, entanglement) |
| M11 | The ML pipeline is integration-tested end-to-end on a small fixture (data → train → evaluate → export) | gap → #79 | archetype | ML Test Score — Infra 3 (full pipeline integration test) |
| M12 | Model quality is validated before serving and a rollback to the previous model is possible and exercised | gap → #79 (shares O11) | archetype | ML Test Score — Infra 4 (validate before serving), Infra 7 (roll back to a previous model) |
| M13 | Model staleness bound: the age of the served model is recorded and may not exceed its recorded baseline (a ratchet, not a fixed TTL) | gap → #138 | telemetry | ML Test Score — Model 4 (impact of staleness known), Monitor 4 (models are not too stale) |
| M14 | Serving-time data invariants (schema from M1) are checked on live inputs and violations are recorded | gap → #138 | telemetry | ML Test Score — Monitor 2 (data invariants hold in training and serving inputs) |
| M15 | Upstream data-dependency changes produce a notification recorded in the repo (a data contract) | gap → #138 | telemetry | ML Test Score — Monitor 1 (dependency changes result in notification); Sculley et al. 2015 (unstable data dependencies) |
| M16 | Numerical stability: no NaN/Inf in weights or predictions on the evaluation set (binary) | gap → #79 | archetype | ML Test Score — Monitor 5 (model is numerically stable) |
| M17 | Property-based tests exist for invariants of transforms (idempotence, monotonicity, shape) — where declared | gap → #140 (Hypothesis on the heavy lane; `noop` when none declared) | now (once #140 lands) | Amershi et al., "Software Engineering for Machine Learning: A Case Study", ICSE-SEIP 2019 (testing ML components); #140 |

## Notes

- **Nothing here is invented as a target.** Every quantitative row (M7, M8, M13) is a
  non-regression ratchet against a recorded baseline — the `60_mutation` shape — never a
  score threshold. That is the only form an ML metric gate may take in this project.
- **Why the whole matrix is archetype-gated.** "Justified building" (`docs/ROADMAP.md`): no ML
  project is in the roster, so building these checks now would be a gate nobody runs. The
  document exists so that the day a project declares `kind = "ml"`, the rows, their sources and
  their gate shapes are already decided.
- **Reuse before build.** M2, M3, M4 are already enforced by the code-quality checks; an ML
  archetype only *adds* rows, it never duplicates them.
