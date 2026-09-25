"""Adoption planner: upgrade an EXISTING governed project onto newer checks.

``init.sh`` bootstraps a *new* project; adoption plans the migration of an
existing one — which newer checks to add to ``[checks].required`` and which
ratchet baselines to seed from current state so the first gate run is green. A
ratchet added without a baseline is vacuous (its default is "off"); seeded from
the project's current value it holds the line going forward without ever
imposing an arbitrary target (the no-absolute-target principle). Pure planning
plus a scoped TOML rewrite live here; ``adopt.sh`` performs the filesystem
effects. See docs/specs/SPEC-adopt.md and ADR-0041.
"""

from __future__ import annotations

import keyword
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

#: The coverage ratchet's baseline file — one file for every language lane (ADR-0068).
COVERAGE_BASELINE = ".borromeanrings-coverage-baseline"

# Curated, safe-after-seeding quality set — correctness/security/maintainability
# first. Deliberately excludes: collaboration gates (workflow; riskier on an
# existing history — a separate wave), 35_architecture (a no-op until contracts
# are declared), 34_api_diff (library archetype only), and the heavy CI lane
# (expensive; adopted separately once a project runs `verify.sh --heavy`).
RECOMMENDED: tuple[str, ...] = (
    "12_secrets",
    "11_changelog",
    "32_complexity",
    "33_coupling",
    "45_docstrings",
    "01_source_coherence",
    "21_archetype",  # noop until [project].archetypes is declared; then fail-closed
    "19_context_budget",
    "18_api_contracts",
    "17_prior_art",
    "04_self_description",
)

# Recommended checks that are ratchets: each needs a baseline file seeded from
# current state, or it is vacuous. Maps check id -> baseline filename.
RATCHET_BASELINES: dict[str, str] = {
    "32_complexity": ".borromeanrings-complexity-baseline",
    "33_coupling": ".borromeanrings-coupling-baseline",
    "45_docstrings": ".borromeanrings-docstring-baseline",
    "19_context_budget": ".borromeanrings-context-baseline",
}

# Ratchets that measure the project tree itself, not its Python package — seeded
# even when [project].package is unset (the package-bound ones are greenfield-pass).
PACKAGE_FREE_RATCHETS: frozenset[str] = frozenset({"19_context_budget"})


@dataclass(frozen=True)
class AdoptionPlan:
    """The concrete migration for one project: which checks to add, which ratchet
    baselines to seed, whether a changelog must be created, and the resulting
    required set (existing ∪ additions, with the existing order preserved)."""

    add_checks: tuple[str, ...]
    seed_baselines: tuple[str, ...]
    needs_changelog: bool
    new_required: tuple[str, ...]


def plan_adoption(
    current_required: tuple[str, ...],
    has_changelog: bool,
    recommended: tuple[str, ...] = RECOMMENDED,
) -> AdoptionPlan:
    """Plan which recommended checks a project should adopt.

    Idempotent: checks already required are not re-added, so re-running against an
    already-migrated project yields an empty ``add_checks``. Baselines are seeded
    only for ratchet checks being newly added; a changelog is needed only when
    ``11_changelog`` is among the additions and the project has none yet.
    """
    already = set(current_required)
    add = tuple(check for check in recommended if check not in already)
    seed = tuple(check for check in add if check in RATCHET_BASELINES)
    needs_changelog = "11_changelog" in add and not has_changelog
    return AdoptionPlan(
        add_checks=add,
        seed_baselines=seed,
        needs_changelog=needs_changelog,
        new_required=current_required + add,
    )


def rewrite_required(toml_text: str, new_required: tuple[str, ...]) -> str:
    """Return ``toml_text`` with ``[checks].required`` replaced by ``new_required``,
    preserving every other line (comments included).

    The rewrite is scoped to the ``[checks]`` table, so an unrelated ``required``
    key under another table is left untouched. Fail-closed: a missing table or a
    missing ``required`` array raises :class:`ValueError` rather than silently
    appending a malformed section.
    """
    header = re.search(r"(?m)^\[checks\][ \t]*$", toml_text)
    if header is None:
        raise ValueError("no [checks] table to update")
    start = header.end()
    following = re.search(r"(?m)^\[", toml_text[start:])
    end = start + following.start() if following else len(toml_text)
    section = toml_text[start:end]
    array = re.search(r"(?ms)^([ \t]*)required[ \t]*=[ \t]*\[.*?\]", section)
    if array is None:
        raise ValueError("no required array in [checks] to rewrite")
    rendered = (
        array.group(1) + "required = [" + ", ".join(f'"{check}"' for check in new_required) + "]"
    )
    section = section[: array.start()] + rendered + section[array.end() :]
    return toml_text[:start] + section + toml_text[end:]


def infer_package(src_root: Path | str) -> str:
    """The importable package under ``src_root``, or ``""`` when it cannot be told.

    ``[project].package`` is what every check that measures the project's own code keys
    on. Left empty — which is what ``init.sh`` used to write — `32_complexity`,
    `33_coupling` and `45_docstrings` report "no package/source to measure (greenfield)"
    about a project full of modules, while the gate still says PASS (audit of
    2026-09-20). It is a value the layout already answers, so it is read rather than
    asked for: exactly one directory holding an ``__init__.py``. Two candidates, or none,
    means the project must say which, and the empty string is then honest.
    """
    root = Path(src_root)
    if not root.is_dir():
        return ""
    packages = sorted(
        child.name
        for child in root.iterdir()
        if child.is_dir()
        and (child / "__init__.py").is_file()
        # Only a name that is an importable identifier, because this value is written
        # into the config and from there into `python3 -c "import <package>"`. A
        # directory called `pkg"; whoami; #` must never be offered as one (review of
        # #261); the spine refuses it too, and refusing twice is the point.
        and child.name.isidentifier()
        and not keyword.iskeyword(child.name)
    )
    return packages[0] if len(packages) == 1 else ""


def coverage_seed(receipts: Sequence[Mapping[str, object]]) -> str | None:
    """The value to seed :data:`COVERAGE_BASELINE` with, from past ``40_test`` receipts.

    Adoption never runs a language's test tool itself (no installs, no surprises), so the
    only honest source for a coverage baseline is a coverage number the gate already
    measured. ``receipts`` is oldest-first; the LATEST receipt that carries a numeric
    ``coverage_percent`` wins (a ``noop`` run carries none). ``None`` when no run has
    measured coverage yet — the caller says to run the gate first rather than seeding 0.
    """
    for receipt in reversed(receipts):
        value = receipt.get("coverage_percent")
        if isinstance(value, int | float) and not isinstance(value, bool):
            # Full precision, deliberately. `:g` rounds to six significant digits, and
            # 40_test compares the measurement it takes now against this number with a
            # 1e-9 epsilon — so a rounded baseline is a baseline the project's own
            # unchanged coverage sits below. That is what produced
            # "COVERAGE REGRESSION: 97.37% is below baseline 97.37%" on the first run
            # after adopting (audit of 2026-09-20).
            return repr(float(value))
    return None
