"""T3 **project profiler** — the enforcement-coverage-map *selector*.

Enforcing every practice on every project is wrong (CS130: right-size to risk).
The profiler classifies a project's **type**, names its **quality-attribute
needs**, offers **stack pathways with trade-offs**, and emits a **runnable
`borromeanrings.toml`** turning the right coverage-map rows on at the right tier.

It is **advisory**: it *proposes* config; the human *chooses*; borromeanRings
*enforces* the choice (VISION §6 red line — it never mutates the live config, never
decides what to build). The deterministic core (archetype→profile→config) is
model-free and unit-tested; only description→archetype is injected (the same seam
pattern as :mod:`meta_harness.critic`). Its output must round-trip through
:func:`meta_harness.spine.load_config` — a gate-able artifact, not prose.
See docs/specs/SPEC-profiler.md, ADR-0024.
"""

from collections.abc import Callable
from dataclasses import dataclass

# The base code-quality/hygiene floor every project gets. Governance checks
# (git-identity, layout, collaboration) are the maintainer's to declare separately.
_BASE_REQUIRED: tuple[str, ...] = (
    "00_build",
    "05_hygiene",
    "10_format",
    "20_lint",
    "30_typecheck",
    "40_test",
    "50_security",
)


@dataclass(frozen=True)
class StackOption:
    """One candidate stack and its one-line trade-off (generate alternatives)."""

    name: str
    tradeoffs: str


@dataclass(frozen=True)
class EnforcementProfile:
    """The recommended enforcement posture for a project archetype."""

    archetype: str
    quality_priorities: tuple[str, ...]  # CS130 quality attributes, highest first
    required_checks: tuple[str, ...]
    heavy_checks: tuple[str, ...]  # CI-tier (e.g. mutation); ADR-0022
    stack_options: tuple[StackOption, ...]
    notes: str


# Injected: free-text project description -> archetype key. Model is a secret.
Classifier = Callable[[str], str]

_DEFAULT_ARCHETYPE = "library"  # conservative fallback — never an empty gate

PROFILES: dict[str, EnforcementProfile] = {
    "library": EnforcementProfile(
        archetype="library",
        quality_priorities=("correctness", "maintainability", "security", "performance"),
        required_checks=_BASE_REQUIRED,
        heavy_checks=("60_mutation",),  # a reused API needs strong tests
        stack_options=(
            StackOption("Python package (src layout)", "great ecosystem; runtime types only"),
            StackOption("Go module", "single binary, strong stdlib; more boilerplate"),
            StackOption("Rust crate", "memory-safe, fast; steeper learning curve"),
        ),
        notes="Public API stability and test strength dominate; ratchet mutation.",
    ),
    "cli": EnforcementProfile(
        archetype="cli",
        quality_priorities=("correctness", "maintainability", "usability"),
        required_checks=_BASE_REQUIRED,
        heavy_checks=(),  # lighter — low blast radius; keep the gate fast
        stack_options=(
            StackOption("Python + Typer", "fast to build; needs an interpreter"),
            StackOption("Go + Cobra", "single static binary; verbose"),
            StackOption("Rust + clap", "fast, portable binary; slower iteration"),
        ),
        notes="Low blast radius; keep enforcement light (no heavy mutation lane).",
    ),
    "web_api": EnforcementProfile(
        archetype="web_api",
        quality_priorities=("security", "correctness", "availability", "performance"),
        required_checks=_BASE_REQUIRED,
        heavy_checks=("60_mutation",),
        stack_options=(
            StackOption("Python + FastAPI", "typed, fast to build; async care needed"),
            StackOption("Go + chi/net-http", "high throughput, single binary; more code"),
            StackOption("TypeScript + Hono", "edge-ready, full-stack JS; runtime sprawl"),
        ),
        notes="Security is the top driver; add dependency/secret scanning as they land.",
    ),
    "data_pipeline": EnforcementProfile(
        archetype="data_pipeline",
        quality_priorities=("correctness", "reproducibility", "performance"),
        required_checks=_BASE_REQUIRED,
        heavy_checks=("60_mutation",),
        stack_options=(
            StackOption("Python + Polars/dbt", "expressive, testable; single-node limits"),
            StackOption("Spark", "scales horizontally; heavy ops footprint"),
            StackOption("SQL + orchestrator", "declarative, auditable; less general compute"),
        ),
        notes="Correctness + reproducibility dominate; pin deps, ratchet mutation.",
    ),
    "ml_service": EnforcementProfile(
        archetype="ml_service",
        quality_priorities=("correctness", "reliability", "performance", "security"),
        required_checks=_BASE_REQUIRED,
        heavy_checks=("60_mutation",),
        stack_options=(
            StackOption("Python + FastAPI + Torch", "ecosystem fit; GPU/runtime weight"),
            StackOption("Python + Triton/ONNX serving", "optimized inference; more infra"),
            StackOption("Go gateway + Python model svc", "fast edge, isolated model; two langs"),
        ),
        notes="Guard the serving layer (correctness+reliability) distinctly from the model.",
    ),
}


def known_archetypes() -> tuple[str, ...]:
    """The archetype keys the profiler recognises."""
    return tuple(PROFILES)


def profile_for(archetype: str) -> EnforcementProfile:
    """Look up an archetype's profile; **fail safe** to the default for unknowns."""
    return PROFILES.get(archetype, PROFILES[_DEFAULT_ARCHETYPE])


def classify(description: str, classifier: Classifier) -> str:
    """Classify a project description into an archetype via the injected classifier.

    Fail-safe: a result outside :func:`known_archetypes` falls back to the default —
    borromeanRings never turns an unclear classification into an empty/invalid gate.
    """
    guess = classifier(description).strip()
    return guess if guess in PROFILES else _DEFAULT_ARCHETYPE


def recommend(description: str, classifier: Classifier) -> EnforcementProfile:
    """Classify a description, then return the matching enforcement profile."""
    return profile_for(classify(description, classifier))


def _toml_array(items: tuple[str, ...]) -> str:
    """Render a tuple of strings as a single-line TOML array."""
    return "[" + ", ".join(f'"{item}"' for item in items) + "]"


def render_config(
    profile: EnforcementProfile,
    *,
    language: str = "python",
    package: str = "",
    src_dir: str = "src",
    tests_dir: str = "tests",
) -> str:
    """Emit a candidate ``borromeanrings.toml`` for a profile.

    The maintainer edits and adopts it; borromeanRings then enforces it. The output
    parses via :func:`meta_harness.spine.load_config` (a gate-able artifact).
    """
    return "\n".join(
        (
            f"# Profiler-proposed borromeanRings config for a '{profile.archetype}' project.",
            "# Advisory — review, edit, and adopt; borromeanRings then enforces it. ADR-0024.",
            "",
            "[project]",
            f'language = "{language}"',
            f'package = "{package}"',
            f'src_dir = "{src_dir}"',
            f'tests_dir = "{tests_dir}"',
            "",
            "[context]",
            f"value_priorities = {_toml_array(profile.quality_priorities)}",
            "",
            "[checks]",
            f"required = {_toml_array(profile.required_checks)}",
            f"heavy = {_toml_array(profile.heavy_checks)}",
            "",
        )
    )


def render_recommendation(profile: EnforcementProfile) -> str:
    """Human-readable recommendation: archetype, priorities, stacks, active checks."""
    lines = [
        f"project archetype: {profile.archetype}",
        f"quality priorities (highest first): {', '.join(profile.quality_priorities)}",
        f"required checks: {', '.join(profile.required_checks)}",
        f"heavy (CI-tier) checks: {', '.join(profile.heavy_checks) or '(none)'}",
        "stack pathways:",
    ]
    lines.extend(f"  - {opt.name} — {opt.tradeoffs}" for opt in profile.stack_options)
    lines.append(f"notes: {profile.notes}")
    return "\n".join(lines)
