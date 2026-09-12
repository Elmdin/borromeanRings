"""The gate must run the toolchain this repo pins. ADR-0077.

These are the tests that would have caught the 2026-09-10 divergence: two PRs green
on a laptop and red on GitHub because ``pip install -e ".[dev]"`` resolved newer
releases of ``ruff`` and ``mypy`` than the laptop had.
"""

import importlib.metadata as metadata
import re
import subprocess
from pathlib import Path

import pytest
import tomllib

from meta_harness.toolchain import (
    LIBRARY_DECIDERS,
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
# `shellcheck` (from 16_shellcheck, #124) is excluded here on purpose: the
# `shellcheck-py` wheel is versioned 0.11.0.1 while the binary it ships reports
# 0.11.0, so TOOLS (which verifies the RUNNING version against the pin) cannot
# check it — the case the _DIST_OF_BINARY comment below describes. It is pinned
# exactly as `shellcheck-py==` in [dev] and enforced by
# test_every_dev_requirement_is_pinned_exactly, which is the right guarantee for a
# tool whose wheel and binary versions differ.
_NOT_A_DISTRIBUTION = {"python3", "compileall", "timeout", "gtimeout", "shellcheck"}
# Import name → distribution name, where they differ.
_DIST_OF_MODULE = {"pip_audit": "pip-audit"}
# Binary name → distribution name, where they differ. Empty on purpose.
#
# It was briefly pre-seeded with `shellcheck -> shellcheck-py` to smooth an incoming
# merge. Review showed that is wrong, and instructive about why this file exists at all:
# the `shellcheck-py` wheel is versioned 0.11.0.1 while the binary it ships reports
# 0.11.0, so following the assertion's own advice produces a drift on a correctly pinned
# machine. Worse, `command -v shellcheck` finds whichever shellcheck is on PATH — here a
# conda binary, on a runner the image's — which is not the wheel at all, and succeeds
# even when the wheel is absent. That is precisely the shim problem this module exists to
# catch, reintroduced by the fix for it.
#
# So a binary whose reported version is not its distribution's version cannot be verified
# this way, and must not be added here. Give it a check-specific version assertion
# instead.
_DIST_OF_BINARY: dict[str, str] = {}


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
        "differ, read the _DIST_OF_BINARY comment in this file FIRST — a binary whose "
        "reported version differs from its wheel's cannot be verified this way at all."
    )

    orphaned = sorted(known - found)
    assert not orphaned, (
        f"no check appears to invoke {orphaned}, which TOOLS still pins. Check the "
        "scanner BEFORE removing anything: it reads three shell patterns, so a tool "
        "reached through a variable, an alias, or only inside a "
        "`borromeanrings_run_bounded` command string is invisible to it even though the "
        "gate still runs it. Unpinning a live tool is the harmful outcome here. Only if "
        "the check really is gone should the entry and its pin be removed."
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


@pytest.mark.parametrize("dist", LIBRARY_DECIDERS)
def test_the_gate_imports_the_pinned_version_of_each_library(dist: str) -> None:
    """Imported deciders are observed through metadata, not through an argv.

    They were pinned before they were verified: setting any of them to a nonexistent
    9.9.9 used to leave the whole suite green, because the comparison walked only the
    invoked tools. `coverage` measures the ratchet and `libcst` generates the mutants,
    so a silent move in either changes a score with nothing to show for it.
    """
    declared = parse_pins("\n".join(_dev_requirements()))
    try:
        observed: str | None = metadata.version(dist)
    except metadata.PackageNotFoundError:
        observed = None
    found = drifts(declared, {canonical(dist): observed}, (dist,))
    assert found == (), render(found)


@pytest.mark.parametrize("tool", TOOLS, ids=lambda t: t.dist)
def test_the_gate_runs_the_pinned_version_of_each_tool(tool) -> None:  # type: ignore[no-untyped-def]
    """Observed the way the check invokes it — a PATH shim can shadow site-packages."""
    declared = parse_pins("\n".join(_dev_requirements()))
    observed = {canonical(tool.dist): _observe(tool.invocation)}
    found = drifts(declared, observed, (tool.dist,))
    assert found == (), render(found)
