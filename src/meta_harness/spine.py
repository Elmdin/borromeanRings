"""The policy spine: the single declarative source of this repo's invariants.

Loads ``borromeanrings.toml`` and exposes the required-check set and declared context.
The gate (``verify.sh``) consumes the required set and enforces config-compliance:
every declared check must produce a pass receipt. The spine governs *outcomes*
(what must hold), deliberately not *how* the wrapped agent plans or decides.
See docs/specs/SPEC-spine.md.
"""

import keyword
import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomllib

#: What ``[git].require`` may ask of a commit's author. ``email`` — the address, which is
#: the durable identity and the one a project actually specifies; ``email+name`` — the
#: display name too, for a project that controls how its commits are made. Closed
#: vocabulary: an unknown value is refused, never silently relaxed (#229, ADR-0087).
IDENTITY_REQUIREMENTS: tuple[str, ...] = ("email", "email+name")

#: Languages with a shipped `checks/<language>/` lane (ADR-0015, ADR-0068), plus ``none``
#: for a project governed by the shared (language-agnostic) checks only. Closed vocabulary:
#: an unknown value fails closed in :func:`load_config` rather than falling through to
#: Python's checks or to an empty set that would pass vacuously.
SUPPORTED_LANGUAGES: tuple[str, ...] = ("python", "typescript", "go", "none")
#: The closed vocabulary of application archetypes a project may declare in
#: ``[project].archetypes``. Lives here (not in meta_harness.archetypes) because the spine
#: is an architecture leaf and must import no domain module; the catalog is keyed by
#: exactly these names and a unit test binds the two. See SPEC-archetypes.md, ADR-0062.
ARCHETYPES: tuple[str, ...] = (
    "library",
    "cli",
    "web-api",
    "web-app",
    "ml",
    "embedded",
    "data-pipeline",
)
#: Every key `[verification]` understands. An unknown key there is a hard error
#: (see :func:`load_config`): a typo'd verification claim must never read as
#: "nothing declared", which would silently switch the rule off. ADR-0074.
VERIFICATION_KEYS: frozenset[str] = frozenset({"properties"})
# The policy-spine file name, and the pre-rename spelling still accepted (issue #62).
# Projects governed before the borromeo -> borromeanRings rename may still carry the
# legacy file; it keeps loading (with a FutureWarning on stderr) so they never silently
# fall out of governance. Migration: `git mv borromeo.toml borromeanrings.toml`.
CONFIG_NAME = "borromeanrings.toml"
LEGACY_CONFIG_NAME = "borromeo.toml"


@dataclass(frozen=True)
class Config:
    """The declared invariants borromeanRings enforces on every run."""

    required_checks: tuple[str, ...]
    context: Mapping[str, Any]
    # [checks].heavy — CI-tier checks required only under `verify.sh --heavy` (ADR-0033).
    heavy_checks: tuple[str, ...] = ()
    #: Checks too expensive for a per-PR round; graded only in a `--scheduled` run
    #: (ADR-0090). Declared like the others, never hardcoded.
    scheduled_checks: tuple[str, ...] = ()
    prompt_rewriting_enabled: bool = False
    # [self_report].enabled — record the reply's VERIFICATION STATUS block at Stop
    # (ADR-0066). Defaults to prompt_rewriting_enabled: the reply-shape contracts
    # travel together unless a project says otherwise.
    self_report_enabled: bool = False
    hygiene_requires: tuple[str, ...] = ()
    # [project] — what borromeanRings targets in the GOVERNED project (portability).
    package: str = ""  # importable package name (optional; "" → skip import check)
    src_dir: str = "src"
    tests_dir: str = "tests"
    # [test].fast_paths — the subset of the test suite the FAST (interactive) lane
    # runs. Empty (the default) ⇒ no fast lane: every lane runs the whole suite,
    # exactly as before. See meta_harness.lane and ADR-0081.
    test_fast_paths: tuple[str, ...] = ()
    language: str = "python"  # selects checks/<language>/ — the per-language check set
    # [project].archetypes — what KIND of application this is (ADR-0062). Selects the
    # required-feature set 21_archetype gates and which checks must be non-noop. Empty ⇒
    # the archetype dimension is off. Validated against ARCHETYPES (fail-closed).
    archetypes: tuple[str, ...] = ()
    # [git] — declared commit identity; empty ⇒ identity enforcement is off.
    git_name: str = ""
    git_email: str = ""
    git_require: str = "email"  # what a commit's author must match (IDENTITY_REQUIREMENTS)
    # [layout] — file-organization conventions; each rule off when empty/zero.
    specs_dir: str = ""
    root_doc_allowlist: tuple[str, ...] = ()
    test_grouping_threshold: int = 0
    test_groups: tuple[str, ...] = ()
    # [collaboration] — Tier A collaboration gates (SPEC-collaboration.md,
    # ADR-0021); each rule off when empty/zero.
    collaboration_protected_branches: tuple[str, ...] = ()
    collaboration_branch_patterns: tuple[str, ...] = ()
    collaboration_commit_types: tuple[str, ...] = ()
    collaboration_subject_max_length: int = 0
    # [architecture] — import-direction fitness over the internal module graph
    # (ADR-0027); each rule off when empty/false.
    architecture_leaves: tuple[str, ...] = ()
    architecture_private: tuple[str, ...] = ()
    architecture_forbidden: tuple[tuple[str, str], ...] = ()
    architecture_forbid_cycles: bool = False
    # [api_contracts] — the project's own API-usage rules (ADR-0054); raw rule tables are
    # validated by meta_harness.api_contracts.parse_rules at check time (fail closed).
    api_contracts_rules: tuple[dict[str, object], ...] = ()
    api_contracts_packs: tuple[str, ...] = ()
    # [changelog] — Keep a Changelog discipline (ADR-0028); off when disabled.
    changelog_enabled: bool = False
    changelog_path: str = "CHANGELOG.md"
    changelog_require_entry_on_src_change: bool = False
    # [critic] — model-backed rubric judgment (ADR-0023/0030). Empty judge_command
    # ⇒ the critic checks are off (no live judge wired).
    critic_judge_command: str = ""
    critic_rubrics: tuple[str, ...] = ()  # enabled Wave-2 rubrics (ADR-0036)
    # [audit] — dependency CVE audit (ADR-0034); ignore base tooling / accepted CVEs.
    audit_ignore_packages: tuple[str, ...] = ()
    audit_ignore_vulns: tuple[str, ...] = ()
    # [licenses] — dependency license compliance (ADR-0035); deny patterns off when empty.
    license_deny: tuple[str, ...] = ()
    license_allow_packages: tuple[str, ...] = ()
    # [enhancements] — agent-enhancement recommender interests (ADR-0037); advisory.
    enhancements_interests: tuple[str, ...] = ()
    # [secrets] — git-history secret scan (ADR-0042); fingerprints of already-rotated
    # / known-benign historical findings to acknowledge (74_secret_history).
    secrets_history_allow: tuple[str, ...] = ()
    # [adr] — ADR-discipline gate (ADR-0043); a feature branch touching src must add
    # an ADR. adr_dir defaults to docs/adr; require_prefixes to the feature prefix.
    adr_dir: str = "docs/adr"
    adr_require_prefixes: tuple[str, ...] = ("feat/",)

    # [prior_art] — a feature branch that adds public surface must record a survey of
    # what already existed under `dir` (ADR-0051). The 13_adr pattern applied to reuse.
    prior_art_dir: str = "docs/surveys"
    prior_art_require_prefixes: tuple[str, ...] = ("feat/",)
    # [api] — public-API breaking-change policy (ADR-0040). allow_breaking=true only
    # for a deliberate major-version release.
    api_allow_breaking: bool = False
    # [container] — Dockerfile hygiene (ADR-0044); the SRE/operational slice. Which
    # rules apply is per-project (a run-and-exit gate-runner omits `healthcheck`).
    container_dockerfile: str = "Dockerfile"
    container_require: tuple[str, ...] = ("non_root", "pinned_base", "healthcheck")
    # [citations] — citation-resolution gate (ADR-0073); off unless enabled. paths are
    # the repo-relative prefixes whose changed *.md files are scanned.
    citations_enabled: bool = False
    citations_paths: tuple[str, ...] = ("docs/", "README.md", "CHANGELOG.md", "skills/")
    # [a11y] — static accessibility invariants for HTML (ADR-0045); the Product/UX
    # slice. require selects rules; exclude drops build-output/vendored dirs.
    a11y_require: tuple[str, ...] = ("html_lang", "img_alt", "page_title")
    a11y_exclude: tuple[str, ...] = ("node_modules", "dist", "build", "vendor")
    # [generator] — the headless generator's command (ADR-0071/ADR-0078). Empty ⇒ there
    # is no headless generator and `generate.sh` refuses to run; never a silent default.
    generator_command: str = ""
    # [charter] — session-charter gate (ADR-0063): a committed CHARTER.toml naming goal,
    # stakes (low|high), done_when, stop_when, may_not, owner. Opt-in; off by default.
    charter_enabled: bool = False
    charter_path: str = "CHARTER.toml"
    charter_high_stakes_fields: tuple[str, ...] = ("rollback", "reviewer", "blast_radius")
    # [quotes] — quote fidelity (ADR-0065): marked quotations in the Markdown under
    # `paths` must be verbatim against their saved source. Off unless enabled.
    quotes_enabled: bool = False
    quotes_paths: tuple[str, ...] = ("docs",)
    # [supply_chain] — lockfile integrity + pinned dependencies (ADR-0061). No lockfile
    # declared ⇒ 76_lockfile is a noop; pin_optional extends 78_pins to optional groups.
    supply_chain_lockfile: str = ""
    supply_chain_manifests: tuple[str, ...] = ("pyproject.toml", "package.json")
    supply_chain_pin_optional: bool = False
    # [verification] — the mathematical-verification ladder (ADR-0074). Tier 1 only:
    # the project-relative directory holding its property suite. NO default — writing
    # the key is an affirmative claim, so "" means the rule is off, and a declared
    # directory with no property tests is a failure, not a no-op.
    verification_properties: str = ""
    # [provenance] — re-authored text must not reproduce a declared source (ADR-0070).
    # declared=False ⇒ rule off. sources are read-only paths (machine-local ones come
    # from BORROMEANRINGS_PROVENANCE_SOURCES, never the config); allow is the human's
    # classification of generic overlaps, kept reviewable in the config.
    provenance_declared: bool = False
    provenance_sources: tuple[str, ...] = ()
    provenance_paths: tuple[str, ...] = ("docs", "skills", ".claude/skills")
    provenance_allow: tuple[str, ...] = ()
    # [predicates] — hedge-word lint + graph integrity over acceptance predicates
    # (ADR-0064). Off unless enabled; hedges EXTEND the built-in list.
    predicates_enabled: bool = False
    predicates_paths: tuple[str, ...] = ("docs/specs", "docs/adr", ".github/ISSUE_TEMPLATE")
    predicates_hedges: tuple[str, ...] = ()
    predicates_require_reference: bool = True

    # [shell] — shellcheck lint over the project's own shell (ADR-0050). borromeanRings
    # is roughly half bash, and that bash IS the trust root: the gate, the hooks, every
    # check. `source_paths` are shellcheck -P entries so `source`d libraries resolve
    # statically (SCRIPTDIR = the checked script's own directory) rather than being
    # blanket-suppressed; `exclude` is a per-code escape hatch that should stay empty.
    shell_source_paths: tuple[str, ...] = ("SCRIPTDIR", "SCRIPTDIR/..")
    shell_exclude: tuple[str, ...] = ()


class ProjectClaimError(ValueError):
    """A config that is invalid because of what it claims the project IS.

    Every other config error is a fact each check reports on in its own receipt; these
    two refuse the gate before any check runs, because everything derived from the claim
    would be wrong (verify.sh, ADR-0068). Subclasses of ValueError, so every caller that
    treats a ValueError as "invalid config" is unchanged.
    """

    kind = "claim"


class UnknownArchetype(ProjectClaimError):
    """``[project].archetypes`` names an archetype that does not exist (#79)."""

    kind = "archetype"


class UnknownLanguage(ProjectClaimError):
    """``[project].language`` names a language with no check lane (ADR-0068)."""

    kind = "language"


class UnusablePackageName(ProjectClaimError):
    """``[project].package`` is not a Python identifier (review of #261).

    The name is interpolated into commands the gate runs — ``python3 -c "import
    <package>"`` among them — so a name carrying a quote or a semicolon is not a
    misconfiguration to report, it is a way to make the gate run something else. Every
    legitimate value is an identifier, so anything else is refused before any check runs.
    """

    kind = "package"


class UnknownIdentityRequirement(ProjectClaimError):
    """``[git].require`` names something other than a shipped rule (#229, ADR-0087)."""

    kind = "identity-requirement"


def _archetypes(project: Mapping[str, Any]) -> tuple[str, ...]:
    """``[project].archetypes`` validated against :data:`ARCHETYPES`; unknown ⇒ raise."""
    declared = tuple(str(name) for name in project.get("archetypes", []))
    unknown = [name for name in declared if name not in ARCHETYPES]
    if unknown:
        raise UnknownArchetype(
            f"borromeanrings.toml [project].archetypes has unknown archetype(s) "
            f"{', '.join(unknown)} — known: {', '.join(ARCHETYPES)} (fail-closed)."
        )
    return declared


def resolve_config_path(path: str | Path) -> Path:
    """Resolve the spine path, falling back to a sibling legacy ``borromeo.toml``.

    The fallback applies ONLY when ``path`` names the canonical file and it is absent:
    the canonical file always wins when present, and any other file name is returned
    untouched (a missing file then surfaces as ``FileNotFoundError`` in the caller).

    The notice is a ``FutureWarning``, not a ``DeprecationWarning``: Python's default
    filters hide the latter outside ``__main__``, so it never reached stderr through the
    real call paths (``status.sh``, the hooks — PR #165 review). A ``FutureWarning`` is
    the end-user-facing category, shown by default, once per process per legacy file.

    Args:
        path: the requested TOML config path.

    Returns:
        ``path`` itself, or the sibling legacy file when that is what exists.
    """
    requested = Path(path)
    if requested.exists() or requested.name != CONFIG_NAME:
        return requested
    legacy = requested.with_name(LEGACY_CONFIG_NAME)
    if not legacy.exists():
        return requested
    warnings.warn(
        f"{legacy} uses the deprecated config name {LEGACY_CONFIG_NAME}; rename it to "
        f"{CONFIG_NAME} (git mv {LEGACY_CONFIG_NAME} {CONFIG_NAME}). The legacy name "
        "still loads for now — see docs/RENAME.md.",
        FutureWarning,
        stacklevel=2,
    )
    return legacy


def _validated_package(project: Mapping[str, Any]) -> str:
    """``[project].package``, which must be empty or a Python identifier (fail-closed).

    Empty means "no import check" and is legitimate. Anything else must be a name Python
    could import and a shell could not reinterpret: the value reaches
    ``python3 -c "import <package>"`` inside a command string (``00_build``), and
    ``init.sh``/``adopt.sh`` now write it from a directory name they read off disk, so a
    directory called ``pkg"; whoami; #`` would otherwise become a command (review of
    #261). Keywords are refused too — ``import class`` is a syntax error, not a check.
    """
    package = str(project.get("package", ""))
    if not package:
        return ""
    # Dotted paths are legitimate — `package = "fixturepkg.core"` is a real configuration
    # this project's own tests use — so each SEGMENT must be an identifier, not the whole
    # string. (My first version refused the dotted form: a validator tighter than the
    # thing it guards, which is the mistake the review of #259 caught a week ago.)
    segments = package.split(".")
    if not all(part.isidentifier() and not keyword.iskeyword(part) for part in segments):
        raise UnusablePackageName(
            f"borromeanrings.toml [project].package = '{package}' is not an importable "
            "name; it must be a Python identifier (fail-closed)."
        )
    return package


def _validated_identity_requirement(git: Mapping[str, Any]) -> str:
    """``[git].require``, which must name a shipped rule (fail-closed).

    A typo must not fall through to "check nothing": what identity means for this
    project is exactly what this value says.
    """
    require = str(git.get("require", "email"))
    if require not in IDENTITY_REQUIREMENTS:
        raise UnknownIdentityRequirement(
            f"borromeanrings.toml [git].require = '{require}' is not a rule; "
            f"supported: {', '.join(IDENTITY_REQUIREMENTS)} (fail-closed)."
        )
    return require


def _validated_language(project: Mapping[str, Any]) -> str:
    """``[project].language``, which must name a shipped check lane (fail-closed).

    A typo ("pyhton") or a language with no ``checks/<lang>/`` must not fall through to
    another lane's checks or to an empty set that passes vacuously (ADR-0068).
    """
    language = str(project.get("language", "python"))
    if language not in SUPPORTED_LANGUAGES:
        raise UnknownLanguage(
            f"borromeanrings.toml [project].language = '{language}' has no check lane; "
            f"supported: {', '.join(SUPPORTED_LANGUAGES)} (fail-closed)."
        )
    return language


def _validated_required(raw: Mapping[str, Any]) -> list[str]:
    """The declared required checks, refusing an empty set.

    Fail-closed: borromeanRings never reads "nothing declared" as "nothing to enforce".
    """
    required = list(_table(raw, "checks").get("required", []))
    if not required:
        raise ValueError(
            "borromeanrings.toml must declare a non-empty [checks].required — "
            "no declared checks is a misconfiguration (fail-closed)."
        )
    return required


def _reject_unknown_verification(raw: Mapping[str, Any]) -> None:
    """Refuse an unrecognised ``[verification]`` key.

    A misspelled verification claim would otherwise read as "nothing declared",
    which is the silent-downgrade this project exists to prevent.
    """
    unknown = sorted(set(_table(raw, "verification")) - VERIFICATION_KEYS)
    if unknown:
        raise ValueError(
            f"borromeanrings.toml [verification] has unknown key(s): {', '.join(unknown)}. "
            f"Known: {', '.join(sorted(VERIFICATION_KEYS))}. A misspelled verification "
            "claim would silently read as 'nothing declared' — fail-closed instead."
        )


def _table(raw: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    """``[name]`` as a table (``{}`` when absent); anything else is a config error.

    Every section is read with ``.get``. A scalar in a section's place (``charter =
    "high"`` for ``[charter] stakes = "high"``) used to surface as an AttributeError
    from deep inside :func:`load_config`: a traceback rather than the ``ValueError``
    every caller treats as an invalid config. Fail closed, and name the section.
    """
    value = raw.get(name, {})
    if not isinstance(value, Mapping):
        raise ValueError(
            f"[{name}] must be a table, got {type(value).__name__} — "
            f"write it as a [{name}] section, not `{name} = ...`"
        )
    return value


def load_config(path: str | Path = CONFIG_NAME) -> Config:
    """Load and validate the policy spine from ``borromeanrings.toml``.

    Fail-closed: an empty or absent ``[checks].required`` is a misconfiguration
    and raises — borromeanRings never treats "nothing declared" as "nothing to enforce".

    Args:
        path: path to the TOML config (default ``borromeanrings.toml``).

    Returns:
        The validated :class:`Config`.

    Raises:
        ValueError: if no required checks are declared, or ``[project].language`` is
            not one of :data:`SUPPORTED_LANGUAGES`.
        ValueError: if no required checks are declared, or an archetype is unknown.
        ValueError: if no required checks are declared, or if ``[verification]``
            carries a key borromeanRings does not understand.
        ValueError: if no required checks are declared.
        FileNotFoundError: if neither the canonical nor the legacy file exists.
    """
    raw: dict[str, Any] = tomllib.loads(resolve_config_path(path).read_text(encoding="utf-8"))
    required = _validated_required(raw)
    _reject_unknown_verification(raw)
    verification: Mapping[str, Any] = _table(raw, "verification")
    context: Mapping[str, Any] = _table(raw, "context")
    prompt_rewriting_enabled = bool(_table(raw, "prompt_rewriting").get("enabled", False))
    self_report_enabled = bool(_table(raw, "self_report").get("enabled", prompt_rewriting_enabled))
    hygiene_requires = tuple(_table(raw, "hygiene").get("requires", []))
    project = _table(raw, "project")
    language = _validated_language(project)
    git = _table(raw, "git")
    layout = _table(raw, "layout")
    collaboration = _table(raw, "collaboration")
    architecture = _table(raw, "architecture")
    api_contracts = _table(raw, "api_contracts")
    changelog = _table(raw, "changelog")
    critic = _table(raw, "critic")
    audit = _table(raw, "audit")
    licenses = _table(raw, "licenses")
    charter = _table(raw, "charter")
    supply_chain = _table(raw, "supply_chain")
    provenance = _table(raw, "provenance")
    predicates = _table(raw, "predicates")
    test = _table(raw, "test")
    return Config(
        required_checks=tuple(required),
        heavy_checks=tuple(_table(raw, "checks").get("heavy", [])),
        scheduled_checks=tuple(_table(raw, "checks").get("scheduled", [])),
        context=context,
        prompt_rewriting_enabled=prompt_rewriting_enabled,
        self_report_enabled=self_report_enabled,
        hygiene_requires=hygiene_requires,
        package=_validated_package(project),
        src_dir=str(project.get("src_dir", "src")),
        tests_dir=str(project.get("tests_dir", "tests")),
        language=language,
        test_fast_paths=tuple(str(p) for p in test.get("fast_paths", [])),
        archetypes=_archetypes(project),
        git_name=str(git.get("name", "")),
        git_email=str(git.get("email", "")),
        git_require=_validated_identity_requirement(git),
        specs_dir=str(layout.get("specs_dir", "")),
        root_doc_allowlist=tuple(layout.get("root_doc_allowlist", [])),
        test_grouping_threshold=int(layout.get("test_grouping_threshold", 0)),
        test_groups=tuple(layout.get("test_groups", [])),
        collaboration_protected_branches=tuple(collaboration.get("protected_branches", [])),
        collaboration_branch_patterns=tuple(collaboration.get("branch_patterns", [])),
        collaboration_commit_types=tuple(collaboration.get("commit_types", [])),
        collaboration_subject_max_length=int(collaboration.get("subject_max_length", 0)),
        architecture_leaves=tuple(architecture.get("leaves", [])),
        architecture_private=tuple(architecture.get("private", [])),
        architecture_forbidden=tuple(
            (str(pair[0]), str(pair[1])) for pair in architecture.get("forbidden", [])
        ),
        architecture_forbid_cycles=bool(architecture.get("forbid_cycles", False)),
        api_contracts_rules=tuple(dict(rule) for rule in api_contracts.get("rules", [])),
        api_contracts_packs=tuple(str(pack) for pack in api_contracts.get("packs", [])),
        changelog_enabled=bool(changelog.get("enabled", False)),
        changelog_path=str(changelog.get("path", "CHANGELOG.md")),
        changelog_require_entry_on_src_change=bool(
            changelog.get("require_entry_on_src_change", False)
        ),
        critic_judge_command=str(critic.get("judge_command", "")),
        critic_rubrics=tuple(critic.get("rubrics", [])),
        audit_ignore_packages=tuple(audit.get("ignore_packages", [])),
        audit_ignore_vulns=tuple(audit.get("ignore_vulns", [])),
        license_deny=tuple(licenses.get("deny", [])),
        license_allow_packages=tuple(licenses.get("allow_packages", [])),
        enhancements_interests=tuple(_table(raw, "enhancements").get("interests", [])),
        api_allow_breaking=bool(_table(raw, "api").get("allow_breaking", False)),
        secrets_history_allow=tuple(_table(raw, "secrets").get("history_allow", [])),
        adr_dir=str(_table(raw, "adr").get("dir", "docs/adr")),
        adr_require_prefixes=tuple(_table(raw, "adr").get("require_prefixes", ["feat/"])),
        prior_art_dir=str(_table(raw, "prior_art").get("dir", "docs/surveys")),
        prior_art_require_prefixes=tuple(
            _table(raw, "prior_art").get("require_prefixes", ["feat/"])
        ),
        container_dockerfile=str(_table(raw, "container").get("dockerfile", "Dockerfile")),
        container_require=tuple(
            _table(raw, "container").get("require", ["non_root", "pinned_base", "healthcheck"])
        ),
        citations_enabled=bool(_table(raw, "citations").get("enabled", False)),
        citations_paths=tuple(
            _table(raw, "citations").get("paths", ["docs/", "README.md", "CHANGELOG.md", "skills/"])
        ),
        a11y_require=tuple(
            _table(raw, "a11y").get("require", ["html_lang", "img_alt", "page_title"])
        ),
        a11y_exclude=tuple(
            _table(raw, "a11y").get("exclude", ["node_modules", "dist", "build", "vendor"])
        ),
        generator_command=str(raw.get("generator", {}).get("command", "")),
        charter_enabled=bool(charter.get("enabled", False)),
        charter_path=str(charter.get("path", "CHARTER.toml")),
        charter_high_stakes_fields=tuple(
            charter.get("high_stakes_fields", ["rollback", "reviewer", "blast_radius"])
        ),
        quotes_enabled=bool(_table(raw, "quotes").get("enabled", False)),
        quotes_paths=tuple(_table(raw, "quotes").get("paths", ["docs"])),
        supply_chain_lockfile=str(supply_chain.get("lockfile", "")),
        supply_chain_manifests=tuple(
            supply_chain.get("manifests", ["pyproject.toml", "package.json"])
        ),
        supply_chain_pin_optional=bool(supply_chain.get("pin_optional", False)),
        verification_properties=str(verification.get("properties", "")).strip(),
        provenance_declared="provenance" in raw,
        provenance_sources=tuple(str(p) for p in provenance.get("sources", [])),
        provenance_paths=tuple(
            str(p) for p in provenance.get("paths", ["docs", "skills", ".claude/skills"])
        ),
        provenance_allow=tuple(str(p) for p in provenance.get("allow", [])),
        predicates_enabled=bool(predicates.get("enabled", False)),
        predicates_paths=tuple(
            str(p)
            for p in predicates.get("paths", ["docs/specs", "docs/adr", ".github/ISSUE_TEMPLATE"])
        ),
        predicates_hedges=tuple(str(h) for h in predicates.get("hedges", [])),
        predicates_require_reference=bool(predicates.get("require_reference", True)),
        shell_source_paths=tuple(
            _table(raw, "shell").get("source_paths", ["SCRIPTDIR", "SCRIPTDIR/.."])
        ),
        shell_exclude=tuple(_table(raw, "shell").get("exclude", [])),
    )
