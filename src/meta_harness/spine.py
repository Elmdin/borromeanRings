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
    return Config(required_checks=tuple(required), context=context)
