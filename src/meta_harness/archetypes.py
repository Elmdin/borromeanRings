"""Application archetypes — what an app *of its kind* must have, as deterministic gates.

The gate decides how well code is written and what engineering surround exists; it does
not decide whether an application is *complete for its kind*. A web API without a health
endpoint, a CLI without a documented entry point, an ML project without a model card —
each passes every quality check while missing something non-negotiable for that
archetype (#79). This module is the catalog of those requirements plus the pure
evaluator the ``21_archetype`` check and the gate's verdict consume.

Three layers, deliberately separated (the durable "what" from the volatile "how"):

- **Features** — binary, deterministic predicates over files: a path exists, or a file's
  text matches a regular expression. Nothing here calls a model, the network, a build or
  the program. If a requirement cannot be decided that way it is not a feature.
- **``must_be_non_noop``** — checks that, for this archetype, must have inspected
  something. A ``noop`` receipt is non-failing on its own (ADR-0049); a declared archetype
  is what turns "inspected nothing" from legitimate into a failure (#130, #138).
- **Playbooks** — advisory prose the wrapped agent reads. Never gated, never parsed.

The catalog is immutable data (frozen dataclasses) keyed by :data:`meta_harness.spine.ARCHETYPES`.
See docs/specs/SPEC-archetypes.md and ADR-0062.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from meta_harness.spine import ARCHETYPES

#: Bumped whenever a feature list or a must-be-non-noop set changes (recorded in the log).
CATALOG_VERSION = "1"
#: Directories never searched for evidence: vendored, generated, or borromeanRings's own.
SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        "vendor",
        ".meta-harness",
        "mutants",
        "__pycache__",
        "site-packages",
        ".tox",
        ".mypy_cache",
    }
)
#: Files larger than this are never read for a content match (presence still counts).
MAX_FILE_BYTES = 1024 * 1024


@dataclass(frozen=True)
class Feature:
    """One required capability and the deterministic predicate that detects it.

    Present when some regular file (outside :data:`SKIP_DIRS`) matches one of the
    presence globs ``paths``, **or** some file matching one of the ``content`` globs has
    text matching ``pattern`` (a regex; case-insensitive, multiline). Either half may be
    empty; a feature must declare at least one.
    """

    id: str
    title: str
    paths: tuple[str, ...] = ()
    content: tuple[str, ...] = ()
    pattern: str = ""
    why: str = ""


@dataclass(frozen=True)
class Archetype:
    """A kind of application: its required features, the checks it forbids from being
    hollow, and the advisory playbook."""

    name: str
    summary: str
    features: tuple[Feature, ...]
    must_be_non_noop: tuple[str, ...]
    playbook: str


@dataclass(frozen=True)
class FeatureResult:
    """One feature's verdict on one project: present or not, with the evidence path."""

    feature_id: str
    title: str
    present: bool
    evidence: str


@dataclass(frozen=True)
class Report:
    """The evaluation of a project against its declared archetypes."""

    archetypes: tuple[str, ...]
    results: tuple[FeatureResult, ...]
    must_be_non_noop: tuple[tuple[str, str], ...]


# --- shared predicates ---------------------------------------------------------------------

_SOURCE = ("**/*.py", "**/*.js", "**/*.ts", "**/*.tsx", "**/*.go", "**/*.rs", "**/*.java")
_MANIFESTS = ("pyproject.toml", "setup.py", "setup.cfg", "package.json", "Cargo.toml", "go.mod")
_BUILD_FILES = ("Makefile", "makefile", "CMakeLists.txt", "**/*.cmake", ".github/workflows/*.yml")
_C_SOURCE = ("**/*.c", "**/*.h", "**/*.cpp", "**/*.hpp", "**/*.rs")

LICENSE_PRESENT = Feature(
    "license_present", "a license file is present", paths=("LICENSE*", "COPYING*"), why="ADR-0012"
)
CHANGELOG_PRESENT = Feature(
    "changelog_present",
    "a changelog is present",
    paths=("CHANGELOG*", "HISTORY*"),
    why="Keep a Changelog; ADR-0028",
)
STRUCTURED_LOGGING = Feature(
    "structured_logging_configured",
    "structured logging is configured",
    content=_SOURCE,
    pattern=r"structlog|json_?log|jsonlogger|logging\.config|\bpino\b|\bwinston\b|zerolog|\bslog\b",
    why="O7 — logs are structured event streams",
)
DATA_SCHEMA = Feature(
    "data_schema_present",
    "input/feature expectations are captured in a schema",
    paths=("**/*.schema.json", "schema.json", "schema.yaml", "schema.yml", "schemas/**/*"),
    content=_SOURCE,
    pattern=r"pandera|great_expectations|tfdv|pydantic|jsonschema",
    why="M1 — feature expectations in a schema",
)
LOCKFILE = Feature(
    "dependency_lockfile",
    "dependencies are pinned in a lockfile",
    paths=(
        "requirements*.txt",
        "poetry.lock",
        "uv.lock",
        "Pipfile.lock",
        "conda-lock.yml",
        "environment.yml",
    ),
    why="M5 / S8 — reproducible environments (lock integrity is #76)",
)
PIPELINE_TEST = Feature(
    "pipeline_integration_test",
    "an end-to-end pipeline test exists",
    paths=(
        "tests/**/test_*pipeline*",
        "tests/**/test_*e2e*",
        "tests/**/test_*end_to_end*",
        "tests/**/test_*integration*",
    ),
    why="M11 — full pipeline integration test",
)
ROLLBACK = Feature(
    "rollback_command_declared",
    "a rollback command is declared",
    paths=("scripts/rollback*", "**/rollback*.sh"),
    content=("Makefile", "makefile", ".github/workflows/*.yml"),
    pattern=r"rollback",
    why="O11 / M12 — every release can be rolled back",
)

# --- the catalog ----------------------------------------------------------------------------

_LIBRARY = Archetype(
    "library",
    "an importable package consumed by other code",
    (
        Feature("package_manifest", "a package manifest is present", paths=_MANIFESTS, why="#79"),
        Feature(
            "version_declared",
            "a version is declared",
            paths=("VERSION",),
            content=("pyproject.toml", "setup.cfg", "package.json", "Cargo.toml"),
            pattern=r'^\s*(version\s*=|"version"\s*:)',
            why="Semantic Versioning; ADR-0048",
        ),
        LICENSE_PRESENT,
        CHANGELOG_PRESENT,
    ),
    ("00_build", "40_test"),
    """\
Design the public surface deliberately: export from the package root, keep everything else
private (leading underscore / __all__), and treat a removed or renamed public symbol as a
breaking change (34_api_diff, ADR-0040). Version semantically and write the changelog entry
with the change, not at release time. Ship type information (py.typed / .d.ts). Depend
loosely (lower bounds, no pins in a library) so consumers can resolve. Test the public
contract, not internals; a docstring on every public symbol is the API reference.""",
)

_CLI = Archetype(
    "cli",
    "a command-line tool run by people or scripts",
    (
        Feature(
            "entrypoint_declared",
            "an invocable entry point is declared",
            paths=("**/__main__.py",),
            content=("pyproject.toml", "package.json", "Cargo.toml", "*.sh"),
            pattern=r"\[project\.scripts\]|\"bin\"\s*:|\[\[bin\]\]|^#!\s*/",
            why="#79 — a CLI has an entry point",
        ),
        Feature(
            "usage_documented",
            "usage is documented in the README",
            content=("README*", "docs/USAGE*"),
            pattern=r"^#{1,6}\s.*\b(usage|quick ?start|getting started|run|install|how to)\b",
            why="Nielsen #10 — help and documentation",
        ),
        LICENSE_PRESENT,
        CHANGELOG_PRESENT,
    ),
    ("00_build", "40_test"),
    """\
Follow the conventions scripts rely on: exit 0 only on success and a distinct non-zero code
per failure class; errors to stderr, results to stdout; `--help` and `--version`; a
machine-readable output mode (`--json`) next to the human one; no interactive prompts when
stdin is not a TTY. Read configuration from flags, then environment, then a config file,
in that precedence. Never print secrets. Keep the entry point thin and the logic in an
importable module so it is testable without spawning a process.""",
)

_WEB_API = Archetype(
    "web-api",
    "a network service exposing HTTP/RPC endpoints",
    (
        Feature(
            "health_endpoint_declared",
            "a health/readiness endpoint route is declared",
            content=_SOURCE,
            pattern=r"/health(z)?\b|/ready(z)?\b|/live(z)?\b|/ping\b",
            why="O6 — distinct liveness and readiness endpoints",
        ),
        STRUCTURED_LOGGING,
        Feature(
            "input_validation_layer",
            "a boundary input-validation layer is declared",
            content=_SOURCE + _MANIFESTS,
            pattern=r"pydantic|marshmallow|jsonschema|cerberus|voluptuous|\bzod\b|\bjoi\b|\byup\b"
            r"|class-validator|validator/v10",
            why="#79 web-api row 1; OWASP ASVS V5",
        ),
        Feature(
            "auth_mechanism_declared",
            "an authentication mechanism is declared",
            content=_SOURCE + _MANIFESTS,
            pattern=r"\bjwt\b|oauth|HTTPBearer|HTTPBasic|passport|authlib|django\.contrib\.auth"
            r"|Authorization",
            why="#79 web-api row 2; ASVS V2/V4",
        ),
        Feature(
            "rate_limiter_declared",
            "a rate limiter is declared",
            content=_SOURCE + _MANIFESTS,
            pattern=r"slowapi|ratelimit|throttl|express-rate-limit|limiter|tollbooth",
            why="#79 web-api row 3",
        ),
        Feature(
            "error_handler_declared",
            "a non-leaking error handler is declared",
            content=_SOURCE,
            pattern=r"exception_handler|errorhandler|ErrorHandler|error_middleware|recover\(\)"
            r"|@ControllerAdvice",
            why="#79 web-api row 4; U14",
        ),
        Feature(
            "config_from_environment",
            "configuration is read from the environment",
            content=_SOURCE,
            pattern=r"os\.environ|getenv|dotenv|process\.env|pydantic_settings|BaseSettings"
            r"|os\.Getenv|\bviper\b",
            why="O5 — config in the environment (Twelve-Factor III)",
        ),
        Feature(
            "api_spec_present",
            "the API surface is specified",
            paths=("openapi.*", "**/openapi.*", "swagger.*", "**/*.proto", "**/schema.graphql"),
            content=_SOURCE,
            pattern=r"openapi|swagger|FastAPI\(|apispec|graphql",
            why="ASVS V13 — a documented API surface",
        ),
    ),
    ("40_test", "50_security"),
    """\
Validate at the boundary with a schema library and reject early with a field-level 4xx.
Authenticate every non-public route; authorise per resource, least privilege; never roll
your own crypto or session store. Rate-limit per key/IP with 429 + Retry-After. One error
handler maps exceptions to a stable error envelope — no stack traces, no internals, no
secrets in responses; log the detail server-side as a structured event with a request id.
Expose /livez (process up) and /readyz (dependencies reachable) separately. All config and
secrets from the environment; fail at startup when a required one is missing. Publish the
OpenAPI document and treat it as the contract 34_api_diff would guard.""",
)

_WEB_APP = Archetype(
    "web-app",
    "a user-facing browser application",
    (
        Feature(
            "i18n_catalog_present",
            "user-facing strings are externalised (i18n catalog)",
            paths=("locales/**/*", "i18n/**/*", "lang/**/*", "**/*.po", "**/*.pot"),
            content=_SOURCE,
            pattern=r"i18next|gettext|react-intl|formatjs|\bi18n\b",
            why="U17 — strings externalised for translation",
        ),
        Feature(
            "responsive_viewport_declared",
            "a responsive viewport is declared",
            content=("**/*.html", "**/*.htm", "**/*.jinja*", "**/*.j2", "**/*.ejs", "**/*.vue"),
            pattern=r'<meta\s+name\s*=\s*["\']viewport["\']',
            why="U10 — content reflows at narrow viewports (static half)",
        ),
        Feature(
            "bundle_budget_declared",
            "a bundle-size budget is declared",
            paths=(".size-limit*", "bundlesize*", "budget.json", "lighthouserc*"),
            content=("package.json",),
            pattern=r"size-limit|bundlesize|bundlewatch",
            why="U12 — bundle-size ratchet (the declaration; the ratchet is phase 2)",
        ),
        Feature(
            "error_page_declared",
            "a designed error page / boundary is declared",
            paths=("**/404.html", "**/500.html", "**/error.html", "**/error.tsx", "**/error.vue"),
            content=_SOURCE,
            pattern=r"ErrorBoundary|errorElement|error_page|errorhandler|handler404|handler500",
            why="U14 — users see a designed error, not a stack",
        ),
        STRUCTURED_LOGGING,
    ),
    ("15_a11y", "40_test"),
    """\
Show status for every asynchronous action (a loading state per long operation) and make
destructive actions confirmable or undoable (Nielsen #1, #5). Write error messages in plain
language that name the field and suggest the fix (WCAG 3.3.1/3.3.3). Keep help and
navigation in one consistent place across pages (WCAG 3.2.3/3.2.6). Externalise every
user-facing string; declare `lang` on the document; test reflow at 320 px without
two-dimensional scrolling. Keep a bundle budget and measure it in CI. Run a rendered a11y
tool (axe) on the heavy lane — the static gate (15_a11y) only sees presence facts.""",
)

_ML = Archetype(
    "ml",
    "a project that trains, evaluates or serves a model",
    (
        Feature(
            "model_card_present",
            "a model card is present",
            paths=("MODEL_CARD.md", "model_card.md", "docs/model_card*", "docs/MODEL_CARD*"),
            why="M6 — Mitchell et al. 2019",
        ),
        Feature(
            "datasheet_present",
            "a dataset datasheet is present",
            paths=("DATASHEET.md", "datasheet.md", "docs/datasheet*", "docs/DATASHEET*"),
            why="M6 — Gebru et al. 2021",
        ),
        DATA_SCHEMA,
        Feature(
            "seed_fixed",
            "random seeds are fixed",
            content=_SOURCE,
            pattern=r"manual_seed|random\.seed|np\.random\.seed|set_seed|seed_everything"
            r"|random_state\s*=|PYTHONHASHSEED",
            why="M5 — training is reproducible",
        ),
        LOCKFILE,
        Feature(
            "evaluation_script_present",
            "an evaluation script is present",
            paths=("**/eval*.py", "**/evaluate*.py", "evaluation/**/*", "scripts/eval*"),
            why="M7 / M9 — the evaluation receipt a ratchet can read",
        ),
        Feature(
            "baseline_recorded",
            "a baseline comparison is recorded",
            paths=("BASELINE*", "baselines/**/*", "metrics/*.json", ".ml-baseline*"),
            why="M9 — the deployed model is not beaten by the simple baseline",
        ),
        PIPELINE_TEST,
        Feature(
            "numerical_stability_guard",
            "a NaN/Inf guard is present",
            content=_SOURCE,
            pattern=r"isnan|isfinite|nan_to_num|assert_all_finite|allclose",
            why="M16 — numerically stable",
        ),
        ROLLBACK,
    ),
    ("40_test",),
    """\
Treat data as code: a schema for every input, validated on training and serving data; unit
tests for feature functions; PII out of fixtures and logs. Make training reproducible —
seeds, pinned data version, locked dependencies — so two runs of one commit agree. Record
the simple baseline and the primary metric per declared slice, then ratchet them (never a
fixed target). Validate the model before serving and keep the previous artefact so
rollback is one command. Write the model card and datasheet with the model, not after.""",
)

_EMBEDDED = Archetype(
    "embedded",
    "firmware for a microcontroller (bare-metal or RTOS)",
    (
        Feature(
            "watchdog_configured",
            "a watchdog is configured",
            content=_C_SOURCE,
            pattern=r"watchdog|\bwdt\b|IWDG|WWDG|WDT_|wdog",
            why="#79 embedded row 4",
        ),
        Feature(
            "static_analysis_configured",
            "static analysis / MISRA tooling is configured",
            paths=(".clang-tidy", "cppcheck*", "**/*.cppcheck", "misra*", ".pc-lint*"),
            content=_BUILD_FILES,
            pattern=r"cppcheck|clang-tidy|misra|pc-lint",
            why="#79 embedded row 6",
        ),
        Feature(
            "hal_abstraction_present",
            "a hardware-abstraction layer is present",
            paths=("hal/**/*", "HAL/**/*", "bsp/**/*", "drivers/**/*", "**/*hal*.h"),
            why="#79 embedded row 7 — off-target testability",
        ),
        Feature(
            "linker_script_present",
            "a linker script fixes the memory layout",
            paths=("**/*.ld", "**/*.lds", "**/*.icf", "**/*.scat"),
            why="#79 embedded row 1 — deterministic memory",
        ),
        Feature(
            "host_tests_present",
            "host (off-target) tests are present",
            paths=("test/**/*", "tests/**/*"),
            why="#79 embedded row 7",
        ),
        Feature(
            "toolchain_pinned",
            "the cross toolchain is pinned",
            paths=("toolchain*.cmake", "platformio.ini", "rust-toolchain*"),
            content=_BUILD_FILES,
            pattern=r"arm-none-eabi|avr-gcc|riscv|xtensa|CROSS_COMPILE",
            why="reproducible firmware builds",
        ),
    ),
    (),
    """\
No heap after init and never in an ISR; static or pool allocation; a documented stack
budget per task. Configure every pin before use, pair init/deinit, no floating inputs.
Keep ISRs short and non-blocking, share state through `volatile` + critical sections or
lock-free queues, defer work to the main loop. Configure *and* kick the watchdog from the
main loop, never from a timer ISR. Define the safe state on reset/fault and enable
brown-out detection. Compile with -Wall -Wextra -Werror, run cppcheck/clang-tidy under a
MISRA profile, and keep logic behind a HAL so it runs in host tests.""",
)

_DATA_PIPELINE = Archetype(
    "data-pipeline",
    "batch/stream data movement and transformation",
    (
        Feature(
            "pipeline_definition_present",
            "the pipeline is defined as code",
            paths=("dags/**/*", "pipelines/**/*", "flows/**/*", "jobs/**/*"),
            content=_SOURCE,
            pattern=r"@dag\b|@flow\b|@task\b|@asset\b|airflow|prefect|dagster|luigi|\bdbt\b",
            why="the pipeline is code, not a console",
        ),
        DATA_SCHEMA,
        Feature(
            "data_quality_checks",
            "data-quality checks are declared",
            content=_SOURCE + ("**/*.yml", "**/*.yaml", "**/*.sql"),
            pattern=r"great_expectations|expect_|pandera|\bsoda\b|dbt test|assert_frame_equal",
            why="ML Test Score — Data 1/2",
        ),
        STRUCTURED_LOGGING,
        PIPELINE_TEST,
        LOCKFILE,
        Feature(
            "backfill_or_rollback_declared",
            "a backfill or rollback command is declared",
            paths=ROLLBACK.paths + ("scripts/backfill*", "**/backfill*"),
            content=ROLLBACK.content,
            pattern=r"rollback|backfill",
            why="O11 — re-runnable, reversible loads",
        ),
    ),
    ("40_test",),
    """\
Make every step idempotent and every load re-runnable for a date range (backfill) so a
failure is retried, not hand-fixed. Validate inputs against the schema at the boundary and
quarantine bad rows instead of dropping them silently. Log structured events with a run id
and row counts per step; alert on freshness and volume, not on the absence of errors.
Pin dependencies and the data version; test the whole pipeline end-to-end on a small
fixture. Keep secrets in the environment and PII out of fixtures and logs.""",
)

CATALOG: Mapping[str, Archetype] = {
    a.name: a for a in (_LIBRARY, _CLI, _WEB_API, _WEB_APP, _ML, _EMBEDDED, _DATA_PIPELINE)
}


# --- selection -------------------------------------------------------------------------------


def _archetypes(names: Sequence[str]) -> tuple[Archetype, ...]:
    """Resolve names to catalog entries; unknown ⇒ ``ValueError`` (fail closed)."""
    unknown = [name for name in names if name not in CATALOG]
    if unknown:
        raise ValueError(
            f"unknown archetype(s): {', '.join(unknown)} — known: {', '.join(ARCHETYPES)}"
        )
    return tuple(CATALOG[name] for name in names)


def required_features(archetypes: Sequence[str]) -> tuple[Feature, ...]:
    """The declared archetypes' features, unioned by id, in first-appearance order."""
    seen: dict[str, Feature] = {}
    for archetype in _archetypes(archetypes):
        for feature in archetype.features:
            seen.setdefault(feature.id, feature)
    return tuple(seen.values())


def non_noop_checks(archetypes: Sequence[str]) -> tuple[tuple[str, str], ...]:
    """``(check_id, archetype)`` pairs the declared archetypes require to be non-noop, sorted."""
    pairs = {
        (check, archetype.name)
        for archetype in _archetypes(archetypes)
        for check in archetype.must_be_non_noop
    }
    return tuple(sorted(pairs))


# --- evaluation ------------------------------------------------------------------------------


def _glob_regex(glob: str) -> re.Pattern[str]:
    """Translate a root-relative glob (``**/`` = any depth) to an anchored regex."""
    out = ""
    i = 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        else:
            out += {"*": "[^/]*", "?": "[^/]"}.get(glob[i], re.escape(glob[i]))
            i += 1
    return re.compile(f"^{out}$")


def _project_files(root: Path) -> tuple[str, ...]:
    """Every regular file under ``root`` as sorted root-relative POSIX paths, pruning SKIP_DIRS."""
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        rel = Path(dirpath).relative_to(root).as_posix()
        prefix = "" if rel == "." else rel + "/"
        found.extend(prefix + name for name in sorted(filenames))
    return tuple(found)


def _matching(files: Sequence[str], globs: Sequence[str]) -> list[str]:
    """Files matching any glob, in glob order then path order (deterministic evidence)."""
    return [rel for glob in globs for rel in files if _glob_regex(glob).match(rel)]


def _content_evidence(root: Path, rel: str, pattern: re.Pattern[str]) -> str:
    """``rel:line`` of the first match in the file, or ``""`` (unreadable / oversized / none)."""
    path = root / rel
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return ""
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    match = pattern.search(text)
    if match is None:
        return ""
    return f"{rel}:{text.count(chr(10), 0, match.start()) + 1}"


def _evidence(root: Path, files: Sequence[str], feature: Feature) -> str:
    """The first evidence for ``feature``: a presence path, else a ``path:line`` content hit."""
    present = _matching(files, feature.paths)
    if present:
        return present[0]
    pattern = re.compile(feature.pattern, re.MULTILINE | re.IGNORECASE)
    for rel in _matching(files, feature.content):
        hit = _content_evidence(root, rel, pattern)
        if hit:
            return hit
    return ""


def evaluate(project_root: Path | str, archetypes: Sequence[str]) -> Report:
    """Evaluate ``project_root`` against the declared archetypes' required features.

    Pure file inspection: presence and regex content matches only. Unknown archetype ⇒
    ``ValueError``.
    """
    root = Path(project_root)
    features = required_features(archetypes)
    files = _project_files(root) if features else ()
    results = tuple(
        FeatureResult(f.id, f.title, bool(hit), hit)
        for f in features
        for hit in (_evidence(root, files, f),)
    )
    return Report(tuple(archetypes), results, non_noop_checks(archetypes))


# --- reporting -------------------------------------------------------------------------------


def render_report(report: Report) -> str:
    """Deterministic text: one line per feature, a summary, and the must-be-non-noop list."""
    names = ", ".join(report.archetypes)
    lines = [f"archetypes: {names} (catalog v{CATALOG_VERSION})"]
    for result in report.results:
        mark = "ok     " if result.present else "MISSING"
        suffix = f"  [{result.evidence}]" if result.present else ""
        lines.append(f"  {mark}  {result.feature_id} — {result.title}{suffix}")
    missing = sum(1 for r in report.results if not r.present)
    total = len(report.results)
    if missing:
        lines.append(f"{missing} of {total} required feature(s) MISSING for archetypes {names}.")
    else:
        lines.append(f"all {total} required feature(s) present for archetypes {names}.")
    pairs = ", ".join(f"{check} ({name})" for check, name in report.must_be_non_noop)
    lines.append(f"must be non-noop: {pairs or '(none)'}")
    return "\n".join(lines) + "\n"


def non_noop_violations(archetypes: Sequence[str], statuses: Mapping[str, str]) -> tuple[str, ...]:
    """Messages for checks an archetype requires to inspect something but which did not.

    ``statuses`` maps each check in the run's expected set to its receipt status. A
    ``noop`` receipt violates; so does a check absent from the set (required-to-inspect
    implies required-to-run). Empty ⇒ no violation.
    """
    out = []
    for check, name in non_noop_checks(archetypes):
        if check not in statuses:
            out.append(
                f"{check}: not in [checks].required but required to inspect something "
                f"by archetype {name}"
            )
        elif statuses[check] == "noop":
            out.append(f"{check}: NOOP but required to inspect something by archetype {name}")
    return tuple(out)
