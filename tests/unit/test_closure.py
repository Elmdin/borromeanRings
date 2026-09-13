"""Which distributions a project is actually responsible for (#228).

`70_pip_audit` and `72_licenses` read the *installed* environment. On a clean CI
runner that equals the project's dependencies; on a developer machine it is
everything they have ever installed, and the same commit then gets a different
verdict per machine. This module is the narrowing, so these tests are mostly about
what it must NOT include.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from meta_harness.closure import (
    ClosureUnavailable,
    declared_dependencies,
    installed_closure,
    normalise,
    project_closure,
    requirement_name,
)


def _pyproject(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "pyproject.toml"
    path.write_text(body, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("Foo.Bar", "foo-bar"), ("FOO_BAR", "foo-bar"), ("foo--bar", "foo-bar"), ("x", "x")],
)
def test_names_are_pep503_normalised(raw: str, expected: str) -> None:
    assert normalise(raw) == expected


@pytest.mark.parametrize(
    ("requirement", "expected"),
    [
        ("requests", "requests"),
        ("requests>=2.0", "requests"),
        ("requests[socks]>=2,<3", "requests"),
        ('requests ; python_version < "3.11"', "requests"),
        ("  Requests_Toolbelt == 1.0 ", "requests-toolbelt"),
        ("", None),
        ("; extra == 'x'", None),
    ],
)
def test_requirement_names_survive_specifiers_extras_and_markers(
    requirement: str, expected: str | None
) -> None:
    assert requirement_name(requirement) == expected


def test_every_declared_group_counts(tmp_path: Path) -> None:
    """Dev tools included on purpose: a CVE in the type checker runs over your source."""
    path = _pyproject(
        tmp_path,
        "[project]\nname='x'\nversion='0'\ndependencies=['runtime-dep']\n"
        "[project.optional-dependencies]\ndev=['dev-dep']\ndocs=['docs-dep']\n"
        "[dependency-groups]\nextra=['group-dep']\n",
    )
    assert declared_dependencies(path) == {"runtime-dep", "dev-dep", "docs-dep", "group-dep"}


def test_a_project_with_no_dependencies_declares_an_empty_set(tmp_path: Path) -> None:
    """Empty is a real answer, and must be distinguishable from "could not tell"."""
    manifest = _pyproject(tmp_path, "[project]\nname='x'\nversion='0'\n")
    assert declared_dependencies(manifest) == set()


def test_an_unreadable_manifest_raises_rather_than_returning_empty(tmp_path: Path) -> None:
    """Fail closed: returning an empty set would silently audit nothing at all."""
    with pytest.raises(ClosureUnavailable):
        declared_dependencies(tmp_path / "absent.toml")


def test_a_malformed_manifest_raises(tmp_path: Path) -> None:
    with pytest.raises(ClosureUnavailable):
        declared_dependencies(_pyproject(tmp_path, "[project\nname="))


def test_a_declared_but_uninstalled_package_stays_in_scope() -> None:
    """It is declared, so a report naming it is about this project regardless."""
    assert "definitely-not-installed-xyz" in installed_closure(["definitely-not-installed-xyz"])


def test_the_closure_reaches_transitive_dependencies() -> None:
    """pytest pulls in pluggy; a CVE there is this project's problem."""
    closure = installed_closure(["pytest"])
    assert "pytest" in closure
    assert "pluggy" in closure


def test_the_closure_does_not_swallow_the_whole_environment() -> None:
    """The bug this module exists to prevent, asserted directly.

    Following `extra ==` requirements turned the graph into the index — measured at
    624 distributions including `notebook`, which nothing here depends on. Those are
    pulled in only when someone asks for the extra, and an extra this project wants
    is declared in its own manifest and arrives as a seed.
    """
    closure = installed_closure(["pytest"])
    assert len(closure) < 40, sorted(closure)
    for unrelated in ("notebook", "torch", "semgrep"):
        assert unrelated not in closure


def test_project_closure_is_the_declared_set_plus_its_reach(tmp_path: Path) -> None:
    path = _pyproject(
        tmp_path,
        "[project]\nname='x'\nversion='0'\n[project.optional-dependencies]\nd=['pytest']\n",
    )
    closure = project_closure(path)
    assert {"pytest", "pluggy"} <= closure


def test_a_dependency_cycle_terminates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real graphs contain cycles (a package that test-depends on its own plugin).

    Driven through a stub rather than whatever happens to be installed, so the
    cycle, the duplicate seed and the unparseable requirement are all exercised
    deterministically instead of by luck of the environment.
    """
    graph = {
        "alpha": ["beta>=1", "", "gamma; extra == 'test'"],
        "beta": ["alpha", "alpha"],  # cycle, and a duplicate
    }

    def fake_requires(name: str) -> list[str] | None:
        if name not in graph:
            raise __import__("importlib.metadata", fromlist=["x"]).PackageNotFoundError(name)
        return graph[name]

    monkeypatch.setattr("meta_harness.closure.metadata.requires", fake_requires)

    closure = installed_closure(["alpha", "alpha"])  # duplicate seed

    assert closure == {"alpha", "beta"}  # gamma is extra-only; no infinite loop
