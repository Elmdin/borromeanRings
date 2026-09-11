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
from dataclasses import dataclass
from pathlib import Path

#: Where the compact verdict lives, relative to the governed project root.
LAST_VERDICT_FILE = ".meta-harness/last_verdict.json"
#: Append-only history of every gate verdict (one JSON object per line) — the raw
#: material the effectiveness ledger summarises. See meta_harness.ledger, ADR-0047.
VERDICT_HISTORY_FILE = ".meta-harness/verdict_history.jsonl"

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


@dataclass(frozen=True)
class Verdict:
    """One gate run's outcome: the overall pass bool and each check's status.

    ``harness_version`` records *which* borromeanRings governed the run (the on-disk
    ``git describe`` of ``BORROMEANRINGS_HOME``, or the ``VERSION`` file) — so a governed
    project's evidence answers "what version verified me?", not just "did it pass?".
    Absent in records written before versioning ⇒ defaults to ``""`` (back-compatible).

    ``generator`` records *who* produced the change the run judged — the self-declared
    ``<kind>:<id>`` label the adapter running the gate exported (``claude-code:<session>``
    from the Stop hook, ``headless:<command>`` from ``generate.sh``). It is persisted
    under ``intent``, the home ADR-0056 gives the gated *what* (branch, head, digest), so
    the two land in one object once both are in the tree. Provenance, never evidence: the
    gate makes no decision on it, absent reads ``""``, and nothing here can loosen ``ok``
    (ADR-0071 §4, ADR-0049).
    """

    ok: bool
    checks: tuple[tuple[str, str], ...] = ()
    run_id: str = ""
    digest: str = ""
    harness_version: str = ""
    generator: str = ""

    def to_dict(self) -> dict[str, object]:
        """A JSON-serialisable view (tuples become lists)."""
        return {
            "ok": self.ok,
            "run_id": self.run_id,
            "digest": self.digest,
            "harness_version": self.harness_version,
            "intent": {"generator": self.generator},
            "checks": [list(pair) for pair in self.checks],
        }


def _parse_generator(raw: object) -> str:
    """The ``intent.generator`` label from a persisted record; anything else ⇒ ``""``.

    Fail-soft in both directions: a record written before the field existed, and a record
    whose ``intent`` is not an object carrying a string, both read as "no generator
    recorded". Never a guess — an unattributed run says so.
    """
    if not isinstance(raw, dict):
        return ""
    value = raw.get("generator")
    return value if isinstance(value, str) else ""


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
        generator=_parse_generator(data.get("intent")),
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
