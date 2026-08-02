"""Git-history secret scanning.

``12_secrets`` scans the *current* tracked files; but a secret that was committed
and later deleted is still compromised — it lives forever in the reachable history
and is recoverable by anyone with a clone. This scans every unique blob reachable
from any ref (``git rev-list --all``) — deliberately NOT unreachable/dangling
objects, which never get pushed and would only surface local test artifacts as
false positives (matrix row **C — git-history secret scan**).

History is immutable: a real finding can't be fixed with an in-line
``allow-secret`` marker (you can't edit the past), so the remedy is **rotation**.
A fingerprint allowlist (``[secrets].history_allow``) acknowledges findings already
rotated / known-benign. Native: reuses :func:`meta_harness.secrets.scan_text` over
blob text the check feeds from git. The actual secret is never emitted — only a
one-way fingerprint — so receipts never re-leak it. See docs/specs/SPEC-secret-history.md
and ADR-0042.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass

from meta_harness.secrets import scan_text


def fingerprint(kind: str, secret: str) -> str:
    """A short, stable, one-way id for a finding — safe to print and to allowlist.

    Derived from the kind + the matched secret text, so the same secret yields the
    same fingerprint across every blob it appears in (enabling dedup and allowlisting)
    without ever exposing the secret itself."""
    return hashlib.sha256(f"{kind}:{secret}".encode()).hexdigest()[:16]


@dataclass(frozen=True)
class HistoryFinding:
    """A unique secret found in history: its kind, the blob it was first seen in, and
    its fingerprint (the allowlist key). The secret text itself is intentionally absent."""

    kind: str
    blob: str
    fingerprint: str


def scan_blobs(blobs: Iterable[tuple[str, str]], allow: Iterable[str] = ()) -> list[HistoryFinding]:
    """Scan ``(blob_sha, text)`` pairs for secrets, returning one finding per unique
    secret not in ``allow``.

    Deduplicates by fingerprint (the same secret recurs in every historical blob of a
    file), so each distinct leaked secret is reported once, attributed to the first
    blob it was seen in. Allowlisted fingerprints are dropped."""
    allowed = set(allow)
    seen: set[str] = set()
    findings: list[HistoryFinding] = []
    for blob, text in blobs:
        for match in scan_text(text):
            fp = fingerprint(match.kind, match.snippet)
            if fp in allowed or fp in seen:
                continue
            seen.add(fp)
            findings.append(HistoryFinding(kind=match.kind, blob=blob, fingerprint=fp))
    return findings
