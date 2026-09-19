# SPEC — Application archetypes: required-feature gates + playbooks

**Status:** Implemented (phase 1 of #79) · **Realized by:** `src/meta_harness/archetypes.py`,
`src/meta_harness/spine.py` (`[project].archetypes`), `checks/shared/21_archetype.sh`,
the `must_be_non_noop` clause in `verify.sh`'s verdict · ADR-0062

## Problem

The gate decides *how well* code is written and *what engineering surround exists*, but
not *whether an application has what an app of its kind must have*. An agent asked to
build a web API produces something clean, typed and tested — and missing a health
endpoint, structured logging and an auth mechanism, because nothing says what "complete"
means for that kind of app (#79). Separately, several checks legitimately emit `noop`
when they find nothing to inspect (ADR-0049); for a declared web app, `15_a11y`
inspecting *nothing* is not legitimate, and an archetype must be able to say so (#130
§"honest problems", #138).

## Vocabulary

`[project].archetypes` is a list of archetype names. The vocabulary is closed:

| Archetype | Kind of program |
|---|---|
| `library` | an importable package consumed by other code |
| `cli` | a command-line tool run by people or scripts |
| `web-api` | a network service exposing HTTP/RPC endpoints |
| `web-app` | a user-facing browser application (rendered UI) |
| `ml` | a project that trains, evaluates or serves a model |
| `embedded` | firmware for a microcontroller / bare-metal or RTOS target |
| `data-pipeline` | batch/stream data movement and transformation |

The name list lives in `spine.ARCHETYPES` (the spine is an architecture *leaf* and may
import no domain module); the catalog in `archetypes.CATALOG` is keyed by exactly that
list, and a unit test binds the two. Names are hyphenated, following the issue; the
profiler's advisory `PROFILES` keys (`web_api`, …) are a separate namespace and stay
untouched.

## Contract

### Declaration (spine)

```toml
[project]
archetypes = ["cli", "library"]
```

- `Config.archetypes: tuple[str, ...]`, default `()`.
- **Unknown archetype ⇒ `load_config` raises `ValueError`** naming the unknown names and
  the vocabulary. Fail closed at config time: every consumer of the spine (the gate, the
  hooks, `status`) refuses to run on a misspelled archetype rather than silently gating
  nothing.
- Duplicates are harmless (features are unioned by id).
- Absent / empty ⇒ the whole dimension is off: `21_archetype` reports `noop` ("rule off"),
  and the verdict's non-noop clause has nothing to check. **Back-compat: a project with no
  `archetypes` key behaves exactly as before this feature.**

### Catalog (pure, immutable data)

`archetypes.CATALOG: Mapping[str, Archetype]`, `CATALOG_VERSION = "1"`.

- `Archetype(name, summary, features, must_be_non_noop, playbook)` — frozen dataclass.
- `Feature(id, title, paths=(), content=(), pattern="", why="")` — frozen dataclass. A
  feature is **present** when a regular file matches one of the presence globs `paths`,
  **or** a file matching one of the `content` globs has text matching `pattern`
  (`re.MULTILINE | re.IGNORECASE`). Globs are root-relative with `Path.glob`-like
  semantics (`**/` = any depth, `*` = one segment). Files inside a skipped directory
  (`.git`, `.venv`, `venv`, `node_modules`, `dist`, `build`, `vendor`, `.meta-harness`,
  `mutants`, `__pycache__`, `site-packages`, `.tox`, `.mypy_cache`) are never evidence.
  For content matches, files over 1 MiB and unreadable files are skipped (never evidence,
  never a crash). Evidence order is deterministic: presence globs in declaration order,
  paths sorted; then content globs likewise. A feature declares at least one half, and
  `content` and `pattern` come together.
- **Every predicate is file/config presence or a regex over file content.** No model
  call, no network, no build, no execution. This decides **presence, not correctness**:
  a content pattern can be satisfied by a comment or an unrelated identifier, and a
  present health route can still be wrong. The gate says the artefact exists on the
  record; whether it works is what the archetype's tests (which must be non-`noop`) and
  the playbook are for. If a requirement cannot be decided that way it
  is *not* a feature; it goes in the playbook (advisory prose) instead.
- `must_be_non_noop: tuple[str, ...]` — check ids (as in `[checks].required`) that must
  have inspected something when this archetype is declared.
- `playbook: str` — best practices the agent reads. **Advisory**: never gated, never
  parsed.

### Functions

| Function | Behaviour |
|---|---|
| `required_features(archetypes) -> tuple[Feature, ...]` | union over the declared archetypes, de-duplicated by `id`, in first-appearance order. Unknown name ⇒ `ValueError` (fail closed even if the spine was bypassed). `()` ⇒ `()`. |
| `non_noop_checks(archetypes) -> tuple[tuple[str, str], ...]` | `(check_id, archetype)` pairs, sorted by check then archetype. |
| `evaluate(project_root, archetypes) -> Report` | `Report(archetypes, results, must_be_non_noop)`; `results` is one `FeatureResult(feature_id, title, present, evidence)` per required feature, in order. `evidence` is the matched path (`path` for presence, `path:line` for content) or `""` when absent. |
| `render_report(report) -> str` | exact, deterministic text: one line per feature (`ok`/`MISSING` + evidence or the hint), a summary line, and the must-be-non-noop list. |
| `non_noop_violations(archetypes, statuses) -> tuple[str, ...]` | for each `(check, archetype)` in `non_noop_checks`: a message when `statuses[check]` is `"noop"` (*"required to inspect something by archetype X"*), or when `check` is not in `statuses` at all (not in the run's expected set — required-to-inspect implies required-to-run). Empty ⇒ no violation. |

### Gate: `checks/shared/21_archetype.sh`

| State | Receipt |
|---|---|
| no archetypes declared | `noop` — log says the rule is off |
| every required feature present | `pass` — log is `render_report` |
| any required feature absent | `fail` — log lists each absent feature with its hint |

Off unless `21_archetype` is in `[checks].required` (per-project opt-in, ADR-0010).

### Verdict: `must_be_non_noop`

In `verify.sh`'s verdict block, after the receipt rows are computed and **before**
`RESULT`, `non_noop_violations(config.archetypes, {check: status})` is consulted. Each
violation prints as a row-level line and turns the run **FAIL**. This is the one place
the archetype dimension can override a check's own non-failing `noop`: an archetype
asserting "this check must inspect something" makes a hollow green red. Projects without
archetypes are unaffected (empty tuple ⇒ no violations).

## Archetype → features (catalog v1)

Each feature names the matrix row or issue that justifies it. "Predicate" is the exact
mechanism; anything not expressible as one lives in the playbook only.

| Archetype | Feature id | Predicate | Justification |
|---|---|---|---|
| `library` | `package_manifest` | `pyproject.toml` / `setup.py` / `setup.cfg` / `package.json` / `Cargo.toml` / `go.mod` present | #79 (a library is a distributable unit) |
| `library` | `version_declared` | `VERSION` present, or `version =` / `"version":` in a manifest | Semantic Versioning; ADR-0048 |
| `library` | `license_present` | `LICENSE*` / `COPYING*` present | OSS hygiene (ADR-0012) |
| `library` | `changelog_present` | `CHANGELOG*` / `HISTORY*` present | Keep a Changelog; ADR-0028 |
| `cli` | `entrypoint_declared` | `[project.scripts]` in `pyproject.toml`, a `__main__.py`, `"bin"` in `package.json`, `[[bin]]` in `Cargo.toml`, or a root `*.sh` with a shebang | #79 (a CLI has an invocable entry point) |
| `cli` | `usage_documented` | `README*` / `docs/USAGE*` has a heading mentioning usage / quick start / getting started / run / install / how to | Nielsen #10 help & documentation |
| `cli` | `license_present`, `changelog_present` | as above | shared |
| `web-api` | `health_endpoint_declared` | source mentions `/health`, `/healthz`, `/ready`, `/readyz`, `/live`, `/livez` or `/ping` | O6 |
| `web-api` | `structured_logging_configured` | source mentions `structlog`, `json_log`/`jsonlogger`, `logging.config`, `pino`, `winston`, `zerolog`, `slog`, `log/slog` | O7 |
| `web-api` | `input_validation_layer` | source mentions `pydantic`, `marshmallow`, `jsonschema`, `cerberus`, `voluptuous`, `zod`, `joi`, `yup`, `class-validator`, `validator/v10` | #79 web-api row 1; OWASP ASVS V5 |
| `web-api` | `auth_mechanism_declared` | source mentions `jwt`, `oauth`, `HTTPBearer`, `HTTPBasic`, `passport`, `authlib`, `django.contrib.auth`, `Authorization` header handling | #79 web-api row 2; ASVS V2/V4 |
| `web-api` | `rate_limiter_declared` | source mentions `slowapi`, `ratelimit`, `throttl`, `express-rate-limit`, `limiter`, `tollbooth` | #79 web-api row 3 |
| `web-api` | `error_handler_declared` | source mentions `exception_handler`, `errorhandler`, `ErrorHandler`, `error_middleware`, `recover()`, `@ControllerAdvice` | #79 web-api row 4; U14 (static half) |
| `web-api` | `config_from_environment` | source mentions `os.environ`, `getenv`, `dotenv`, `process.env`, `pydantic_settings`, `BaseSettings`, `os.Getenv`, `viper` | O5 (positive half); Twelve-Factor III |
| `web-api` | `api_spec_present` | `openapi.*` / `swagger.*` / `*.proto` / `schema.graphql` present, or `FastAPI(` / `apispec` / `swagger` in source | ASVS V13 (documented API surface) |
| `web-app` | `i18n_catalog_present` | `locales/` `i18n/` `lang/` directory content, `*.po`, `*.pot`, `messages.*.json`, or `i18next` / `gettext` / `react-intl` / `formatjs` in source | U17 |
| `web-app` | `responsive_viewport_declared` | an HTML/template file declares `<meta name="viewport"` | U10 (static half) |
| `web-app` | `bundle_budget_declared` | `.size-limit*`, `bundlesize*`, `budget.json`, `lighthouserc*`, or `"size-limit"` / `"bundlesize"` in `package.json` | U12 (the budget declaration; the ratchet itself is #79 phase 2) |
| `web-app` | `error_page_declared` | `404.*` / `500.*` / `error.*` page, or `ErrorBoundary` / `errorElement` / `error.tsx` in source | U14 (users see a designed error, not a stack) |
| `web-app` | `structured_logging_configured` | as web-api | O7 |
| `ml` | `model_card_present` | `MODEL_CARD.md` / `model_card.md` / `docs/model_card*` | M6 (Mitchell et al. 2019) |
| `ml` | `datasheet_present` | `DATASHEET.md` / `datasheet.md` / `docs/datasheet*` | M6 (Gebru et al. 2021) |
| `ml` | `data_schema_present` | `*.schema.json`, `schema.{json,yaml,yml}`, `schemas/` content, or `pandera` / `great_expectations` / `tfdv` / `pydantic` in source | M1 |
| `ml` | `seed_fixed` | source mentions `manual_seed`, `random.seed`, `np.random.seed`, `set_seed`, `seed_everything`, `random_state=`, `PYTHONHASHSEED` | M5 (reproducibility) |
| `ml` | `dependency_lockfile` | `requirements*.txt`, `poetry.lock`, `uv.lock`, `Pipfile.lock`, `conda-lock.yml`, `environment.yml` | M5 / S8 (presence half; lock *integrity* is #76) |
| `ml` | `evaluation_script_present` | `eval*.py`, `evaluate*.py`, `evaluation/` content, `scripts/eval*`, `Makefile` `eval` target | M7 / M9 (the receipt the future ratchet reads) |
| `ml` | `baseline_recorded` | `BASELINE*.md`, `baselines/` content, `metrics/*.json`, `.ml-baseline*` | M9 (simple baseline is recorded) |
| `ml` | `pipeline_integration_test` | `tests/**/test_*pipeline*`, `test_*e2e*`, `test_*end_to_end*`, `test_*integration*` | M11 |
| `ml` | `numerical_stability_guard` | source mentions `isnan`, `isfinite`, `nan_to_num`, `assert_all_finite`, `allclose`, `torch.isfinite` | M16 |
| `ml` | `rollback_command_declared` | `Makefile` `rollback` target, `scripts/rollback*`, `rollback*.sh`, or `rollback` in a deploy workflow | M12 / O11 |
| `embedded` | `watchdog_configured` | source mentions `watchdog`, `wdt`, `IWDG`, `WWDG`, `WDT_`, `wdog` | #79 embedded row 4 |
| `embedded` | `static_analysis_configured` | `.clang-tidy`, `cppcheck*`, `*.cppcheck`, `misra*`, `.pc-lint*`, or `cppcheck` / `clang-tidy` / `MISRA` in a Makefile / CMake / CI file | #79 embedded row 6 |
| `embedded` | `hal_abstraction_present` | `hal/`, `HAL/`, `bsp/`, `drivers/` content, or `*hal*.h` | #79 embedded row 7 (off-target testability) |
| `embedded` | `linker_script_present` | `*.ld`, `*.lds`, `*.icf`, `*.scat` | deterministic memory layout (#79 embedded row 1) |
| `embedded` | `host_tests_present` | `test/` or `tests/` content | #79 embedded row 7 |
| `embedded` | `toolchain_pinned` | `toolchain*.cmake`, `platformio.ini`, `Makefile` mentioning a cross compiler (`arm-none-eabi`, `avr-gcc`, `riscv`, `xtensa`, `CROSS_COMPILE`), or `rust-toolchain*` | reproducible firmware builds |
| `data-pipeline` | `pipeline_definition_present` | `dags/`, `pipelines/`, `flows/`, `jobs/` content, or `@dag` / `@flow` / `@task` / `@asset` / `airflow` / `prefect` / `dagster` / `luigi` / `dbt` in source | M11 analogue (the pipeline is code) |
| `data-pipeline` | `data_schema_present` | as ml | M1 |
| `data-pipeline` | `data_quality_checks` | source mentions `great_expectations`, `expect_`, `pandera`, `soda`, `dbt test`, `check_`, `assert_frame_equal`, `validate(` | ML Test Score Data 1/2 |
| `data-pipeline` | `structured_logging_configured` | as web-api | O7 |
| `data-pipeline` | `pipeline_integration_test` | as ml | M11 |
| `data-pipeline` | `dependency_lockfile` | as ml | M5 / S8 |
| `data-pipeline` | `backfill_or_rollback_declared` | `rollback_command_declared` globs, or `backfill` in a Makefile / `scripts/` | O11 (re-runnable, reversible loads) |

### Checks each archetype requires to be non-`noop`

| Archetype | `must_be_non_noop` | Why |
|---|---|---|
| `library` | `00_build`, `40_test` | a library with no importable package or no tests is hollow |
| `cli` | `00_build`, `40_test` | same |
| `web-api` | `40_test`, `50_security` | untested / unscanned network surface |
| `web-app` | `15_a11y`, `40_test` | `15_a11y` inspecting no HTML in a declared web app is the #130 vacuity case |
| `ml` | `40_test` | untested model code |
| `embedded` | — | the Python check set does not run on firmware; `18_api_contracts` (#130) joins here when it lands |
| `data-pipeline` | `40_test` | untested pipeline code |

Required-to-inspect implies required-to-run: a listed check absent from the run's
expected set is a violation too (the archetype demands evidence the run cannot produce).

## Edge cases

| Case | Behaviour |
|---|---|
| multiple archetypes | features unioned by id (shared ids like `structured_logging_configured` appear once); `must_be_non_noop` pairs are per archetype, so one hollow check can be blamed on several archetypes |
| none declared | `21_archetype` ⇒ `noop`; no non-noop clause; identical verdict to pre-feature |
| unknown archetype | `load_config` raises; `required_features` raises; the gate exits 1 before running checks (the language probe already fails closed on a broken config) |
| a feature's evidence lives in a skipped dir only | absent — vendored/build output is never evidence |
| unreadable / huge file | skipped silently for that file; other candidates still count |
| `must_be_non_noop` check `MISSING` or `!TAMPERED` | already failing; the non-noop clause adds nothing |

## Non-goals (phase 1)

- No per-project override / relaxation of a feature list, no catalog version pinning
  beyond `CATALOG_VERSION` (recorded in the log). Both are ADR-0062 follow-ups; the
  catalog is data, so both are additive.
- No behavioural verification ("the health endpoint responds"), no rendered-DOM checks
  (U10/U13), no ratchets over evaluation receipts (M7/M8) — they need a run, a browser or
  a baseline, which this deterministic presence gate does not have.
- Playbooks are read by the agent; nothing verifies they were followed.

## Tests

- Unit (`tests/unit/test_archetypes.py`, `test_spine.py`): catalog integrity (every
  archetype's features carry at least one glob, a compilable regex, a title and a
  justification; `must_be_non_noop` ids look like check ids; `CATALOG` keys ==
  `spine.ARCHETYPES`), spine parse + fail-closed unknown, `required_features` union /
  order / unknown, `evaluate` on fixture trees (present via path, present via content
  with `path:line` evidence, absent, skipped dir, huge file, unreadable file), exact
  `render_report`, `non_noop_violations` (noop, absent, pass).
- Integration (`tests/integration/test_archetype_gate.py`, excluded from mutmut like the
  other shell drivers): the real `verify.sh` on fixtures — off (`noop`, PASS), all present
  (PASS), one absent (FAIL naming it), and a declared `web-app` with no HTML where
  `15_a11y` is `noop` — the run turns FAIL with *"required to inspect something by
  archetype web-app"* although every receipt is non-failing.
