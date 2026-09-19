"""Supply-chain hardening: lockfile integrity + pinned dependencies (pure decisions).

Two threshold-free facts about a project's dependency declarations, each a yes/no
per file or per requirement — no score, no target number (matrix #2, rows S8):

* **Lockfile integrity** — when the project declares a lockfile
  (``[supply_chain].lockfile``), a change to a dependency *manifest* (``pyproject.toml``,
  ``package.json``) that is not accompanied by a change to that lockfile means the
  lock is stale: what CI installs no longer matches what the manifest says.
* **Pinned dependencies** — every runtime requirement in ``[project].dependencies``
  (and the optional groups, when ``[supply_chain].pin_optional`` is on) must carry an
  upper bound or an exact/compatible pin (``==``, ``===``, ``~=``, ``<``, ``<=``). A
  bare name or a ``>=``-only requirement floats to whatever the index serves tomorrow.

Pure logic here (stdlib ``tomllib`` + ``re``; no ``packaging`` dependency). The check
scripts (``checks/ci/76_lockfile.sh``, ``checks/ci/78_pins.sh``) supply the changed-path
set from git and the manifest text, and map the result to a receipt. See
docs/specs/SPEC-supply-chain.md and ADR-0061.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import tomllib

#: Dependency manifests whose change must be mirrored by the declared lockfile.
DEFAULT_MANIFESTS: tuple[str, ...] = ("pyproject.toml", "package.json")

#: Version operators that bound a requirement from above (or pin it exactly).
_PINNING_OPS = frozenset({"==", "===", "~=", "<", "<="})

_NAME = r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?"
_REQUIREMENT_RE = re.compile(
    rf"^\s*(?P<name>{_NAME})\s*(?:\[(?P<extras>[^\]]*)\])?\s*(?P<rest>.*?)\s*$"
)
_CLAUSE_RE = re.compile(r"^(?P<op>===|==|~=|!=|<=|>=|<|>)\s*(?P<version>[^<>=!~\s]\S*)$")
_COMMIT_PIN_RE = re.compile(r"@[0-9a-fA-F]{7,40}$")


# ----------------------------------------------------------------------- lockfile


@dataclass(frozen=True)
class LockfileVerdict:
    """Outcome of the lockfile-integrity decision: ``pass`` / ``fail`` / ``noop`` + why."""

    status: str
    message: str


def _normalize_path(path: str) -> str:
    """Strip a leading ``./`` so declared and git-reported paths compare equal."""
    return path[2:] if path.startswith("./") else path


def lockfile_verdict(
    changed_paths: Sequence[str],
    *,
    lockfile: str,
    manifests: Sequence[str] = DEFAULT_MANIFESTS,
    lockfile_exists: bool = True,
) -> LockfileVerdict:
    """Decide whether the declared lockfile kept up with the manifest.

    ``changed_paths`` are the paths (relative to the project root) that differ from the
    merge-base. No ``lockfile`` declared ⇒ ``noop`` (the rule is off — honest about
    inspecting nothing). A declared lockfile that does not exist ⇒ ``fail`` (a
    misconfiguration must never read as "nothing to check"). A changed manifest without
    a changed lockfile ⇒ ``fail`` naming both; otherwise ``pass``.
    """
    lockfile = _normalize_path(lockfile)
    if not lockfile:
        return LockfileVerdict(
            "noop", "no [supply_chain].lockfile declared — lockfile integrity is off"
        )
    if not lockfile_exists:
        return LockfileVerdict(
            "fail",
            f"declared lockfile '{lockfile}' does not exist — generate it, or clear "
            "[supply_chain].lockfile if this project has none",
        )
    changed = {_normalize_path(p) for p in changed_paths}
    touched = [m for m in manifests if _normalize_path(m) in changed]
    if not touched:
        return LockfileVerdict(
            "pass", f"no manifest ({', '.join(manifests)}) changed — '{lockfile}' need not change"
        )
    if lockfile in changed:
        return LockfileVerdict(
            "pass", f"manifest ({', '.join(touched)}) changed together with '{lockfile}'"
        )
    return LockfileVerdict(
        "fail",
        f"MANIFEST CHANGED WITHOUT THE LOCKFILE: {', '.join(touched)} changed but "
        f"'{lockfile}' did not change — regenerate the lockfile and commit it with the "
        "manifest change",
    )


# ------------------------------------------------------------ requirement parsing


@dataclass(frozen=True)
class Requirement:
    """The PEP 508 pieces this module needs: name, extras, version spec, URL, marker."""

    name: str
    extras: str
    specifier: str
    url: str
    marker: str


def parse_requirement(requirement: str) -> Requirement | None:
    """Split a PEP 508 requirement string; ``None`` if it has no valid project name.

    Handles ``name[extras] spec ; marker``, ``name @ url ; marker`` and the legacy
    parenthesised spec ``name (>=1, <2)``. Deliberately a subset: enough to judge pins
    and to walk a dependency closure, with no third-party parser.
    """
    body, _, marker = requirement.partition(";")
    match = _REQUIREMENT_RE.match(body)
    if match is None:
        return None
    rest = match.group("rest")
    url = ""
    if rest.startswith("@"):
        url, rest = rest[1:].strip(), ""
    if rest.startswith("(") and rest.endswith(")"):
        rest = rest[1:-1].strip()
    return Requirement(
        name=match.group("name"),
        extras=(match.group("extras") or "").strip(),
        specifier=rest,
        url=url,
        marker=marker.strip(),
    )


# ---------------------------------------------------------------------- pin rule


def _url_pin_status(url: str) -> tuple[bool, str]:
    """A direct reference is pinned only by a commit hash or a content hash fragment."""
    if "sha256=" in url or _COMMIT_PIN_RE.search(url.split("#", 1)[0]):
        return True, ""
    return False, "direct URL reference without a commit hash or sha256= fragment"


def _specifier_pin_status(specifier: str) -> tuple[bool, str]:
    """Judge a comma-separated version specifier: bounded above, or exactly pinned?"""
    if not specifier:
        return False, "no version specifier (bare requirement floats to the newest release)"
    ops: list[str] = []
    for clause in (c.strip() for c in specifier.split(",")):
        match = _CLAUSE_RE.match(clause)
        if match is None:
            return False, f"unparseable version clause '{clause}'"
        ops.append(match.group("op"))
    if any(op in _PINNING_OPS for op in ops):
        return True, ""
    return (
        False,
        "only a lower bound / exclusion (>=, >, !=) — add an upper bound (<N) or an "
        "exact/compatible pin (==, ~=)",
    )


def pin_status(requirement: str) -> tuple[bool, str]:
    """``(pinned, reason)`` for one requirement line; ``reason`` is empty when pinned."""
    parsed = parse_requirement(requirement)
    if parsed is None:
        return False, f"unparseable requirement '{requirement.strip()}'"
    if parsed.url:
        return _url_pin_status(parsed.url)
    return _specifier_pin_status(parsed.specifier)


@dataclass(frozen=True)
class PinFinding:
    """One unpinned requirement: its group (``project`` or an optional group) + line."""

    group: str
    requirement: str
    reason: str


@dataclass(frozen=True)
class PinReport:
    """How many requirements were judged, which failed, and whether deps are dynamic."""

    inspected: int
    findings: tuple[PinFinding, ...]
    dynamic: bool


def _requirement_list(value: Any, where: str) -> list[str]:
    """Validate a dependency list from pyproject (fail fast on the wrong shape)."""
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"pyproject.toml: {where} must be a list of strings")
    return list(value)


def _dependency_groups(project: dict[str, Any], pin_optional: bool) -> list[tuple[str, list[str]]]:
    """``(group, requirements)`` pairs to judge: runtime deps, plus optional groups on request."""
    groups = [
        ("project", _requirement_list(project.get("dependencies", []), "[project].dependencies"))
    ]
    if pin_optional:
        optional = project.get("optional-dependencies", {})
        for name, reqs in optional.items():
            groups.append(
                (str(name), _requirement_list(reqs, f"[project.optional-dependencies].{name}"))
            )
    return groups


def pin_report(pyproject_text: str, *, pin_optional: bool = False) -> PinReport:
    """Judge every declared requirement in ``pyproject_text`` for a pin/upper bound.

    ``inspected`` is the number of requirement lines judged (0 ⇒ nothing to inspect —
    the caller reports ``noop``). ``dynamic`` is True when ``[project].dynamic`` lists
    ``dependencies``: the manifest defers them to build time, so nothing here can be
    judged — the caller decides how loudly to say so.

    Raises ``ValueError`` on malformed TOML or a non-list dependency table.
    """
    try:
        raw = tomllib.loads(pyproject_text)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"pyproject.toml is not valid TOML: {exc}") from exc
    project = raw.get("project", {})
    dynamic = "dependencies" in project.get("dynamic", [])
    inspected = 0
    findings: list[PinFinding] = []
    for group, requirements in _dependency_groups(project, pin_optional):
        for requirement in requirements:
            inspected += 1
            pinned, reason = pin_status(requirement)
            if not pinned:
                findings.append(PinFinding(group, requirement, reason))
    return PinReport(inspected=inspected, findings=tuple(findings), dynamic=dynamic)
