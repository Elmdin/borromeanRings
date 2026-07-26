"""Tamper-evident check receipts.

A receipt records one check's verdict (`check`, `command`, `exit_code`,
`status`, a `log` path, plus any check-specific extras). Casual editing —
flipping `status` to "pass" without recomputing the digest — or accidental
corruption must be DETECTABLE.

This is tamper-EVIDENCE, not tamper-proofing. The digest algorithm is public, so
a knowledgeable local editor could re-forge a receipt, its log, and the digest
together. What it buys, honestly:

  - detects accidental corruption / partial writes;
  - detects naive editing (a script or agent that flips a field but does not
    know, or forgets, to recompute the digest);
  - yields a single per-run digest (`run_digest`) that CI can print into its
    external, append-only log — an anchor a later audit can check the local
    receipts against.

The real trust backstop remains CI, which regenerates receipts from scratch in a
clean environment. See ADR-0026 for the threat model and the promotion path to a
fail-closed integrity gate.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

CONTENT_HASH_FIELD = "content_sha256"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_content_hash(receipt: dict[str, object], log_text: str) -> str:
    """Digest of a receipt's meaningful fields + its log content.

    The receipt's own hash field is excluded, so recomputation over a finalized
    receipt reproduces the stored value (no circularity). Field order does not
    matter (canonical JSON with sorted keys).
    """
    core = {k: v for k, v in receipt.items() if k != CONTENT_HASH_FIELD}
    payload = json.dumps(core, sort_keys=True, separators=(",", ":")) + "\n" + _sha256(log_text)
    return _sha256(payload)


def finalize_receipt(receipt: dict[str, object], log_text: str) -> dict[str, object]:
    """Return a copy of ``receipt`` with its content hash attached."""
    out: dict[str, object] = {k: v for k, v in receipt.items() if k != CONTENT_HASH_FIELD}
    out[CONTENT_HASH_FIELD] = compute_content_hash(out, log_text)
    return out


def verify_receipt(receipt: dict[str, object], log_text: str) -> bool:
    """True iff ``receipt`` carries a hash that matches its fields + ``log_text``."""
    stored = receipt.get(CONTENT_HASH_FIELD)
    if not stored:
        return False
    return stored == compute_content_hash(receipt, log_text)


def run_digest(content_hashes: list[str]) -> str:
    """A single anchor digest over a run's per-receipt hashes (order-independent)."""
    return _sha256("\n".join(sorted(content_hashes)))


@dataclass(frozen=True)
class IntegrityReport:
    ok: bool
    tampered: tuple[str, ...]  # stored hash present but does not match
    unhashed: tuple[str, ...]  # no hash field at all
    missing_log: tuple[str, ...]  # referenced log file is gone
    digest: str  # run_digest over the intact receipts


def verify_dir(receipt_dir: Path) -> IntegrityReport:
    """Verify every ``*.json`` receipt in ``receipt_dir`` against its log."""
    tampered: list[str] = []
    unhashed: list[str] = []
    missing_log: list[str] = []
    intact_hashes: list[str] = []

    for jf in sorted(Path(receipt_dir).glob("*.json")):
        try:
            receipt = json.loads(jf.read_text())
        except (OSError, json.JSONDecodeError):
            tampered.append(jf.stem)
            continue

        log_path = Path(receipt.get("log", ""))
        if not log_path.exists():
            missing_log.append(jf.stem)
            continue
        log_text = log_path.read_text(errors="replace")

        if CONTENT_HASH_FIELD not in receipt:
            unhashed.append(jf.stem)
            continue
        if not verify_receipt(receipt, log_text):
            tampered.append(jf.stem)
            continue
        intact_hashes.append(receipt[CONTENT_HASH_FIELD])

    ok = not (tampered or unhashed or missing_log)
    return IntegrityReport(
        ok=ok,
        tampered=tuple(tampered),
        unhashed=tuple(unhashed),
        missing_log=tuple(missing_log),
        digest=run_digest(intact_hashes),
    )
