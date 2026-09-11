"""The gate must run the toolchain this repo pins. ADR-0077.

These are the tests that would have caught the 2026-09-10 divergence: two PRs green
on a laptop and red on GitHub because ``pip install -e ".[dev]"`` resolved newer
releases of ``ruff`` and ``mypy`` than the laptop had.
"""

import re
import subprocess
from pathlib import Path

import pytest
import tomllib

from meta_harness.toolchain import (
    TOOLS,
    canonical,
    drifts,
    parse_pins,
    parse_version,
    render,
    unpinned,
)

REPO = Path(__file__).resolve().parents[2]
CONSTRAINTS = REPO / "constraints-dev.txt"

# Not pinnable from PyPI: the interpreter, stdlib modules, and the coreutils
# binaries `checks/_lib.sh` bounds each check with.
_NOT_A_DISTRIBUTION = {"python3", "compileall", "timeout", "gtimeout"}
# Import name → distribution name, where they differ.
_DIST_OF_MODULE = {"pip_audit": "pip-audit"}


def _dev_requirements() -> list[str]:
    data = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    return list(data["project"]["optional-dependencies"]["dev"])


def _observe(invocation: tuple[str, ...]) -> str | None:
    """The version the gate would see, reached exactly as the gate reaches it."""
    try:
        done = subprocess.run(  # noqa: S603 - fixed argv from the TOOLS table
            [*invocation, "--version"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_version(f"{done.stdout}\n{done.stderr}")


def _tools_named_by_the_checks() -> set[str]:
    """Every pinnable tool the check scripts reach for, however they reach it."""
    found: set[str] = set()
    for script in sorted((REPO / "checks").rglob("*.sh")):
        text = script.read_text(encoding="utf-8")
        found |= set(re.findall(r'run_check\s+"[^"]+"\s+"([^"]+)"', text))
        found |= set(re.findall(r"command -v ([A-Za-z0-9._-]+)", text))
        found |= {
            _DIST_OF_MODULE.get(m, m) for m in re.findall(r"python3 -m ([A-Za-z0-9_]+)", text)
        }
    return {canonical(t) for t in found - _NOT_A_DISTRIBUTION}


def test_the_tools_table_mirrors_what_the_checks_actually_invoke() -> None:
    """A tool added to a check without a pin is a hole in the guarantee."""
    assert _tools_named_by_the_checks() == {canonical(t.dist) for t in TOOLS}


def test_a_constraints_file_pins_the_whole_resolved_closure() -> None:
    """Direct pins alone leave transitive tools (e.g. coverage) free to move."""
    assert CONSTRAINTS.is_file(), "constraints-dev.txt is missing"
    pins = parse_pins(CONSTRAINTS.read_text(encoding="utf-8"))
    assert "coverage" in pins, "the coverage ratchet depends on coverage's own version"
    assert len(pins) > len(TOOLS)


def test_every_gate_tool_is_pinned_exactly_in_both_places() -> None:
    """An upper bound at the next major is not enough: ruff reformats in minors."""
    constraints = parse_pins(CONSTRAINTS.read_text(encoding="utf-8"))
    declared = parse_pins("\n".join(_dev_requirements()))
    assert unpinned(constraints) == (), render((), unpinned(constraints))
    assert unpinned(declared) == (), render((), unpinned(declared))


def test_every_dev_requirement_is_pinned_and_present_in_the_constraints() -> None:
    """Adding a dev dependency without pinning it reopens the whole hole.

    Not limited to the gate's own tools: a test-only dependency (a parser used as a
    conformance oracle, say) decides test outcomes, so its version decides verdicts too.
    """
    constraints = parse_pins(CONSTRAINTS.read_text(encoding="utf-8"))
    declared = _dev_requirements()
    pinned = parse_pins("\n".join(declared))
    named = {canonical(re.split(r"[<>=!~;\[]", line, maxsplit=1)[0].strip()) for line in declared}

    unpinned_here = sorted(named - set(pinned))
    assert unpinned_here == [], f"dev requirements without an exact pin: {unpinned_here}"

    absent = sorted(named - set(constraints))
    assert absent == [], f"pinned in pyproject but missing from constraints-dev.txt: {absent}"


def test_pyproject_and_the_constraints_file_agree() -> None:
    constraints = parse_pins(CONSTRAINTS.read_text(encoding="utf-8"))
    declared = parse_pins("\n".join(_dev_requirements()))
    disagree = {
        name: (version, constraints[name])
        for name, version in declared.items()
        if name in constraints and constraints[name] != version
    }
    assert disagree == {}


@pytest.mark.parametrize("tool", TOOLS, ids=lambda t: t.dist)
def test_the_gate_runs_the_pinned_version_of_each_tool(tool) -> None:  # type: ignore[no-untyped-def]
    """Observed the way the check invokes it — a PATH shim can shadow site-packages."""
    declared = parse_pins(CONSTRAINTS.read_text(encoding="utf-8"))
    observed = {canonical(tool.dist): _observe(tool.invocation)}
    found = drifts(declared, observed, (tool,))
    assert found == (), render(found)
