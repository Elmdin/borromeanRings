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
)

REPO = Path(__file__).resolve().parents[2]

# Transitive, but they decide a verdict: coverage measures the ratchet and libcst
# generates mutmut's mutants. Declared in `dev` so they can be pinned.
_DECIDERS_NOT_INVOKED_DIRECTLY = {"coverage", "libcst"}

# Not pinnable from PyPI: the interpreter, stdlib modules, and the coreutils
# binaries `checks/_lib.sh` bounds each check with.
_NOT_A_DISTRIBUTION = {"python3", "compileall", "timeout", "gtimeout"}
# Import name → distribution name, where they differ.
_DIST_OF_MODULE = {"pip_audit": "pip-audit"}
# Binary name → distribution name, where they differ. Pre-seeded with the binaries that
# in-flight branches will add, so their merge only has to extend TOOLS and the pins.
# Inert until a check actually reaches for the binary.
_DIST_OF_BINARY = {"shellcheck": "shellcheck-py"}


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
    return {canonical(_DIST_OF_BINARY.get(name, name)) for name in found - _NOT_A_DISTRIBUTION}


def test_the_tools_table_mirrors_what_the_checks_actually_invoke() -> None:
    """A tool added to a check without a pin is a hole in the guarantee.

    This makes ``TOOLS`` a registry mirror, like the README's check counts. Extending it
    is a standing obligation of any change that adds a check invoking a new binary, so
    the failure has to say that outright rather than print two sets and leave it there.
    """
    found = _tools_named_by_the_checks()
    known = {canonical(t.dist) for t in TOOLS}

    unregistered = sorted(found - known)
    assert not unregistered, (
        f"checks invoke {unregistered}, which meta_harness.toolchain.TOOLS does not know "
        f"about, so nothing pins {'it' if len(unregistered) == 1 else 'them'}. In the "
        "SAME change: (1) add a Tool(dist, invocation) to TOOLS, where invocation is the "
        "argv the check actually uses — `('x',)` for a PATH binary, "
        "`('python3', '-m', 'x')` for a module; (2) pin the distribution with == in "
        "[project.optional-dependencies].dev; (3) if the binary and distribution names "
        "differ, add an entry to _DIST_OF_BINARY in this file."
    )

    orphaned = sorted(known - found)
    assert not orphaned, (
        f"TOOLS pins {orphaned}, which no check invokes any more. Remove the entry and "
        "its pin, or restore the check that used it — an unused pin freezes a version "
        "for no reason and will eventually block on a CVE."
    )


def test_every_dev_requirement_is_pinned_exactly() -> None:
    """Adding a dev dependency without pinning it reopens the whole hole.

    Not limited to the gate's own tools: a test-only dependency (a parser used as a
    conformance oracle, say) decides test outcomes, so its version decides verdicts too.
    """
    declared = _dev_requirements()
    pinned = parse_pins("\n".join(declared))
    named = {canonical(re.split(r"[<>=!~;\[]", line, maxsplit=1)[0].strip()) for line in declared}

    unpinned_here = sorted(named - set(pinned))
    assert unpinned_here == [], f"dev requirements without an exact pin: {unpinned_here}"

    missing = sorted(_DECIDERS_NOT_INVOKED_DIRECTLY - named)
    assert missing == [], f"a verdict-deciding package is no longer declared: {missing}"


@pytest.mark.parametrize("tool", TOOLS, ids=lambda t: t.dist)
def test_the_gate_runs_the_pinned_version_of_each_tool(tool) -> None:  # type: ignore[no-untyped-def]
    """Observed the way the check invokes it — a PATH shim can shadow site-packages."""
    declared = parse_pins("\n".join(_dev_requirements()))
    observed = {canonical(tool.dist): _observe(tool.invocation)}
    found = drifts(declared, observed, (tool,))
    assert found == (), render(found)
