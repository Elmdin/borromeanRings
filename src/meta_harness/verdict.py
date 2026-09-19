"""Persisted gate verdicts — the last-known health signal a portfolio view reads.

The gate (``verify.sh``) computes a fail-closed verdict from receipts on every run,
but historically kept nothing durable beyond the per-check receipts and the
``last_green_state`` hash (:mod:`meta_harness.change_detect`). A cross-project status
view (:mod:`meta_harness.status`) needs one compact, readable answer per project:
*did the last gate pass, and on which checks?*

This module defines that record and its read/write. Written best-effort by the gate
(a write failure must never turn a real PASS into a FAIL) into the governed project's
evidence area (``.meta-harness/``, git-ignored — same home as receipts). Reads are
fail-soft: a missing, unreadable, or malformed record yields ``None``, never an
exception — a status view must degrade one row, not crash. This is a *last-known*
signal, not a re-verification; ``status --run`` re-gates for freshness. See
docs/specs/SPEC-status.md and ADR-0046.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from meta_harness.evidence import Evidence, Intent, parse_evidence, parse_intent

#: Where the compact verdict lives, relative to the governed project root.
LAST_VERDICT_FILE = ".meta-harness/last_verdict.json"
#: Append-only history of every gate verdict (one JSON object per line) — the raw
#: material the effectiveness ledger summarises. See meta_harness.ledger, ADR-0047.
VERDICT_HISTORY_FILE = ".meta-harness/verdict_history.jsonl"
#: Append-only record of the prompt-rewrite contract, one verdict per Stop: did the reply
#: open with the line the UserPromptSubmit directive asked for? Decided by
#: meta_harness.rewrite_contract; tallied by the self-status view. See ADR-0059 (#81).
REWRITE_CONTRACT_FILE = ".meta-harness/rewrite_contract.jsonl"
#: The rewrite-contract verdict vocabulary. ``honoured``/``not_honoured`` are judged
#: outcomes; ``exempt`` (trivial prompt) and ``unknown`` (no evidence) are not, and a
#: record carrying any other status is counted as ``unknown`` — never as honoured.
REWRITE_STATUSES = ("honoured", "not_honoured", "exempt", "unknown")
#: Append-only record of the self-report contract, one verdict per Stop: did the reply end
#: with the structural VERIFICATION STATUS block, and was it free of confidence grades?
#: Decided by meta_harness.self_report; tallied by the self-status view. See ADR-0066 (#176).
SELF_REPORT_FILE = ".meta-harness/self_report.jsonl"
#: The self-report verdict vocabulary. ``present``/``absent``/``malformed``/``graded`` are
#: judged outcomes; ``exempt`` (trivial prompt) and ``unknown`` (no evidence) are not, and
#: a record carrying any other status counts as ``unknown`` — never as present.
SELF_REPORT_STATUSES = ("present", "absent", "malformed", "graded", "exempt", "unknown")

#: Receipt statuses that do NOT fail the gate.
#:
#: An explicit allowlist, deliberately never a negation. ``noop`` (the check ran but had
#: nothing to inspect) has to be non-failing, and the moment a second non-failing value
#: exists, the old ``status != "pass"`` test becomes a hole: any unknown, misspelled, or
#: forged status would sail through. Matching is exact — no case folding, no stripping —
#: so anything that is not precisely a known-good value fails closed. See ADR-0049.
NON_FAILING_STATUSES = frozenset({"pass", "noop"})


def is_failing(status: str) -> bool:
    """Does this receipt status fail the run? Fail-closed: unknown ⇒ ``True``.

    The single source of truth for the gate's pass/fail classification, so ``verify.sh``
    and every downstream view agree on what a status means.
    """
    return status not in NON_FAILING_STATUSES


#: Longest ``summary`` the gate prints on a row; anything longer is cut with ``...``.
SUMMARY_MAX_CHARS = 72


def status_label(status: str, summary: object = None) -> str:
    """The gate-output text for one check row: ``STATUS``, plus ``(summary)`` if present.

    Any check may write a free-text ``summary`` field into its receipt (``60_mutation``
    writes ``evaluated N, score S``); the gate prints it beside the status so the row
    answers "did the check do real work?" without a trip to the log. The field is
    untrusted JSON a check wrote, so it is validated here: non-strings and blanks are
    ignored, only the first line is used, and it is bounded so the table stays a table.
    """
    label = status.upper()
    if not isinstance(summary, str):
        return label
    first_line = summary.strip().splitlines()[0].strip() if summary.strip() else ""
    if not first_line:
        return label
    if len(first_line) > SUMMARY_MAX_CHARS:
        first_line = first_line[: SUMMARY_MAX_CHARS - 3] + "..."
    return f"{label} ({first_line})"


#: Risk bands, categorical and derived from recorded facts only (ADR-0056). They allocate
#: HUMAN review attention; no band ever relaxes a machine gate (which stays fail-closed).
RISK_GREEN = "green"  # every check passed for real
RISK_HOLLOW = "hollow"  # non-failing, but at least one check inspected nothing
RISK_RED = "red"  # at least one check failed (or was missing/tampered/unknown)
RISK_BANDS: tuple[str, ...] = (RISK_GREEN, RISK_HOLLOW, RISK_RED)


def risk_band(checks: Iterable[tuple[str, str]]) -> str:
    """The band a run's recorded check statuses put it in. Red > hollow > green.

    Deterministic and threshold-free: a failure of any kind is red (never softened by a
    hollow sibling); a run that inspected nothing anywhere — including one with no
    checks at all — is hollow, because "nothing looked" cannot be green.
    """
    statuses = [status for _, status in checks]
    if any(is_failing(status) for status in statuses):
        return RISK_RED
    if not statuses or any(status == "noop" for status in statuses):
        return RISK_HOLLOW
    return RISK_GREEN


@dataclass(frozen=True)
class Verdict:
    """One gate run's outcome: the overall pass bool and each check's status.

    ``harness_version`` records *which* borromeanRings governed the run (the on-disk
    ``git describe`` of ``BORROMEANRINGS_HOME``, or the ``VERSION`` file) — so a governed
    project's evidence answers "what version verified me?", not just "did it pass?".
    Absent in records written before versioning ⇒ defaults to ``""`` (back-compatible).

    ``risk``, ``intent`` and ``evidence`` (ADR-0056) record what was SHOWN to happen:
    the categorical band from :func:`risk_band`, the branch/commit/input digest that was
    gated, and each check's :class:`~meta_harness.evidence.Evidence`. Records written
    before this carry none of it and read back as ``""`` / empty — a missing band is
    reported as *not recorded*, never re-derived into a claim the record did not make.
    ``intent.generator`` records *who* produced the change the run judged — the
    self-declared ``<kind>:<id>`` label the adapter running the gate exported
    (ADR-0078). Provenance, never evidence: the gate makes no decision on it, absent
    reads ``""``, and nothing here can loosen ``ok`` (ADR-0071 §4, ADR-0049).
    """

    ok: bool
    checks: tuple[tuple[str, str], ...] = ()
    run_id: str = ""
    digest: str = ""
    harness_version: str = ""
    risk: str = ""
    intent: Intent = Intent()
    evidence: tuple[Evidence, ...] = ()
    #: Which lane produced it — ``"full"`` (or ``""`` in records written before lanes
    #: existed) for a complete run, ``"fast"`` for the narrowed interactive run the Stop
    #: hook makes. A reader must be able to tell a partial green from a real one, so the
    #: lane is part of the record, not only of the console output. See ADR-0081.
    lane: str = ""

    def to_dict(self) -> dict[str, object]:
        """A JSON-serialisable view (tuples become lists; nested records become objects)."""
        return {
            "ok": self.ok,
            "run_id": self.run_id,
            "digest": self.digest,
            "harness_version": self.harness_version,
            "risk": self.risk,
            "intent": self.intent.to_dict(),
            "lane": self.lane,
            "checks": [list(pair) for pair in self.checks],
            "evidence": [item.to_dict() for item in self.evidence],
        }


def advisory_failures(receipt_dir: Path | str, expected: Iterable[str]) -> tuple[str, ...]:
    """``"<check> (<status>)"`` for each failing receipt OUTSIDE the expected set.

    Every check in a lane runs; only the expected set decides the verdict. A check
    outside it that fails still writes its ``fail`` receipt, and a failure the run dir
    records but the verdict never mentions is the hollow shape in the reporting layer
    (#229). The gate prints these as advisory; they never change ``ok``.

    The run dir's JSON is untrusted: anything that is not an object naming its own file
    as its ``check`` (a list, a string, a scratch file, an unreadable one) is skipped,
    never raised on.
    """
    wanted = set(expected)
    found: list[str] = []
    for path in sorted(Path(receipt_dir).glob("*.json")):
        if path.stem in wanted:
            continue
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(receipt, dict) or receipt.get("check") != path.stem:
            continue
        status = receipt.get("status")
        if isinstance(status, str) and is_failing(status):
            found.append(f"{path.stem} ({status})")
    return tuple(found)


def _parse(data: object) -> Verdict | None:
    """Validate a decoded JSON value into a :class:`Verdict`, or ``None`` if malformed."""
    if not isinstance(data, dict):
        return None
    ok = data.get("ok")
    if not isinstance(ok, bool):
        return None
    raw_checks = data.get("checks", [])
    if not isinstance(raw_checks, list):
        return None
    checks = tuple(
        (str(pair[0]), str(pair[1]))
        for pair in raw_checks
        if isinstance(pair, (list, tuple)) and len(pair) == 2
    )
    return Verdict(
        ok=ok,
        checks=checks,
        run_id=str(data.get("run_id", "")),
        digest=str(data.get("digest", "")),
        harness_version=str(data.get("harness_version", "")),
        risk=str(data.get("risk", "")),
        intent=parse_intent(data.get("intent")),
        evidence=parse_evidence(data.get("evidence")),
        lane=str(data.get("lane", "")),
    )


def _path(project_root: Path | str) -> Path:
    return Path(project_root) / LAST_VERDICT_FILE


def write_last_verdict(project_root: Path | str, verdict: Verdict) -> None:
    """Persist ``verdict`` as the project's last-known gate outcome (creates dirs).

    Written atomically (temp file + ``replace``) so a concurrent reader or a crash
    mid-write never observes a truncated record — it sees the old one or the new one.
    """
    path = _path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(verdict.to_dict(), indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_last_verdict(project_root: Path | str) -> Verdict | None:
    """The last persisted verdict, or ``None`` if absent/unreadable/malformed."""
    try:
        raw = _path(project_root).read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return _parse(data)


def _history_path(project_root: Path | str) -> Path:
    return Path(project_root) / VERDICT_HISTORY_FILE


def append_history(project_root: Path | str, verdict: Verdict) -> None:
    """Append ``verdict`` as one JSON line to the project's gate-history log (creates dirs)."""
    path = _history_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(verdict.to_dict()) + "\n")


def read_history(project_root: Path | str) -> list[Verdict]:
    """Every recorded verdict for the project, oldest first (fail-soft, skips bad lines)."""
    try:
        raw = _history_path(project_root).read_text(encoding="utf-8")
    except OSError:
        return []
    history: list[Verdict] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        verdict = _parse(data)
        if verdict is not None:
            history.append(verdict)
    return history


# --- rewrite-contract records (ADR-0059) -------------------------------------------------


@dataclass(frozen=True)
class RewriteTally:
    """How often the rewrite contract was honoured in this project, from its record."""

    honoured: int = 0
    not_honoured: int = 0
    exempt: int = 0
    unknown: int = 0

    @property
    def judged(self) -> int:
        """Records that carry evidence either way (exempt and unknown do not)."""
        return self.honoured + self.not_honoured

    @property
    def total(self) -> int:
        """Every record, whatever its status."""
        return self.judged + self.exempt + self.unknown


def _rewrite_path(project_root: Path | str) -> Path:
    return Path(project_root) / REWRITE_CONTRACT_FILE


def append_rewrite_record(project_root: Path | str, rec: Mapping[str, object]) -> None:
    """Append one rewrite-contract record as a JSON line (creates dirs; append-only)."""
    path = _rewrite_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(rec)) + "\n")


def _count_statuses(path: Path, statuses: Sequence[str]) -> dict[str, int]:
    """Count the ``status`` of every well-formed record line in ``path``.

    Fail-soft: an unreadable file is all zeros. A malformed line is skipped; a well-formed
    record with an unrecognised status counts as ``unknown`` (fail-closed: it is never
    evidence for the contract).
    """
    counts = dict.fromkeys(statuses, 0)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return counts
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        status = data.get("status")
        counts[status if status in counts else "unknown"] += 1
    return counts


def read_rewrite_tally(project_root: Path | str) -> RewriteTally:
    """Tally the project's rewrite-contract record (see :func:`_count_statuses`)."""
    return RewriteTally(**_count_statuses(_rewrite_path(project_root), REWRITE_STATUSES))


# --- self-report records (ADR-0066) ------------------------------------------------------


@dataclass(frozen=True)
class SelfReportTally:
    """How often replies carried the structural VERIFICATION STATUS block, from the record."""

    present: int = 0
    absent: int = 0
    malformed: int = 0
    graded: int = 0
    exempt: int = 0
    unknown: int = 0

    @property
    def judged(self) -> int:
        """Records that carry evidence either way (exempt and unknown do not)."""
        return self.present + self.absent + self.malformed + self.graded

    @property
    def total(self) -> int:
        """Every record, whatever its status."""
        return self.judged + self.exempt + self.unknown


def _self_report_path(project_root: Path | str) -> Path:
    return Path(project_root) / SELF_REPORT_FILE


def append_self_report_record(project_root: Path | str, rec: Mapping[str, object]) -> None:
    """Append one self-report record as a JSON line (creates dirs; append-only)."""
    path = _self_report_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(rec)) + "\n")


def read_self_report_tally(project_root: Path | str) -> SelfReportTally:
    """Tally the project's self-report record (see :func:`_count_statuses`)."""
    counts = _count_statuses(_self_report_path(project_root), SELF_REPORT_STATUSES)
    return SelfReportTally(**counts)
