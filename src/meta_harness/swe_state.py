"""SWE-state report — what ONE governed project practises, lacks, and should adopt next.

``status.sh`` says whether the gate is green; ``ledger.sh`` says whether it caught
anything. Neither says what the project *should* be doing that it is not. This module
answers that from facts already on disk — the spine's required set, the last verdict,
the archetype evaluation, ``adopt.py``'s recommended set and the governance matrices'
*Enforced by* column — and renders three categorical sections plus the sources each
line came from. **No score, no percentage, no ranking** beyond one fixed adoption order
(fail-closed gaps, then ratchets without a baseline, then RECOMMENDED not adopted, then
archetype features absent). Honest where it cannot tell: ``unknown``, ``unreadable``,
``no matrices on disk`` — never a guess (#139, ADR-0067).

Pure: :func:`assess` takes already-read facts; :func:`parse_matrices` takes text.
``swe-state.sh`` is the composition root that reads the files. Fan-out is held at the
coupling baseline: adoption vocabulary from :mod:`meta_harness.adopt`, the pass/fail
classification from :mod:`meta_harness.verdict`; archetype results cross the seam as
plain :class:`FeatureFact` values. See docs/specs/SPEC-swe-state.md.
"""

from __future__ import annotations

import json
import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import asdict, dataclass

from meta_harness.adopt import RATCHET_BASELINES, plan_adoption
from meta_harness.verdict import Verdict, is_failing

#: Status the report gives a check the last verdict says nothing about.
UNKNOWN = "unknown"
_NOOP = "noop"
_CHECK_ID_RE = re.compile(r"\b(\d{2}_[a-z][a-z0-9_]*)\b")
_GAP_RE = re.compile(r"gap\s*→\s*(#\d+)")
_ROW_ID_RE = re.compile(r"^[A-Z]{1,2}\d+$")


@dataclass(frozen=True)
class CheckState:
    """One required check and what the last verdict recorded for it (or ``unknown``)."""

    check: str
    status: str


@dataclass(frozen=True)
class FeatureFact:
    """One archetype feature's verdict, carried across the seam as data (no import)."""

    feature_id: str
    title: str
    present: bool
    source: str


@dataclass(frozen=True)
class MatrixRow:
    """One governance-matrix row as parsed from its document (``Enforced by`` decoded)."""

    matrix: str
    row: str
    criterion: str
    enforced_by: str
    checks: tuple[str, ...]
    gap: str


@dataclass(frozen=True)
class RowState:
    """A matrix row's standing for this project: ``gap`` / ``lacking`` / ``not_adopted``."""

    row: str
    state: str
    detail: str


@dataclass(frozen=True)
class Adoption:
    """One item of the adopt-next list: its kind (the ordering key), subject and reason."""

    kind: str
    subject: str
    reason: str


@dataclass(frozen=True)
class Practises:
    """What the project demonstrably does, per the last verdict and the working tree."""

    checks: tuple[str, ...]
    features: tuple[FeatureFact, ...]
    matrix_rows: tuple[str, ...]


@dataclass(frozen=True)
class Lacks:
    """What the project does not do, each with the vocabulary that names it."""

    checks: tuple[CheckState, ...]
    recommended: tuple[str, ...]
    ratchets_without_baseline: tuple[str, ...]
    features: tuple[FeatureFact, ...]
    matrix_gaps: tuple[RowState, ...]
    matrix_unmet: tuple[RowState, ...]


@dataclass(frozen=True)
class Sources:
    """Where each section's facts came from, one line per input (auditability)."""

    config: str
    verdict: str
    archetypes: str
    matrices: str


@dataclass(frozen=True)
class SweState:
    """The whole report for one project."""

    project: str
    gated: bool
    archetypes: tuple[str, ...]
    unreadable: tuple[str, ...]
    checks: tuple[CheckState, ...]
    matrices_on_disk: bool
    practises: Practises
    lacks: Lacks
    adopt_next: tuple[Adoption, ...]
    matrix_undecidable: tuple[str, ...]
    sources: Sources


# --- matrices ---------------------------------------------------------------------------------


def _parse_row(matrix: str, line: str) -> MatrixRow | None:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    if len(cells) < 3 or not _ROW_ID_RE.match(cells[0]):
        return None
    enforced_by = cells[2]
    checks = tuple(dict.fromkeys(_CHECK_ID_RE.findall(enforced_by)))
    gap = _GAP_RE.search(enforced_by)
    return MatrixRow(matrix, cells[0], cells[1], enforced_by, checks, gap.group(1) if gap else "")


def parse_matrices(texts: Mapping[str, str]) -> tuple[MatrixRow, ...]:
    """Every ``| Sn | criterion | enforced by | … |`` row of the given documents.

    Files are taken in name order (``02-…`` before ``03-…``), rows in document order, so
    the report is deterministic. Header, separator and prose lines are skipped.
    """
    rows: list[MatrixRow] = []
    for name in sorted(texts):
        for line in texts[name].splitlines():
            if line.startswith("|"):
                row = _parse_row(name, line)
                if row is not None:
                    rows.append(row)
    return tuple(rows)


# --- assessment -------------------------------------------------------------------------------


def _check_states(required: Sequence[str], verdict: Verdict | None) -> tuple[CheckState, ...]:
    recorded = dict(verdict.checks) if verdict is not None else {}
    return tuple(CheckState(check, recorded.get(check, UNKNOWN)) for check in required)


def _is_lacking(status: str) -> bool:
    return status != UNKNOWN and (status == _NOOP or is_failing(status))


def _check_standing(row: MatrixRow, statuses: Mapping[str, str]) -> RowState | str | None:
    """The standing of a gated row that names checks (see :func:`_classify_row`)."""
    failing = [
        f"{c}: {statuses[c]}" for c in row.checks if c in statuses and _is_lacking(statuses[c])
    ]
    if failing:
        return RowState(row.row, "lacking", ", ".join(failing))
    if any(statuses.get(c) == UNKNOWN for c in row.checks):
        return None  # required here but absent from the last verdict (e.g. a heavy check)
    absent = [f"{c}: not adopted" for c in row.checks if c not in statuses]
    if absent:
        return RowState(row.row, "not_adopted", ", ".join(absent))
    return "enforced"


def _classify_row(
    row: MatrixRow, gated: bool, statuses: Mapping[str, str]
) -> RowState | str | None:
    """A row's standing: a ``RowState`` (gap / lacking / not_adopted), ``"enforced"``,
    ``"undecidable"``, or ``None`` when unknowable (never gated, or a named check is
    required here but the last verdict says nothing about it)."""
    if row.gap:
        return RowState(row.row, "gap", f"→ {row.gap}")
    if not row.checks:
        return "undecidable"
    return _check_standing(row, statuses) if gated else None


@dataclass(frozen=True)
class _MatrixStanding:
    """Every matrix row sorted into its bucket for one project."""

    enforced: tuple[str, ...]
    undecidable: tuple[str, ...]
    gaps: tuple[RowState, ...]
    unmet: tuple[RowState, ...]


def _matrix_standing(
    rows: Sequence[MatrixRow], gated: bool, statuses: Mapping[str, str]
) -> _MatrixStanding:
    enforced: list[str] = []
    undecidable: list[str] = []
    gaps: list[RowState] = []
    unmet: list[RowState] = []
    for row in rows:
        standing = _classify_row(row, gated, statuses)
        if standing == "enforced":
            enforced.append(row.row)
        elif standing == "undecidable":
            undecidable.append(row.row)
        elif isinstance(standing, RowState):
            (gaps if standing.state == "gap" else unmet).append(standing)
    return _MatrixStanding(tuple(enforced), tuple(undecidable), tuple(gaps), tuple(unmet))


def _adopt_next(
    lacking: Sequence[CheckState],
    ratchets: Sequence[str],
    recommended: Sequence[str],
    features: Sequence[FeatureFact],
) -> tuple[Adoption, ...]:
    """The fixed order: failing gates, noop gates, baselines, recommended, features."""
    gate = [
        Adoption(
            "gate",
            c.check,
            f"last reported {c.status}; the gate is fail-closed: fix the finding",
        )
        for c in lacking
        if c.status != _NOOP
    ] + [
        Adoption(
            "gate",
            c.check,
            "last reported noop; it inspected nothing: point it at something or drop it",
        )
        for c in lacking
        if c.status == _NOOP
    ]
    baseline = [
        Adoption("baseline", c, f"seed {RATCHET_BASELINES[c]} from current state (adopt.sh)")
        for c in ratchets
    ]
    checks = [
        Adoption("check", c, "recommended by adopt.sh; add to [checks].required")
        for c in recommended
    ]
    absent = [Adoption("feature", f.feature_id, f"{f.title} ({f.source})") for f in features]
    return tuple(gate + baseline + checks + absent)


def _verdict_source(verdict: Verdict | None, unreadable: Collection[str]) -> str:
    if verdict is not None:
        outcome = "PASS" if verdict.ok else "FAIL"
        version = verdict.harness_version or UNKNOWN
        return (
            f".meta-harness/last_verdict.json — run {verdict.run_id} {outcome}"
            f" by borromeanRings {version}"
        )
    if "verdict" in unreadable:
        return ".meta-harness/last_verdict.json — unreadable"
    return "never gated"


def _archetype_source(archetypes: Sequence[str], unreadable: Collection[str]) -> str:
    names = ", ".join(archetypes)
    if "config" in unreadable:
        return "unreadable — borromeanrings.toml"
    if "archetypes" in unreadable:
        return f"{names} — unreadable (archetype evaluation failed)"
    return f"{names} — meta_harness.archetypes catalog" if archetypes else "none declared"


def _matrix_source(
    matrix_rows: Sequence[MatrixRow] | None, undecidable: Sequence[str], unreadable: Collection[str]
) -> str:
    if "matrices" in unreadable:
        return "unreadable"
    if matrix_rows is None:
        return "no matrices on disk"
    files = len({row.matrix for row in matrix_rows})
    text = f"{len(matrix_rows)} row(s) from {files} matrix file(s)"
    if undecidable:
        text += "; undecidable from receipts: " + ", ".join(undecidable)
    return text


def _sources(
    *,
    required: Sequence[str],
    verdict: Verdict | None,
    archetypes: Sequence[str],
    matrix_rows: Sequence[MatrixRow] | None,
    undecidable: Sequence[str],
    unreadable: Collection[str],
) -> Sources:
    config = (
        "borromeanrings.toml — unreadable"
        if "config" in unreadable
        else f"borromeanrings.toml — {len(required)} check(s) required"
    )
    return Sources(
        config,
        _verdict_source(verdict, unreadable),
        _archetype_source(archetypes, unreadable),
        _matrix_source(matrix_rows, undecidable, unreadable),
    )


def assess(
    *,
    project: str,
    required: Sequence[str],
    verdict: Verdict | None,
    archetypes: Sequence[str],
    features: Sequence[FeatureFact],
    has_changelog: bool,
    baseline_files_present: Collection[str],
    matrix_rows: Sequence[MatrixRow] | None,
    unreadable: Sequence[str] = (),
) -> SweState:
    """Decide the three sections from already-read facts (pure; see SPEC-swe-state.md §4).

    ``matrix_rows`` is ``None`` when no matrices are on disk. ``unreadable`` names the
    inputs that existed but could not be read (``config``, ``verdict``, ``archetypes``,
    ``matrices``); their sections say so and the rest still renders.
    """
    gated = verdict is not None
    checks = _check_states(required, verdict)
    statuses = {c.check: c.status for c in checks}
    lacking = tuple(c for c in checks if _is_lacking(c.status))
    recommended = (
        ()
        if "config" in unreadable
        else plan_adoption(tuple(required), has_changelog=has_changelog).add_checks
    )
    ratchets = tuple(
        c
        for c in required
        if c in RATCHET_BASELINES and RATCHET_BASELINES[c] not in baseline_files_present
    )
    matrix = _matrix_standing(matrix_rows or (), gated, statuses)
    present = tuple(f for f in features if f.present)
    absent = tuple(f for f in features if not f.present)
    return SweState(
        project=project,
        gated=gated,
        archetypes=tuple(archetypes),
        unreadable=tuple(unreadable),
        checks=checks,
        matrices_on_disk=matrix_rows is not None,
        practises=Practises(
            tuple(c.check for c in checks if c.status == "pass"), present, matrix.enforced
        ),
        lacks=Lacks(lacking, recommended, ratchets, absent, matrix.gaps, matrix.unmet),
        adopt_next=_adopt_next(lacking, ratchets, recommended, absent),
        matrix_undecidable=matrix.undecidable,
        sources=_sources(
            required=required,
            verdict=verdict,
            archetypes=archetypes,
            matrix_rows=matrix_rows,
            undecidable=matrix.undecidable,
            unreadable=unreadable,
        ),
    )


# --- rendering --------------------------------------------------------------------------------


def _join(items: Sequence[str], fallback: str = "") -> str:
    return fallback or (", ".join(items) if items else "none")


def _check_reason(state: SweState) -> str:
    """Why check-derived lines cannot be decided, or ``""`` when they can."""
    if "config" in state.unreadable:
        return "unreadable — borromeanrings.toml"
    if "verdict" in state.unreadable:
        return "unknown — last_verdict.json unreadable"
    return "" if state.gated else "unknown — never gated"


def _matrix_reason(state: SweState, checks_needed: bool) -> str:
    if "matrices" in state.unreadable:
        return "unreadable"
    if not state.matrices_on_disk:
        return "no matrices on disk"
    return _check_reason(state) if checks_needed else ""


def _feature_reason(state: SweState) -> str:
    if "config" in state.unreadable:
        return "unreadable — borromeanrings.toml"
    if "archetypes" in state.unreadable:
        return "unreadable — archetype evaluation failed"
    return "" if state.archetypes else "no archetypes declared"


def _config_reason(state: SweState) -> str:
    return "unreadable — borromeanrings.toml" if "config" in state.unreadable else ""


def _practises_lines(state: SweState) -> list[str]:
    names = f" ({', '.join(state.archetypes)})" if state.archetypes else ""
    p = state.practises
    return [
        "Practises",
        f"  checks (required, last reported pass): {_join(p.checks, _check_reason(state))}",
        "  checks unknown (not in the last verdict): "
        + _join([c.check for c in state.checks if c.status == UNKNOWN], _config_reason(state)),
        f"  archetype features present{names}: "
        f"{_join([f.feature_id for f in p.features], _feature_reason(state))}",
        f"  matrix rows enforced: {_join(p.matrix_rows, _matrix_reason(state, True))}",
    ]


def _lacks_lines(state: SweState) -> list[str]:
    lacks = state.lacks
    return [
        "Lacks",
        "  checks required but last reported noop/fail: "
        + _join([f"{c.check} ({c.status})" for c in lacks.checks], _check_reason(state)),
        f"  recommended by adopt.sh, not required: "
        f"{_join(lacks.recommended, _config_reason(state))}",
        "  ratchets without a baseline: "
        + _join(lacks.ratchets_without_baseline, _config_reason(state)),
        "  archetype features absent: "
        + _join([f"{f.feature_id} — {f.title}" for f in lacks.features], _feature_reason(state)),
        "  matrix rows at a gap: "
        + _join([f"{r.row} ({r.detail})" for r in lacks.matrix_gaps], _matrix_reason(state, False)),
        "  matrix rows unmet here: "
        + _join([f"{r.row} ({r.detail})" for r in lacks.matrix_unmet], _matrix_reason(state, True)),
    ]


def _adopt_lines(state: SweState) -> list[str]:
    lines = ["Adopt next"]
    for n, item in enumerate(state.adopt_next, start=1):
        lines.append(f"  {n}. {f'[{item.kind}]':<10} {item.subject} — {item.reason}")
    if not state.adopt_next:
        lines.append("  (nothing to adopt)")
    return lines


def render(state: SweState) -> str:
    """The report as sectioned plain text (Practises / Lacks / Adopt next / Sources)."""
    name = state.project.rstrip("/").rsplit("/", maxsplit=1)[-1]
    s = state.sources
    sections = [
        [f"SWE state — {name}"],
        _practises_lines(state),
        _lacks_lines(state),
        _adopt_lines(state),
        [
            "Sources",
            f"  config:     {s.config}",
            f"  verdict:    {s.verdict}",
            f"  archetypes: {s.archetypes}",
            f"  matrices:   {s.matrices}",
            "  ordering:   fixed — gate gaps, then baselines, then recommended, then features;"
            " no score, no ranking",
        ],
    ]
    return "\n\n".join("\n".join(lines) for lines in sections) + "\n"


def to_json(state: SweState) -> str:
    """The report as JSON (``asdict``; tuples become lists)."""
    return json.dumps(asdict(state), indent=2, ensure_ascii=False) + "\n"
