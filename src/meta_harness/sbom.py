"""A CycloneDX-shaped SBOM of the declared dependency closure (matrix #2, row S6).

Emits what the NTIA minimum elements ask for — supplier-agnostic name, version and a
package URL per component, plus the dependency graph — as CycloneDX 1.5 JSON, from
**nothing but the stdlib**: ``tomllib`` reads the manifest, ``importlib.metadata``
reads the installed closure. No network, no new dependency, no external tool.

What it is: an honest inventory of the declared roots and everything they pull in *as
installed in the current environment*. What it is **not**: signed, attested, or a
provenance statement — those need a CI build to sign (SLSA / Sigstore) and are recorded
as a maintainer decision in ADR-0061, not claimed here. The document says so itself in
``metadata.properties`` (``borromeanrings:attestation = none``).

Deterministic: no timestamp, and the serial number is a UUIDv5 of the closure, so the
same inputs yield byte-identical output. Entry point: ``sbom.sh`` (→ :func:`main`).
See docs/specs/SPEC-supply-chain.md.
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

import tomllib

from meta_harness.supply_chain import parse_requirement

_USAGE = "usage: sbom.sh [MANIFEST=pyproject.toml] [--optional] [--out FILE]"
_NORMALIZE_RE = re.compile(r"[-_.]+")


@dataclass(frozen=True)
class Distribution:
    """An installed distribution: normalized name, version, raw ``Requires-Dist`` lines."""

    name: str
    version: str
    requires: tuple[str, ...]


@dataclass(frozen=True)
class Component:
    """One SBOM component (a resolved dependency)."""

    name: str
    version: str | None
    purl: str


def normalize_name(name: str) -> str:
    """PEP 503 normalization: lower-case, runs of ``-``/``_``/``.`` collapse to ``-``."""
    return _NORMALIZE_RE.sub("-", name).lower()


def purl(name: str, version: str | None) -> str:
    """The package URL for a PyPI distribution (``pkg:pypi/<name>[@<version>]``)."""
    base = f"pkg:pypi/{normalize_name(name)}"
    return f"{base}@{version}" if version else base


def installed_distributions() -> dict[str, Distribution]:
    """Every distribution visible to this interpreter, keyed by normalized name."""
    found: dict[str, Distribution] = {}
    for dist in metadata.distributions():
        key = normalize_name(str(dist.metadata["Name"] or ""))
        found.setdefault(key, Distribution(key, dist.version, tuple(dist.requires or ())))
    found.pop("", None)  # a distribution with no Name header is not addressable
    return found


def _load_project(pyproject_text: str) -> dict[str, Any]:
    """The ``[project]`` table of a manifest (``{}`` when absent or empty text)."""
    return dict(tomllib.loads(pyproject_text).get("project", {}))


def declared_roots(pyproject_text: str, *, include_optional: bool = False) -> tuple[str, ...]:
    """The requirement strings the manifest declares (runtime, plus optional groups on request).

    Unparseable entries are dropped: an SBOM inventories what can be named.
    """
    project = _load_project(pyproject_text)
    raw: list[str] = list(project.get("dependencies", []))
    if include_optional:
        for group in project.get("optional-dependencies", {}).values():
            raw.extend(group)
    return tuple(r for r in raw if parse_requirement(r) is not None)


def _follow(requirement: str, installed: Mapping[str, Distribution]) -> str | None:
    """The normalized name a requirement resolves to, or ``None`` to skip it.

    Skipped: an unparseable line, an ``extra ==`` marker (an extra nobody requested), and
    a conditional (environment-marked) requirement that is not installed — the marker
    presumably excluded it here. An *unconditional* missing requirement is returned so
    the walk can report it as unresolved rather than silently drop it.
    """
    parsed = parse_requirement(requirement)
    if parsed is None or "extra" in parsed.marker:
        return None
    name = normalize_name(parsed.name)
    if parsed.marker and name not in installed:
        return None
    return name


def closure(
    roots: Sequence[str], installed: Mapping[str, Distribution]
) -> tuple[tuple[Component, ...], tuple[str, ...], dict[str, tuple[str, ...]]]:
    """Walk ``roots`` through the installed ``Requires-Dist`` graph.

    Returns ``(components sorted by name, unresolved names in first-seen order,
    edges: purl -> dependsOn purls)``. Each distribution is visited once (cycles are
    fine).
    """
    queue = [name for name in (_follow(r, installed) for r in roots) if name is not None]
    seen: set[str] = set()
    components: list[Component] = []
    unresolved: list[str] = []
    edges: dict[str, tuple[str, ...]] = {}
    while queue:
        name = queue.pop(0)
        if name in seen:
            continue
        seen.add(name)
        dist = installed.get(name)
        if dist is None:
            unresolved.append(name)
            continue
        components.append(Component(dist.name, dist.version, purl(dist.name, dist.version)))
        deps = [d for d in (_follow(r, installed) for r in dist.requires) if d is not None]
        queue.extend(deps)
        edges[purl(dist.name, dist.version)] = tuple(
            sorted(purl(d, installed[d].version) for d in deps if d in installed)
        )
    return tuple(sorted(components, key=lambda c: c.name)), tuple(unresolved), edges


def _component_entry(component: Component) -> dict[str, Any]:
    return {
        "type": "library",
        "name": component.name,
        "version": component.version,
        "purl": component.purl,
        "bom-ref": component.purl,
    }


def sbom_document(
    project_name: str,
    project_version: str,
    components: Sequence[Component],
    *,
    roots: Sequence[str],
    unresolved: Sequence[str],
    edges: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    """Assemble the CycloneDX 1.5 document; ``roots`` are the purls the project depends on."""
    app_ref = purl(project_name, project_version)
    properties = [
        {"name": "borromeanrings:attestation", "value": "none"},
        {"name": "borromeanrings:signed", "value": "false"},
    ]
    if unresolved:
        properties.append({"name": "borromeanrings:unresolved", "value": ", ".join(unresolved)})
    serial = uuid.uuid5(uuid.NAMESPACE_URL, "|".join([app_ref, *(c.purl for c in components)]))
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {
            "tools": [{"name": "borromeanRings sbom.sh"}],
            "component": {
                "type": "application",
                "name": normalize_name(project_name),
                "version": project_version,
                "purl": app_ref,
                "bom-ref": app_ref,
            },
            "properties": properties,
        },
        "components": [_component_entry(c) for c in components],
        "dependencies": [
            {"ref": app_ref, "dependsOn": list(roots)},
            *({"ref": c.purl, "dependsOn": list(edges.get(c.purl, ()))} for c in components),
        ],
    }


def render_sbom(
    pyproject_text: str, installed: Mapping[str, Distribution], *, include_optional: bool
) -> dict[str, Any]:
    """Manifest text + installed map → the SBOM document (pure; no I/O)."""
    project = _load_project(pyproject_text)
    roots = declared_roots(pyproject_text, include_optional=include_optional)
    components, unresolved, edges = closure(roots, installed)
    resolved = {c.name for c in components}
    root_purls = sorted(
        {
            purl(name, installed[name].version)
            for name in (_follow(r, installed) for r in roots)
            if name is not None and name in resolved
        }
    )
    return sbom_document(
        str(project.get("name", "unknown")),
        str(project.get("version", "0")),
        components,
        roots=root_purls,
        unresolved=unresolved,
        edges=edges,
    )


def _parse_args(argv: Sequence[str]) -> tuple[Path, bool, Path | None] | None:
    """``(manifest, include_optional, out)`` or ``None`` on a usage error."""
    manifest, optional, out = Path("pyproject.toml"), False, None
    args = list(argv)
    while args:
        arg = args.pop(0)
        if arg == "--optional":
            optional = True
        elif arg == "--out" and args:
            out = Path(args.pop(0))
        elif not arg.startswith("-"):
            manifest = Path(arg)
        else:
            return None
    return manifest, optional, out


def main(argv: Sequence[str]) -> int:
    """CLI: print (or write) the SBOM for a manifest. 0 ok · 1 unreadable manifest · 2 usage."""
    parsed = _parse_args(argv)
    if parsed is None:
        print(_USAGE, file=sys.stderr)
        return 2
    manifest, optional, out = parsed
    try:
        text = manifest.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"sbom: cannot read manifest {manifest}: {exc}", file=sys.stderr)
        return 1
    doc = render_sbom(text, installed_distributions(), include_optional=optional)
    rendered = json.dumps(doc, indent=2) + "\n"
    if out is None:
        sys.stdout.write(rendered)
    else:
        out.write_text(rendered, encoding="utf-8")
    return 0
