"""The policy spine: the single declarative source of this repo's invariants.

Loads ``borromeo.toml`` and exposes the required-check set and declared context.
The gate (``verify.sh``) consumes the required set and enforces config-compliance:
every declared check must produce a pass receipt. The spine governs *outcomes*
(what must hold), deliberately not *how* the wrapped agent plans or decides.
See docs/SPEC-spine.md.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomllib


@dataclass(frozen=True)
class Config:
    """The declared invariants borromeo enforces on every run."""

    required_checks: tuple[str, ...]
    context: Mapping[str, Any]
    prompt_rewriting_enabled: bool = False
    hygiene_requires: tuple[str, ...] = ()
    # [project] — what borromeo targets in the GOVERNED project (portability).
    package: str = ""  # importable package name (optional; "" → skip import check)
    src_dir: str = "src"
    tests_dir: str = "tests"
    language: str = "python"  # selects checks/<language>/ — the per-language check set


def load_config(path: str | Path = "borromeo.toml") -> Config:
    """Load and validate the policy spine from ``borromeo.toml``.

    Fail-closed: an empty or absent ``[checks].required`` is a misconfiguration
    and raises — borromeo never treats "nothing declared" as "nothing to enforce".

    Args:
        path: path to the TOML config (default ``borromeo.toml``).

    Returns:
        The validated :class:`Config`.

    Raises:
        ValueError: if no required checks are declared.
    """
    raw: dict[str, Any] = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    required = list(raw.get("checks", {}).get("required", []))
    if not required:
        raise ValueError(
            "borromeo.toml must declare a non-empty [checks].required — "
            "no declared checks is a misconfiguration (fail-closed)."
        )
    context: Mapping[str, Any] = raw.get("context", {})
    prompt_rewriting_enabled = bool(raw.get("prompt_rewriting", {}).get("enabled", False))
    hygiene_requires = tuple(raw.get("hygiene", {}).get("requires", []))
    project = raw.get("project", {})
    return Config(
        required_checks=tuple(required),
        context=context,
        prompt_rewriting_enabled=prompt_rewriting_enabled,
        hygiene_requires=hygiene_requires,
        package=str(project.get("package", "")),
        src_dir=str(project.get("src_dir", "src")),
        tests_dir=str(project.get("tests_dir", "tests")),
        language=str(project.get("language", "python")),
    )
