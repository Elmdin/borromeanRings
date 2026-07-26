"""Native secret scanning — high-confidence provider tokens and private keys.

A hard-coded credential must never land in the tree (matrix row **C — secret
scanning**). This is deliberately a **high-confidence, low-false-positive** scan:
only well-formed provider tokens and private-key blocks, whose shapes almost never
occur by accident. Generic "high-entropy string" / secret-named-assignment
heuristics — the noisy part — are left to a tool (gitleaks) on the CI heavy lane;
a T0 gate that cries wolf gets disabled. Native stdlib ``re``; no external tool.

See docs/specs/SPEC-secrets.md and ADR-0032.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# (name, compiled pattern). High-confidence shapes only.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private-key-block",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
    ),
    ("aws-access-key-id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github-pat", re.compile(r"\bghp_[A-Za-z0-9]{36}\b")),
    ("github-fine-grained-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{82}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("stripe-secret-key", re.compile(r"\b(?:sk|rk)_live_[0-9A-Za-z]{16,}\b")),
    ("slack-webhook", re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/]+")),
)

# The scanner ignores its own pattern source so this module never flags itself.
_ALLOW_MARKER = "borromeanrings: allow-secret"


@dataclass(frozen=True)
class SecretFinding:
    """One high-confidence secret match: its kind, location, and a truncated snippet."""

    kind: str
    path: str
    line: int
    snippet: str


def scan_text(text: str, path: str = "") -> list[SecretFinding]:
    """High-confidence secret findings in ``text`` (one per matching line).

    A line carrying the ``borromeanrings: allow-secret`` marker is skipped (for
    documented examples/fixtures)."""
    findings: list[SecretFinding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if _ALLOW_MARKER in line:
            continue
        for kind, pattern in _PATTERNS:
            match = pattern.search(line)
            if match:
                findings.append(
                    SecretFinding(
                        kind=kind, path=path, line=lineno, snippet=match.group(0)[:12] + "…"
                    )
                )
    return findings


def scan_files(paths: list[Path]) -> list[SecretFinding]:
    """Scan each readable text file in ``paths``; unreadable/binary files are skipped."""
    findings: list[SecretFinding] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue  # binary or unreadable — not a text secret
        findings.extend(scan_text(text, str(path)))
    return findings
