"""The policy spine: the single declarative source of this repo's invariants.

Loads ``borromeanrings.toml`` and exposes the required-check set and declared context.
The gate (``verify.sh``) consumes the required set and enforces config-compliance:
every declared check must produce a pass receipt. The spine governs *outcomes*
(what must hold), deliberately not *how* the wrapped agent plans or decides.
See docs/specs/SPEC-spine.md.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomllib


@dataclass(frozen=True)
class Config:
    """The declared invariants borromeanRings enforces on every run."""

    required_checks: tuple[str, ...]
    context: Mapping[str, Any]
    # [checks].heavy — CI-tier checks required only under `verify.sh --heavy` (ADR-0033).
    heavy_checks: tuple[str, ...] = ()
    prompt_rewriting_enabled: bool = False
    hygiene_requires: tuple[str, ...] = ()
    # [project] — what borromeanRings targets in the GOVERNED project (portability).
    package: str = ""  # importable package name (optional; "" → skip import check)
    src_dir: str = "src"
    tests_dir: str = "tests"
    language: str = "python"  # selects checks/<language>/ — the per-language check set
    # [git] — declared commit identity; empty ⇒ identity enforcement is off.
    git_name: str = ""
    git_email: str = ""
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
    # [api] — public-API breaking-change policy (ADR-0040). allow_breaking=true only
    # for a deliberate major-version release.
    api_allow_breaking: bool = False


def load_config(path: str | Path = "borromeanrings.toml") -> Config:
    """Load and validate the policy spine from ``borromeanrings.toml``.

    Fail-closed: an empty or absent ``[checks].required`` is a misconfiguration
    and raises — borromeanRings never treats "nothing declared" as "nothing to enforce".

    Args:
        path: path to the TOML config (default ``borromeanrings.toml``).

    Returns:
        The validated :class:`Config`.

    Raises:
        ValueError: if no required checks are declared.
    """
    raw: dict[str, Any] = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    required = list(raw.get("checks", {}).get("required", []))
    if not required:
        raise ValueError(
            "borromeanrings.toml must declare a non-empty [checks].required — "
            "no declared checks is a misconfiguration (fail-closed)."
        )
    context: Mapping[str, Any] = raw.get("context", {})
    prompt_rewriting_enabled = bool(raw.get("prompt_rewriting", {}).get("enabled", False))
    hygiene_requires = tuple(raw.get("hygiene", {}).get("requires", []))
    project = raw.get("project", {})
    git = raw.get("git", {})
    layout = raw.get("layout", {})
    collaboration = raw.get("collaboration", {})
    architecture = raw.get("architecture", {})
    changelog = raw.get("changelog", {})
    critic = raw.get("critic", {})
    audit = raw.get("audit", {})
    licenses = raw.get("licenses", {})
    return Config(
        required_checks=tuple(required),
        heavy_checks=tuple(raw.get("checks", {}).get("heavy", [])),
        context=context,
        prompt_rewriting_enabled=prompt_rewriting_enabled,
        hygiene_requires=hygiene_requires,
        package=str(project.get("package", "")),
        src_dir=str(project.get("src_dir", "src")),
        tests_dir=str(project.get("tests_dir", "tests")),
        language=str(project.get("language", "python")),
        git_name=str(git.get("name", "")),
        git_email=str(git.get("email", "")),
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
        enhancements_interests=tuple(raw.get("enhancements", {}).get("interests", [])),
        api_allow_breaking=bool(raw.get("api", {}).get("allow_breaking", False)),
    )
