"""Project-hygiene gate: the engineering *surround* a project must have.

borromeo gates not just code quality but the software-engineering surround — docs,
CI, containerization, license, dev environment, etc. The required artifacts are
*declared* in ``borromeo.toml`` (``[hygiene].requires``); the gate fails closed if
any are missing. Presence-only for v1 (existence is enough); deeper structural
checks can follow. See ADR-0012 (process) and docs/ROADMAP.md.
"""

from collections.abc import Sequence
from pathlib import Path


def missing_paths(root: str | Path, requires: Sequence[str]) -> list[str]:
    """Return the declared engineering-surround paths missing under ``root``.

    A required path may be a file or a directory; existence is sufficient.
    """
    base = Path(root)
    return [req for req in requires if not (base / req).exists()]
