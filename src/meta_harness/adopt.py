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

import re
from dataclasses import dataclass

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
    "18_api_contracts",
)

# Recommended checks that are ratchets: each needs a baseline file seeded from
# current state, or it is vacuous. Maps check id -> baseline filename.
RATCHET_BASELINES: dict[str, str] = {
    "32_complexity": ".borromeanrings-complexity-baseline",
    "33_coupling": ".borromeanrings-coupling-baseline",
    "45_docstrings": ".borromeanrings-docstring-baseline",
}


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
