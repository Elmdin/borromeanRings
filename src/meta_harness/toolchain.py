"""Toolchain determinism: the gate's verdict must not depend on which tool release ran.

ADR-0008 accepted lower-bound ranges for the check toolchain and deferred exact
pinning until "CI/local drift causes a problem". It did. On 2026-09-10 two pull
requests went red on GitHub while green locally, because ``pip install -e ".[dev]"``
resolved newer releases than the machine that produced them: ``ruff`` 0.16.7 against
0.15.8 reformatted a file, and ``mypy`` crossed a major version. A formatter's output
is not covered by semantic versioning, so an upper bound at the next major (the
``78_pins`` rule, ADR-0061) is necessary but *not sufficient* for a tool whose output
IS the verdict. Those tools need an exact pin.

This module is the pure core that compares the pins a repo *declares* against the
versions its gate *observes*. It performs no I/O: the caller supplies both the file
text and the observed versions, so every branch is testable without a subprocess.

One detail earns the ``Tool.invocation`` field. The checks do not agree on how they
reach their tool: ``10_format`` runs ``ruff`` from ``PATH`` while ``40_test`` runs
``python3 -m pytest``. On a machine with a user-site shim those resolve to *different
installs* of the same distribution, so a drift check that reads
``importlib.metadata`` alone can certify a version the gate never runs. Each tool is
therefore recorded with the argv the gate actually uses, and observation must mirror
it. See docs/adr/0077-pin-the-check-toolchain.md.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass

# A PEP 440 release with optional pre/post/dev suffix, as printed by `--version`.
_VERSION = re.compile(r"\b(\d+(?:\.\d+)*(?:(?:a|b|rc)\d+)?(?:\.post\d+)?(?:\.dev\d+)?)\b")
# `name == version` in a requirement or constraints line, before any marker/comment.
_PIN = re.compile(r"^\s*([A-Za-z0-9._-]+)\s*==\s*([^\s;#,]+)")


@dataclass(frozen=True)
class Tool:
    """A gate tool and the argv the gate uses to reach it.

    ``dist`` is the PyPI distribution name (what a pin names); ``invocation`` is the
    command the check runs, which is what must be observed.
    """

    dist: str
    invocation: tuple[str, ...]


@dataclass(frozen=True)
class Drift:
    """One tool whose observed version does not match its declared pin."""

    dist: str
    declared: str
    observed: str | None  # None ⇒ the tool was absent or printed no parseable version

    @property
    def reason(self) -> str:
        """Why this tool is a drift, phrased for a check log."""
        if self.observed is None:
            return f"pinned {self.declared}, but the gate could not read a version"
        return f"pinned {self.declared}, but the gate runs {self.observed}"


# The tools whose output decides a verdict, with the invocation each check uses.
# `test_every_gate_tool_is_pinned` keeps this in step with checks/ — a tool added to
# a check without a pin here is a hole in the guarantee, so the suite fails.
TOOLS: tuple[Tool, ...] = (
    Tool("ruff", ("ruff",)),
    Tool("mypy", ("mypy",)),
    Tool("pytest", ("python3", "-m", "pytest")),
    Tool("bandit", ("bandit",)),
    Tool("mutmut", ("mutmut",)),
    Tool("pip-audit", ("python3", "-m", "pip_audit")),
    Tool("pip-licenses", ("pip-licenses",)),
)


def canonical(name: str) -> str:
    """Canonical distribution name (PEP 503): case-folded, runs of ``-_.`` to ``-``."""
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_version(text: str) -> str | None:
    """First PEP 440 release in ``--version`` output, or None if there is none.

    Handles every shape the gate's tools print, including ``mutmut, version 3.6.0``
    and ``mypy 1.19.1 (compiled: yes)``.
    """
    match = _VERSION.search(text)
    return match.group(1) if match else None


def parse_pins(text: str) -> Mapping[str, str]:
    """Exact (``==``) pins in requirement lines, keyed by canonical name.

    Non-exact requirements are ignored rather than rejected: this answers "what is
    pinned", and a separate rule (``78_pins``) decides whether a range is allowed.
    """
    pins: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        match = _PIN.match(line)
        if match:
            pins[canonical(match.group(1))] = match.group(2)
    return pins


def drifts(
    declared: Mapping[str, str],
    observed: Mapping[str, str | None],
    tools: tuple[Tool, ...] = TOOLS,
) -> tuple[Drift, ...]:
    """Tools whose observed version differs from the declared pin.

    A tool with no declared pin is skipped here — ``unpinned`` reports that, so the
    two failure modes stay distinguishable in a log.
    """
    out: list[Drift] = []
    for tool in tools:
        want = declared.get(canonical(tool.dist))
        if want is None:
            continue
        got = observed.get(canonical(tool.dist))
        if got != want:
            out.append(Drift(tool.dist, want, got))
    return tuple(out)


def unpinned(declared: Mapping[str, str], tools: tuple[Tool, ...] = TOOLS) -> tuple[str, ...]:
    """Gate tools with no exact pin, in declaration order."""
    return tuple(t.dist for t in tools if canonical(t.dist) not in declared)


def render(found: tuple[Drift, ...], missing: tuple[str, ...] = ()) -> str:
    """A check-log body naming every drift and every unpinned tool; '' when clean."""
    lines = [f"{d.dist}: {d.reason}" for d in found]
    lines += [f"{name}: no exact pin declared" for name in missing]
    return "\n".join(lines)
