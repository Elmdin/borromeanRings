"""The project's own dependency closure — what a supply-chain check may judge (#228).

``70_pip_audit`` and ``72_licenses`` read the *installed* environment. On a clean CI
runner that happens to equal the project's declared dependencies, and both checks'
comments said so — ``in CI that is the project's declared deps``. Off CI it is false,
and nothing detected the difference: on a developer machine the audit reported 43
CVE'd and 14 GPL packages — torch, notebook, semgrep, pynput — none of them
dependencies of anything being gated.

That breaks the claim ``verify.yml`` makes in its own header: the same ``verify.sh``,
author- and environment-agnostic (QAS-2). Same commit, different verdict, decided by
what else happens to be installed. And the remedy each check printed was *actionable
and wrong*: following it would write a permanent exception into the project's config
for a package it does not depend on.

This module answers "which distributions is this project actually responsible for?"
— the declared dependencies plus everything they pull in — so the checks can judge
that set and say so. Pure stdlib: the declarations come from ``pyproject.toml``, the
edges from installed metadata (``importlib.metadata``).

**Deliberately over-inclusive about platforms, strict about extras.** Environment
markers are not evaluated, so a package that might not be needed on *this* platform is
still listed — for a security check a false inclusion costs a look while a false
exclusion costs the finding. But a requirement guarded by ``extra == "..."`` is
skipped: those are pulled in only when someone asks for that extra, and following them
turns a dependency graph into the whole index (measured: 624 distributions instead of
33, including `notebook`, which nothing here depends on). An extra this project
actually wants is declared in its own manifest and arrives as a seed.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from importlib import metadata
from pathlib import Path

import tomllib

#: PEP 508 requirement -> distribution name (drops extras, markers, specifiers).
_REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
#: A requirement that exists only to serve an extra: `foo; extra == "bar"`.
_EXTRA_ONLY = re.compile(r";.*\bextra\s*==")


class ClosureUnavailable(Exception):
    """The declared dependencies cannot be read. Callers fail closed (#228)."""


def normalise(name: str) -> str:
    """PEP 503 normalised distribution name, so `Foo.Bar` and `foo-bar` compare equal."""
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_name(requirement: str) -> str | None:
    """The distribution a PEP 508 requirement string refers to, normalised."""
    match = _REQUIREMENT_NAME.match(requirement)
    return normalise(match.group(1)) if match else None


def declared_dependencies(pyproject: Path) -> set[str]:
    """Every distribution the project declares, across all groups.

    Runtime dependencies, every ``[project.optional-dependencies]`` group, and every
    ``[dependency-groups]`` entry. Development tools are included on purpose: a CVE in
    the type checker or the mutation runner is a CVE in something that executes over
    this project's source.

    Raises :class:`ClosureUnavailable` when the manifest cannot be read or parsed —
    never returns an empty set to mean "could not tell", because an empty closure is
    also the correct answer for a project with no dependencies, and a check must be
    able to distinguish those two.
    """
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ClosureUnavailable(f"cannot read {pyproject}: {exc}") from exc

    requirements: list[str] = []
    project = data.get("project", {})
    requirements += project.get("dependencies", []) or []
    for group in (project.get("optional-dependencies", {}) or {}).values():
        requirements += group or []
    for group in (data.get("dependency-groups", {}) or {}).values():
        requirements += [entry for entry in (group or []) if isinstance(entry, str)]

    return {name for name in map(requirement_name, requirements) if name}


def installed_closure(seeds: Iterable[str]) -> set[str]:
    """``seeds`` plus every distribution reachable from them through installed metadata.

    Breadth-first over ``Requires-Dist``, skipping requirements that exist only to
    serve an extra. A seed that is not installed is still kept: it is declared, so a
    report naming it is about this project even if this environment lacks it.
    """
    pending = [normalise(seed) for seed in seeds]
    seen: set[str] = set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        try:
            requires = metadata.requires(name) or []
        except metadata.PackageNotFoundError:
            continue  # declared but absent here — still ours, just not installed
        for requirement in requires:
            if _EXTRA_ONLY.search(requirement):
                continue  # optional: only pulled in when that extra is requested
            child = requirement_name(requirement)
            if child and child not in seen:
                pending.append(child)
    return seen


def project_closure(pyproject: Path) -> set[str]:
    """The declared dependencies and everything they pull in, normalised."""
    return installed_closure(declared_dependencies(pyproject))
