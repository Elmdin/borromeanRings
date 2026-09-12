"""Unit tests for the source-coherence guard (meta_harness.source_coherence).

The guard separates the two situations that a bare exit code cannot tell apart:
a genuinely **greenfield** project (nothing to inspect yet — must stay green) and a
**misconfigured** one whose declared source path resolves to nothing while the repo
demonstrably holds source elsewhere (the gate is blind — must fail). See
docs/specs/SPEC-self-status.md.
"""

from __future__ import annotations

from pathlib import Path

from meta_harness.source_coherence import (
    Coherence,
    assess,
    implementation_sources,
    top_directories,
    walk_sources,
)


def test_configured_path_with_source_passes() -> None:
    result = assess(
        configured_count=38,
        tracked_sources=["src/pkg/a.py", "tests/test_a.py"],
        configured_path="src",
    )
    assert result.status == "pass"
    assert "38" in result.message


def test_a_single_source_file_is_already_coherent() -> None:
    """Boundary: one file at the declared path is real code, not 'nothing'.

    Guards the `> 0` test against drifting to `> 1`, which would declare a one-module
    project blind and fail it.
    """
    result = assess(configured_count=1, tracked_sources=["src/only.py"], configured_path="src")
    assert result.status == "pass"


def test_genuinely_greenfield_is_noop_not_failure() -> None:
    """No source anywhere: planning/ideation must never be forced to scaffold code."""
    result = assess(configured_count=0, tracked_sources=[], configured_path="src")
    assert result.status == "noop"
    assert "greenfield" in result.message


def test_configured_path_empty_while_source_exists_elsewhere_fails() -> None:
    """The 3ML case: src_dir='src' is empty, but 30 tracked .py live in tools/."""
    tracked = [f"tools/mod_{i}.py" for i in range(30)] + ["tests/test_x.py"]
    result = assess(configured_count=0, tracked_sources=tracked, configured_path="src")
    assert result.status == "fail"
    # The message must name where the code actually is, so the fix is one config line.
    assert "tools" in result.message
    assert "src" in result.message


def test_failure_message_counts_the_offending_directories() -> None:
    tracked = ["tools/a.py", "tools/b.py", "scripts/c.py"]
    result = assess(configured_count=0, tracked_sources=tracked, configured_path="src")
    assert "tools" in result.message and "scripts" in result.message
    assert "2" in result.message  # tools holds 2 files


def test_untracked_only_source_does_not_fail() -> None:
    """Untracked scratch files must never fail a gate — only tracked source counts."""
    result = assess(configured_count=0, tracked_sources=[], configured_path="src")
    assert result.status != "fail"


def test_result_is_immutable() -> None:
    result = assess(configured_count=1, tracked_sources=[], configured_path="src")
    assert isinstance(result, Coherence)
    try:
        result.status = "fail"  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("Coherence must be frozen")


def test_top_directories_groups_and_ranks_by_count() -> None:
    paths = ["tools/a.py", "tools/b.py", "tools/c.py", "scripts/d.py", "lib/e.py"]
    assert top_directories(paths)[0] == ("tools", 3)


def test_top_directories_labels_repo_root_files() -> None:
    assert top_directories(["setup.py"]) == [("(repo root)", 1)]


def test_top_directories_is_bounded() -> None:
    paths = [f"d{i}/x.py" for i in range(20)]
    assert len(top_directories(paths, limit=3)) == 3


# --- walk_sources: the non-git fallback -----------------------------------------------


def test_walk_sources_finds_nested_source(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("", encoding="utf-8")
    (tmp_path / "top.py").write_text("", encoding="utf-8")
    assert walk_sources(tmp_path) == ["pkg/a.py", "top.py"]


def test_walk_sources_prunes_vendored_and_cache_dirs(tmp_path: Path) -> None:
    """A .venv full of third-party code must not read as 'the project has source'."""
    for skipped in (".venv", "node_modules", "__pycache__", ".git", "mutants"):
        (tmp_path / skipped).mkdir()
        (tmp_path / skipped / "dep.py").write_text("", encoding="utf-8")
    (tmp_path / "real.py").write_text("", encoding="utf-8")
    assert walk_sources(tmp_path) == ["real.py"]


def test_walk_sources_on_empty_tree_is_empty(tmp_path: Path) -> None:
    assert walk_sources(tmp_path) == []


def test_walk_sources_skips_past_pruned_dirs_without_abandoning_the_walk(
    tmp_path: Path,
) -> None:
    """Pruning one directory must SKIP it, not stop scanning.

    A `continue` that became a `break` would abandon the walk at the first vendored
    directory it met, silently under-reporting the project's source — the same class of
    quiet blindness this whole check exists to catch.
    """
    for skipped in (".venv", "node_modules", "build", "__pycache__", ".git"):
        (tmp_path / skipped).mkdir()
        (tmp_path / skipped / "dep.py").write_text("", encoding="utf-8")
    expected = []
    for i in range(10):
        pkg = tmp_path / f"pkg{i}"
        pkg.mkdir()
        (pkg / "mod.py").write_text("", encoding="utf-8")
        expected.append(f"pkg{i}/mod.py")
    assert walk_sources(tmp_path) == sorted(expected)


# --- what counts as "implementation the gate is blind to" -----------------------------
# The guard FAILS builds, so this boundary decides whether it helps or gets in the way.


def test_tests_are_not_implementation_so_tdd_red_stays_green() -> None:
    """A failing test written before the code is the RED step, not a misconfiguration.

    Treating any stray ``.py`` as "real source elsewhere" would fail the gate for every
    project practising test-first development — punishing the workflow borromeanRings is
    meant to support.
    """
    assert implementation_sources(["tests/test_feature.py"], tests_dir="tests") == []


def test_conventional_test_layouts_are_recognised_wherever_they_live() -> None:
    paths = ["test/test_a.py", "tests/helpers_test.py", "somewhere/test_deep.py"]
    assert implementation_sources(paths, tests_dir="tests") == []


def test_packaging_and_docs_scaffolding_is_not_implementation() -> None:
    paths = ["setup.py", "conftest.py", "noxfile.py", "docs/conf.py"]
    assert implementation_sources(paths, tests_dir="tests") == []


def test_a_real_second_source_tree_still_counts() -> None:
    """The case the guard exists for: 30 modules of real code the gate never sees."""
    paths = [f"tools/mod_{i}.py" for i in range(30)] + ["tests/test_x.py", "setup.py"]
    assert implementation_sources(paths, tests_dir="tests") == [
        f"tools/mod_{i}.py" for i in range(30)
    ]


def test_vendored_trees_are_not_the_projects_own_source() -> None:
    paths = ["node_modules/dep.py", ".venv/lib/dep.py", "build/gen.py", "app/main.py"]
    assert implementation_sources(paths, tests_dir="tests") == ["app/main.py"]


def test_top_directories_breaks_ties_by_name_for_a_stable_message(tmp_path: Path) -> None:
    """Equal counts rank alphabetically — a message that reshuffles per run reads as noise."""
    paths = ["zeta/a.py", "zeta/b.py", "alpha/c.py", "alpha/d.py"]
    assert top_directories(paths) == [("alpha", 2), ("zeta", 2)]


def test_top_directories_normalizes_windows_separators() -> None:
    """Backslash paths group by the same directory as their POSIX spelling."""
    assert top_directories(["tools\\a.py", "tools\\b.py"]) == [("tools", 2)]
