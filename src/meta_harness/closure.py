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

**When in doubt, include.** For a security check a false inclusion costs a look while
a false exclusion costs the finding, so every ambiguity resolves toward including:

* Environment markers are not evaluated — a package that might not be needed on *this*
  platform is still listed.
* A requirement guarded **solely** by an extra nobody asked for is skipped. Following
  all of them turns a dependency graph into the whole index (measured: 624
  distributions against 55 for the real closure, including ``notebook``).
* But an extra the project **did** ask for is followed. ``pip-audit[doc]`` in the
  manifest means ``pdoc`` is this project's dependency, and a CVE in it is this
  project's problem. Requested extras are tracked per distribution rather than
  stripped off the name.
* And a marker that could be satisfied *without* the extra (``extra == "x" or
  sys_platform == "win32"``) is followed too, because presence of the word ``extra``
  is not proof the requirement is optional.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from importlib import metadata
from pathlib import Path

import tomllib

#: PEP 508 requirement -> distribution name (drops extras, markers, specifiers).
_REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
#: The bracketed extras of a requirement: `foo[bar, baz] >= 1`.
_REQUIREMENT_EXTRAS = re.compile(r"^\s*[A-Za-z0-9][A-Za-z0-9._-]*\s*\[([^\]]*)\]")
#: Each `extra == "name"` an environment marker mentions.
_MARKER_EXTRA = re.compile(r"""\bextra\s*==\s*["']([^"']+)["']""")


class ClosureUnavailable(Exception):
    """The declared dependencies cannot be read. Callers fail closed (#228)."""


def normalise(name: str) -> str:
    """PEP 503 normalised distribution name, so `Foo.Bar` and `foo-bar` compare equal."""
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_name(requirement: str) -> str | None:
    """The distribution a PEP 508 requirement string refers to, normalised."""
    match = _REQUIREMENT_NAME.match(requirement)
    return normalise(match.group(1)) if match else None


def requirement_extras(requirement: str) -> frozenset[str]:
    """The extras a requirement asks for: ``pip-audit[doc, test]`` -> {doc, test}."""
    match = _REQUIREMENT_EXTRAS.match(requirement)
    if not match:
        return frozenset()
    return frozenset(part.strip().lower() for part in match.group(1).split(",") if part.strip())


def _is_optional(requirement: str, wanted_extras: frozenset[str]) -> bool:
    """True when this requirement exists only to serve an extra nobody asked for.

    Presence-based on purpose, with the ambiguity resolved toward keeping it: a
    marker that names an extra we did want, or that could be satisfied without the
    extra at all (``extra == "x" or sys_platform == "win32"``), is not optional.
    """
    marker = requirement.partition(";")[2]
    named = {name.lower() for name in _MARKER_EXTRA.findall(marker)}
    if not named:
        return False
    if named & wanted_extras:
        return False
    return " or " not in marker


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
    return set(declared_requirements(pyproject))


def declared_requirements(pyproject: Path) -> dict[str, set[str]]:
    """Every declared distribution mapped to the extras the project asked of it.

    ``pip-audit[doc]`` in the manifest means ``pdoc`` is this project's dependency,
    so the extras have to survive parsing rather than being stripped off the name.

    ``[build-system].requires`` counts too: the build backend executes over this
    project's source, which is the same reason the dev tools are included.
    """
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ClosureUnavailable(f"cannot read {pyproject}: {exc}") from exc

    project = data.get("project", {})
    groups: list[object] = [project.get("dependencies")]
    groups += (project.get("optional-dependencies") or {}).values()
    groups += (data.get("dependency-groups") or {}).values()
    groups.append((data.get("build-system") or {}).get("requires"))

    wanted: dict[str, set[str]] = {}
    for group in groups:
        for entry in _strings(group):
            name = requirement_name(entry)
            if name:
                wanted.setdefault(name, set()).update(requirement_extras(entry))
    return wanted


def _strings(group: object) -> list[str]:
    """The string entries of a declared group; anything else is not a requirement.

    ``[dependency-groups]`` permits ``{include-group = "..."}`` tables alongside
    requirement strings, and a malformed manifest can put anything here.
    """
    return [entry for entry in group if isinstance(entry, str)] if isinstance(group, list) else []


def installed_closure(seeds: Iterable[str] | Mapping[str, set[str]]) -> set[str]:
    """``seeds`` plus every distribution reachable from them through installed metadata.

    ``seeds`` may be a mapping of distribution -> requested extras (what
    :func:`declared_requirements` returns) or a bare iterable of names.

    Breadth-first over ``Requires-Dist``, skipping requirements that exist only to
    serve an extra. A seed that is not installed is still kept: it is declared, so a
    report naming it is about this project even if this environment lacks it.
    """
    extras: Mapping[str, set[str]] = seeds if isinstance(seeds, Mapping) else {}
    pending = [(normalise(seed), frozenset(extras.get(seed, ()))) for seed in seeds]
    seen: set[str] = set()
    while pending:
        name, wanted = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        try:
            requires = metadata.requires(name) or []
        except metadata.PackageNotFoundError:
            continue  # declared but absent here — still ours, just not installed
        for requirement in requires:
            if _is_optional(requirement, wanted):
                continue
            child = requirement_name(requirement)
            if child and child not in seen:
                # `pip-audit[doc, test]; extra == "dev"` names extras of its own.
                pending.append((child, requirement_extras(requirement)))
    return seen


def project_closure(pyproject: Path) -> set[str]:
    """The declared dependencies and everything they pull in, normalised."""
    return installed_closure(declared_requirements(pyproject))
