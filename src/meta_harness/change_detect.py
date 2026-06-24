"""Gate-skip change detection — borromeanRings's no-op Stop guard.

The Stop hook re-runs the full gate on every turn, even when the agent only
answered a question and changed no governed file. That is wasted compute and
tokens for zero added assurance.

This module lets the Stop hook skip the gate *only* when the governed input state
is byte-for-byte identical to the state that last passed the gate — i.e. proof
that this exact state is green already exists (the content-hash-cache pattern).
This is NOT "passing on trust": the verdict is a deterministic function of the
gated inputs, so an identical input set has an identical verdict.

Fail-closed: any change, any missing record, any read/compute error ⇒ do NOT
skip (run the gate). Skipping is the rare, provably-safe case; running is the
default.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from meta_harness.spine import Config

# Evidence lives with the governed project (same place as receipts), not borromeanRings.
_STATE_FILE = ".meta-harness/last_green_state"
# Build/cache artifacts never change the gate verdict — exclude them from the hash.
_SKIP_DIRS = frozenset(
    {"__pycache__", ".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".meta-harness"}
)


def _iter_files(project_root: Path, rel: str) -> list[Path]:
    """All files under ``project_root/rel`` (recursively), artifacts excluded."""
    base = project_root / rel
    if not base.exists():
        return []
    if base.is_file():
        return [base]
    out: list[Path] = []
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        parts = path.relative_to(project_root).parts
        if any(part in _SKIP_DIRS for part in parts):
            continue
        if path.suffix == ".pyc":
            continue
        out.append(path)
    return out


def _gated_paths(project_root: Path, config: Config) -> list[Path]:
    """The inputs the gate actually consumes — what a real change must touch.

    The governed source and tests, the per-language check scripts (when borromeanRings
    governs itself), and the policy/build config. A stray file outside this set
    (e.g. an extracted ``.txt``) is not governed code and must not force a run.
    """
    targets = (config.src_dir, config.tests_dir, "checks", "borromeanrings.toml", "pyproject.toml")
    collected: dict[Path, None] = {}
    for target in targets:
        for path in _iter_files(project_root, target):
            collected[path] = None
    return sorted(collected)


def compute_state_hash(project_root: Path, config: Config) -> str:
    """A deterministic SHA-256 over the gated inputs' relative paths and bytes."""
    digest = hashlib.sha256()
    for path in _gated_paths(project_root, config):
        rel = path.relative_to(project_root).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _state_path(project_root: Path) -> Path:
    return project_root / _STATE_FILE


def read_last_green(project_root: Path) -> str | None:
    """The hash recorded at the last green gate, or ``None`` if unavailable."""
    try:
        return (_state_path(project_root).read_text(encoding="utf-8").strip()) or None
    except OSError:
        return None


def record_green(project_root: Path, config: Config) -> None:
    """Record the current gated-input hash as the last proven-green state."""
    path = _state_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(compute_state_hash(project_root, config), encoding="utf-8")


def should_skip_gate(project_root: Path, config: Config) -> bool:
    """True only when the current state matches the last proven-green state.

    Fail-closed: returns ``False`` (run the gate) on any error or missing record.
    """
    last = read_last_green(project_root)
    if last is None:
        return False
    try:
        return compute_state_hash(project_root, config) == last
    except OSError:
        return False
