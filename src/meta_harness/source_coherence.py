"""Source-coherence guard: is the gate actually looking at the project's code?

A check that finds no source exits 0, and a bare exit code cannot distinguish the two
situations behind that zero:

* **greenfield** — there is no source anywhere yet, so "nothing to analyze" is the truth
  and the gate must stay green (ideation must never be forced to scaffold code);
* **misconfigured** — ``[project].src_dir`` points somewhere empty while the repository
  demonstrably holds source elsewhere. Every source-reading check then passes vacuously
  and the verdict reports a green that means nothing.

Scope, stated precisely because a guard that over-claims is worse than none: this decides
on **``src_dir`` only**. ``[project].package`` is a separate, legitimately-optional knob
that three checks additionally require; the calling check reports when it is unset rather
than failing, since a scripts-only project has no package. Whatever counts source here
must count it the way the protected checks do, or guard and checks drift apart.

This module is the pure decision core for that distinction: it takes already-gathered
counts and paths and returns a verdict, so it is trivially testable and holds no I/O.
Gathering (git vs filesystem) belongs to the calling check. See
docs/specs/SPEC-self-status.md and ADR-0049.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

#: Label for source files sitting directly at the repository root (no directory part).
ROOT_LABEL = "(repo root)"

#: Directories that never hold a project's own source — caches, vendored deps, build
#: output, virtualenvs, and borromeanRings's own evidence area. Counting these would let
#: a `.venv` full of third-party code masquerade as "the project has source elsewhere".
SKIP_DIRS = frozenset(
    {
        ".git",
        ".meta-harness",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "build",
        "dist",
        "mutants",
        "node_modules",
        "venv",
        ".venv",
    }
)

#: How many offending directories to name in a failure message before truncating.
DEFAULT_DIR_LIMIT = 5


@dataclass(frozen=True)
class Coherence:
    """The guard's verdict: a receipt ``status`` plus the human explanation for it."""

    status: str
    message: str


def top_directories(paths: Sequence[str], limit: int = DEFAULT_DIR_LIMIT) -> list[tuple[str, int]]:
    """Group ``paths`` by leading directory, ranked by count (ties broken by name).

    Ranking is deterministic so the failure message is stable across runs — a message
    that reshuffles on every run reads as noise rather than evidence.
    """
    counts: Counter[str] = Counter()
    for path in paths:
        head, _, tail = path.replace("\\", "/").partition("/")
        counts[head if tail else ROOT_LABEL] += 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return ranked[:limit]


#: Directory names that conventionally hold tests rather than implementation, checked in
#: addition to the project's configured ``tests_dir`` (projects disagree on the spelling).
TEST_DIRS = frozenset({"tests", "test", "testing"})

#: Directories that hold prose or generated material, never the implementation.
NON_SOURCE_DIRS = frozenset({"docs", "doc"})

#: Packaging/tooling shims that exist in almost every repo and are nobody's "real source".
TOOLING_FILENAMES = frozenset({"setup.py", "conftest.py", "noxfile.py", "tasks.py"})


def _is_test_path(parts: Sequence[str], tests_dir: str) -> bool:
    head, name = parts[0], parts[-1]
    return (
        head == tests_dir
        or head in TEST_DIRS
        or name.startswith("test_")
        or name.endswith("_test.py")
    )


def implementation_sources(paths: Sequence[str], *, tests_dir: str = "tests") -> list[str]:
    """The subset of ``paths`` that could be the project's own implementation.

    The guard fails builds, so this boundary decides whether it helps or gets in the way.
    Tests, packaging shims, docs scaffolding and vendored trees are all excluded: none of
    them is implementation the gate could be "blind to", and counting them would fail the
    gate for a project whose only code so far is a failing test — the RED step of the
    test-first workflow borromeanRings exists to support.

    What remains is a genuine second source tree (the misconfiguration this guard is for).
    """
    kept: list[str] = []
    for path in paths:
        parts = tuple(path.replace("\\", "/").split("/"))
        if not parts or _is_test_path(parts, tests_dir):
            continue
        if parts[0] in NON_SOURCE_DIRS or any(part in SKIP_DIRS for part in parts):
            continue
        if parts[-1] in TOOLING_FILENAMES:
            continue
        kept.append(path)
    return kept


def walk_sources(root: Path | str, suffix: str = ".py") -> list[str]:
    """Source files under ``root`` (project-relative), pruning :data:`SKIP_DIRS`.

    The fallback for a project that is not a git repository, where "tracked" has no
    meaning. Kept here rather than inline in the check so it is testable.
    """
    base = Path(root)
    found: list[str] = []
    for path in base.rglob(f"*{suffix}"):
        relative = path.relative_to(base)
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        found.append(str(relative))
    return sorted(found)


def assess(
    *,
    configured_count: int,
    tracked_sources: Sequence[str],
    configured_path: str,
) -> Coherence:
    """Decide whether the declared source path coheres with the project's real source.

    ``configured_count`` is how many source files the declared path resolves to (counted
    the same way the source-reading checks count them), and ``tracked_sources`` is the
    project's version-controlled source. Untracked files are deliberately excluded: a
    scratch file must never fail someone's gate.
    """
    if configured_count > 0:
        return Coherence(
            "pass",
            f"declared source path '{configured_path}' resolves to "
            f"{configured_count} source file(s)",
        )
    if not tracked_sources:
        return Coherence(
            "noop",
            "no source anywhere yet (greenfield) — nothing to check for coherence",
        )
    where = ", ".join(f"{name} ({count})" for name, count in top_directories(tracked_sources))
    return Coherence(
        "fail",
        f"declared source path '{configured_path}' contains no source files, but "
        f"{len(tracked_sources)} tracked source file(s) exist elsewhere: {where}. "
        f"Every source-reading check is inspecting NOTHING and passing vacuously — "
        f"point [project].src_dir/package at the real source.",
    )
