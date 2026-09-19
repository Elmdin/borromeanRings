"""What a gate run SHOWED — per-check evidence and the gated intent.

A pass/fail verdict says *that* the gate was satisfied; it does not say *what was shown*.
This module carries the facts a reviewer would otherwise dig out of receipt files: for
each check, the command that ran, its exit code, where its log is and how big it is, and
the receipt's tamper-evident content hash (:mod:`meta_harness.receipts`); plus the
**intent** — which branch, at which commit, over which gated-input digest — read from
git with a fixed argv, never a shell.

Pure data + fail-soft parsing. Old verdict records that predate this carry none of it and
parse to empty defaults; nothing here ever raises on malformed input. The risk band that
is derived from these facts lives with the gate's classifier in
:mod:`meta_harness.verdict`. See docs/specs/SPEC-verdict-evidence.md and ADR-0056.
"""

from __future__ import annotations

import os
import subprocess  # nosec B404 — used only to query git (fixed argv, no shell, no external input)
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

#: Lane labels: the fast inner gate vs the CI-tier heavy set (ADR-0033).
LANE_FAST = "fast"
LANE_HEAVY = "heavy"

#: Exit code recorded when a receipt carries none (or a non-integer). Deliberately not 0:
#: "no exit recorded" must never read as "exited cleanly".
EXIT_NOT_RECORDED = -1


def _int_or(value: object, default: int) -> int:
    # bool is an int subclass; a ``true`` exit code is corrupt, not exit 1.
    return value if isinstance(value, int) and not isinstance(value, bool) else default


@dataclass(frozen=True)
class Evidence:
    """One check's recorded facts: what ran, how it exited, where its proof is."""

    check: str
    command: str = ""
    exit_code: int = EXIT_NOT_RECORDED
    log: str = ""
    log_bytes: int = 0
    content_sha256: str = ""
    lane: str = LANE_FAST

    @property
    def is_heavy(self) -> bool:
        """Was this check required by the CI-tier heavy lane (``verify.sh --heavy``)?"""
        return self.lane == LANE_HEAVY

    def to_dict(self) -> dict[str, object]:
        """A JSON-serialisable view, keys in reading order."""
        return {
            "check": self.check,
            "command": self.command,
            "exit_code": self.exit_code,
            "log": self.log,
            "log_bytes": self.log_bytes,
            "content_sha256": self.content_sha256,
            "lane": self.lane,
        }


def _log_size(log_path: str) -> int:
    try:
        return os.path.getsize(log_path) if log_path else 0
    except OSError:
        return 0


def evidence_from_receipt(receipt: Mapping[str, object], *, lane: str) -> Evidence:
    """Lift a finalized receipt (see ``_lib.sh`` ``emit_receipt``) into :class:`Evidence`.

    Only the evidence fields are copied — check-specific extras (coverage numbers, worst
    function, …) stay in the receipt. The log size is measured on disk now, so the record
    describes the artifact as it existed when the verdict was written.
    """
    log = str(receipt.get("log", ""))
    return Evidence(
        check=str(receipt.get("check", "")),
        command=str(receipt.get("command", "")),
        exit_code=_int_or(receipt.get("exit_code"), EXIT_NOT_RECORDED),
        log=log,
        log_bytes=_log_size(log),
        content_sha256=str(receipt.get("content_sha256", "")),
        lane=lane,
    )


def _parse_one(raw: object) -> Evidence | None:
    if not isinstance(raw, Mapping):
        return None
    check = raw.get("check")
    if not isinstance(check, str):
        return None
    return Evidence(
        check=check,
        command=str(raw.get("command", "")),
        exit_code=_int_or(raw.get("exit_code"), EXIT_NOT_RECORDED),
        log=str(raw.get("log", "")),
        log_bytes=_int_or(raw.get("log_bytes"), 0),
        content_sha256=str(raw.get("content_sha256", "")),
        lane=str(raw.get("lane", LANE_FAST)),
    )


def parse_evidence(raw: object) -> tuple[Evidence, ...]:
    """Decode a persisted ``evidence`` list (fail-soft: bad entries are skipped)."""
    if not isinstance(raw, list):
        return ()
    parsed = (_parse_one(item) for item in raw)
    return tuple(item for item in parsed if item is not None)


@dataclass(frozen=True)
class Intent:
    """What was gated: the branch and commit under review and the gated-input digest.

    ``input_digest`` is :func:`meta_harness.change_detect.compute_state_hash` over the
    gated paths — the same fingerprint the no-op Stop skip trusts — so a verdict can be
    matched to the exact tree it judged.
    """

    branch: str = ""
    head_sha: str = ""
    input_digest: str = ""

    def to_dict(self) -> dict[str, object]:
        """A JSON-serialisable view."""
        return {
            "branch": self.branch,
            "head_sha": self.head_sha,
            "input_digest": self.input_digest,
        }


def parse_intent(raw: object) -> Intent:
    """Decode a persisted ``intent`` object (fail-soft: anything else ⇒ empty)."""
    if not isinstance(raw, Mapping):
        return Intent()
    return Intent(
        branch=str(raw.get("branch", "")),
        head_sha=str(raw.get("head_sha", "")),
        input_digest=str(raw.get("input_digest", "")),
    )


def _git_query(project_root: Path, *args: str) -> str:
    """One read-only git query; ``""`` when git is absent, fails, or this is not a repo."""
    try:
        result = subprocess.run(  # nosec B603 B607 — fixed argv, no shell; only queries git
            ["git", "-C", str(project_root), *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def read_intent(project_root: Path | str, input_digest: str) -> Intent:
    """Read the gated intent from git (branch + head SHA); fail-soft outside a repo."""
    root = Path(project_root)
    return Intent(
        branch=_git_query(root, "rev-parse", "--abbrev-ref", "HEAD"),
        head_sha=_git_query(root, "rev-parse", "HEAD"),
        input_digest=input_digest,
    )
