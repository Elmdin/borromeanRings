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

**What the skip trusts** (#222). The record is an unkeyed hash and the hashing is
in this repository, so anyone who can write the record can compute a value that
makes the hook stand down on a red tree — no secret required. The record therefore
lives OUTSIDE the governed tree, beside the retry counter, under
``$XDG_STATE_HOME/borromeanrings/<project digest>/`` (:mod:`meta_harness.state_home`,
ADR-0079). That defeats an agent confined to the project directory, which is the
realistic case and the one the local loop exists for. It is NOT a bound against
intent: the gate runs the project's own tests as the user, and that code can reach
``$HOME``. A real bound needs isolated execution (#144/#145).

An in-tree ``.meta-harness/last_green_state`` from an older version is never read —
reading it would reopen exactly the hole this closes — and is removed on the next
green so it cannot mislead a reader.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
from collections.abc import Mapping
from pathlib import Path

from meta_harness.spine import Config
from meta_harness.state_home import StateUnavailable, project_state_dir

_STATE_FILE = "last_green_state"
# Written by versions before #222, inside the tree and therefore forgeable. Never read.
_LEGACY_STATE_FILE = ".meta-harness/last_green_state"
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


def _state_path(project_root: Path, env: Mapping[str, str] | None = None) -> Path:
    """Where this project's last-green record lives — outside the project (#222).

    Raises :class:`StateUnavailable` when no absolute state root exists, rather
    than falling back into the tree: a fallback would restore the forgeable
    location on exactly the machines least able to notice.
    """
    resolved = str(Path(project_root).resolve())
    return project_state_dir(os.environ if env is None else env, resolved) / _STATE_FILE


def read_last_green(project_root: Path, env: Mapping[str, str] | None = None) -> str | None:
    """The hash recorded at the last green gate, or ``None`` if unavailable."""
    try:
        return (_state_path(project_root, env).read_text(encoding="utf-8").strip()) or None
    except (OSError, StateUnavailable):
        return None


def record_green(project_root: Path, config: Config, env: Mapping[str, str] | None = None) -> None:
    """Record the current gated-input hash as the last proven-green state.

    Best-effort: if the state home is unavailable the record is simply not made,
    and the next Stop runs the gate. Failing to record costs one gate run; making
    it inside the tree would cost the guarantee.
    """
    try:
        path = _state_path(project_root, env)
    except StateUnavailable:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(compute_state_hash(project_root, config), encoding="utf-8")
    except OSError:
        return
    # A record from before #222 sits in the tree and is forgeable. It is never read,
    # but leaving it there invites someone to "fix" the skip by reading it again.
    with contextlib.suppress(OSError):
        (Path(project_root) / _LEGACY_STATE_FILE).unlink(missing_ok=True)


def should_skip_gate(
    project_root: Path, config: Config, env: Mapping[str, str] | None = None
) -> bool:
    """True only when the current state matches the last proven-green state.

    Fail-closed: returns ``False`` (run the gate) on any error or missing record.
    """
    last = read_last_green(project_root, env)
    if last is None:
        return False
    try:
        return compute_state_hash(project_root, config) == last
    except OSError:
        return False
